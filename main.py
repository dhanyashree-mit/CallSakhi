import os
import re
import time
from services.db_service import save_message
from groq import Groq
from fastapi import FastAPI, Form, Response, BackgroundTasks, Request
from twilio.rest import Client
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from pymongo import MongoClient
import certifi

# Load environment variables
# Load environment variables from absolute path
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=env_path)
print(f"--- [DEBUG] Loading env from: {env_path}")

app = FastAPI()

# Mount Analytics Dashboard Routes (Isolated from live call paths)
from analytics.routes import router as analytics_router
app.include_router(analytics_router, prefix="/api/analytics")

# Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize AI & Telephony
try:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    groq_client = Groq(api_key=GROQ_API_KEY)
    print("--- [SUCCESS] System Initialized ---")
except Exception as e:
    print(f"--- [ERROR] Initialization failed: {e} ---")

# Savitri Prompt - STRICT rules to prevent hallucination
SAVITRI_PROMPT = """
You are Savitri, a strict Class 10 Science tutor for Indian students.

=== ABSOLUTE RULES (NEVER BREAK THESE) ===
1. You will be told which chapter is locked. NEVER mention or teach any other chapter.
2. You will be given textbook context. USE ONLY THAT CONTEXT. Do not use any outside knowledge.
3. If context is empty or irrelevant, say EXACTLY: "I could not find that in our textbook. Please try again."
4. NEVER say things like "In many textbooks, Chapter 6 is...". You only know what the context says.
5. DO NOT mention any chapter number or name other than the locked one.
6. Use simple English for a 10th-grade student.

=== MODES ===
CONCEPT mode: Extract key concepts from the context using bullet points.
QUIZ mode: Ask 1 MCQ at a time (4 options: A, B, C, D). Wait for answer. After 3 questions give a score.
REVISION mode: List 5 key exam points from the context only.
"""

def normalize(text):
    return str(text).lower().strip().replace("&", "and")

# Voice Settings
VOICE_NAME = "Polly.Aditi" # Premium Indian Female Voice
LANGUAGE_CODE = "en-IN"

# Vector DB Setup (MongoDB Atlas)
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "callsakhi"
COLLECTION_NAME = "knowledge"
ATLAS_VECTOR_SEARCH_INDEX_NAME = "vector_index"

embeddings = None
vector_search = None

def load_db():
    global vector_search, embeddings
    print("--- [AI] Starting Database Initialization... ---", flush=True)
    
    current_uri = os.getenv("MONGODB_URI")
    if not current_uri:
        print("--- [WARNING] MONGODB_URI is empty or None! ---", flush=True)
        return

    print(f"--- [DEBUG] Using MONGODB_URI: {current_uri[:15]}... (Length: {len(current_uri)})", flush=True)

    try:
        print("--- [AI] Connecting to MongoDB Atlas... ---", flush=True)
        # Using both options for maximum compatibility
        client = MongoClient(current_uri)
        
        print("--- [AI] Pinging MongoDB... ---", flush=True)
        try:
            client.admin.command('ping')
            print("--- [AI] Ping successful! ---", flush=True)
        except Exception as ping_err:
            print(f"--- [WARNING] Ping failed but proceeding: {ping_err} ---", flush=True)

        collection = client[DB_NAME][COLLECTION_NAME]
        
        # Initialize embeddings ONLY after successful DB connection
        if embeddings is None:
            print("--- [AI] Loading Embedding Model (this may take a minute)... ---", flush=True)
            embeddings = HuggingFaceEmbeddings(
                model_name='sentence-transformers/all-MiniLM-L6-v2', 
                model_kwargs={'device': 'cpu'}
            )
            print("--- [AI] Embedding Model Loaded! ---", flush=True)
            
        print("--- [AI] Initializing Vector Search... ---", flush=True)
        vector_search = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=embeddings,
            index_name=ATLAS_VECTOR_SEARCH_INDEX_NAME,
            text_key="text"  # CRITICAL: the field in MongoDB is 'text', not 'page_content'
        )
        print("--- [SUCCESS] Connected to MongoDB Atlas Vector Search ---", flush=True)
    except Exception as e:
        print(f"--- [ERROR] Database Initialization failed: {e} ---", flush=True)
        import traceback
        traceback.print_exc()

@app.on_event("startup")
async def startup_event():
    load_db()

# Session storage (Key: CallSid)
sessions = {}
session_state = {} # Stores locked chapter and stage

CHAPTER_MAPPING = {
    "1": "chemical reactions and equations",
    "2": "acids, bases and salts",
    "3": "metals and non-metals",
    "4": "carbon and its compounds",
    "5": "life processes",
    "6": "control and coordination",
    "7": "how do organisms reproduce",
    "8": "heredity",
    "9": "light – reflection and refraction",
    "10": "the human eye and the colourful world",
    "11": "electricity",
    "12": "magnetic effects of electric current",
    "13": "our environment"
}

def get_chapter_from_input(user_input):
    user_input_norm = normalize(user_input)
    # Check for direct number match
    if user_input_norm in CHAPTER_MAPPING:
        return CHAPTER_MAPPING[user_input_norm], user_input_norm
    
    # Robust matching: remove punctuation and handle minor variations
    def clean_text(t):
        # Remove common punctuation and normalize spaces
        for char in [",", ".", "-", "–", "?", "!"]:
            t = t.replace(char, " ")
        words = t.lower().split()
        # Robustness: ignore trailing 's' to handle plural vs singular
        words = [w.rstrip('s') for w in words]
        return " ".join(words)

    cleaned_input = clean_text(user_input_norm)
    for num, name in CHAPTER_MAPPING.items():
        cleaned_name = clean_text(name)
        # Check for partial matches or keyword overlaps
        if cleaned_name in cleaned_input or cleaned_input in cleaned_name:
            return name, num
            
    return None, None

def get_relevant_context(query, chapter=None):
    if vector_search:
        try:
            # Robust search: include chapter in query but don't force strict filtering
            search_query = f"{chapter} {query}" if chapter else query
            print(f"--- [RAG] Searching for: {search_query} ---")
            docs = vector_search.similarity_search(search_query, k=10)
            
            # Fallback: if no results, try searching without the chapter prefix
            if not docs and chapter:
                print(f"--- [RAG FALLBACK] No results with chapter prefix, searching query only... ---")
                docs = vector_search.similarity_search(query, k=10)

            if not docs:
                print(f"--- [WARNING] No documents found in database for: {query} ---")
                return ""
                
            print(f"--- [SUCCESS] Found {len(docs)} relevant chunks ---")
            return "\n".join([doc.page_content for doc in docs])
        except Exception as e:
            print(f"--- [ERROR] MongoDB Search failed: {e} ---")
    else:
        print("--- [ERROR] Vector Search not initialized ---")
    return ""

MODE_MENU = "Press 1 for Concept Explanation, 2 for Quiz, or 3 for Revision."

def _run_llm(messages, max_tokens=250):
    completion = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=messages,
        max_tokens=max_tokens
    )
    return completion.choices[0].message.content

def get_ai_response(call_sid, user_input):
    try:
        if call_sid not in sessions:
            sessions[call_sid] = [{"role": "system", "content": SAVITRI_PROMPT}]

        user_input_norm = normalize(user_input)

        if call_sid not in session_state:
            session_state[call_sid] = {
                "chapter": None, "chapter_num": None, "stage": "chapter_selection",
                "mode": None,
                "quiz_q_num": 0, "quiz_score": 0,
                "quiz_awaiting_answer": False, "quiz_correct_answer": None,
                "start_time": datetime.utcnow().isoformat() + "Z", "engagement_score": 0
            }

        state = session_state[call_sid]
        
        # Increment engagement score for each interaction
        if user_input_norm:
            state["engagement_score"] = state.get("engagement_score", 0) + 1

        # ── STAGE 1: CHAPTER SELECTION ──────────────────────────────────
        if state["stage"] == "chapter_selection":
            chapter_name, chapter_num = get_chapter_from_input(user_input)
            if chapter_name:
                state.update({"chapter": chapter_name, "chapter_num": chapter_num, "stage": "mode_selection"})
                ai_text = (f"Perfect! Chapter {chapter_num}: {chapter_name.title()} is now locked. "
                           f"What do you want to do? {MODE_MENU}")
                sessions[call_sid].append({"role": "user", "content": user_input})
                sessions[call_sid].append({"role": "assistant", "content": ai_text})
                print(f"--- [LOCKED] Chapter: {chapter_name} (#{chapter_num}) for {call_sid} ---")
                return ai_text
            return "I could not find that chapter. Please say a number from 1 to 13."

        chapter     = state["chapter"]
        chapter_num = state["chapter_num"]
        print(f"--- [CHAPTER LOCKED] Using: {chapter} for {call_sid} ---")

        # ── STAGE 2: MODE SELECTION ──────────────────────────────────────
        def is_mode(inp, num, *keywords):
            return inp == num or any(k in inp for k in keywords)

        if state["stage"] == "mode_selection":
            if is_mode(user_input_norm, "1", "concept", "explanation"):
                state.update({"stage": "learning", "mode": "explain"})
            elif is_mode(user_input_norm, "2", "quiz", "question"):
                state.update({"stage": "learning", "mode": "quiz",
                              "quiz_q_num": 0, "quiz_score": 0,
                              "quiz_awaiting_answer": False, "quiz_correct_answer": None})
            elif is_mode(user_input_norm, "3", "revision", "summary", "revise"):
                state.update({"stage": "learning", "mode": "revision"})
            else:
                return f"Please choose: press 1 for Concept, 2 for Quiz, or 3 for Revision for {chapter.title()}."

        # ── STAGE 3: LEARNING ────────────────────────────────────────────
        mode = state.get("mode", "explain")

        # Allow mode switch ONLY when NOT waiting for a quiz answer
        if state["stage"] == "learning" and not state.get("quiz_awaiting_answer"):
            if is_mode(user_input_norm, "1", "concept", "explanation") and mode != "explain":
                state.update({"mode": "explain"}); mode = "explain"
            elif is_mode(user_input_norm, "2", "quiz", "question") and mode != "quiz":
                state.update({"mode": "quiz", "quiz_q_num": 0, "quiz_score": 0,
                              "quiz_awaiting_answer": False, "quiz_correct_answer": None}); mode = "quiz"
            elif is_mode(user_input_norm, "3", "revision", "summary", "revise") and mode != "revision":
                state.update({"mode": "revision"}); mode = "revision"

        # ── QUIZ: ANSWER CHECKING ────────────────────────────────────────
        if mode == "quiz" and state.get("quiz_awaiting_answer"):
            correct = state.get("quiz_correct_answer", "1")
            if user_input_norm in ["1", "2", "3", "4"]:
                q_num = state["quiz_q_num"]
                if user_input_norm == correct:
                    state["quiz_score"] += 1
                    feedback = "That is correct! Well done."
                else:
                    letter = {"1":"A","2":"B","3":"C","4":"D"}.get(correct, correct)
                    feedback = f"That is not correct. The right answer is option {letter}."

                if q_num >= 3:
                    # Quiz finished
                    score = state["quiz_score"]
                    state.update({"quiz_awaiting_answer": False, "quiz_q_num": 0, "stage": "mode_selection"})
                    ai_text = (f"{feedback} Quiz complete! Your score is {score} out of 3. "
                               f"{MODE_MENU}")
                    sessions[call_sid].append({"role": "assistant", "content": ai_text})
                    print(f"--- [AI] Response: {ai_text} ---")
                    return ai_text
                else:
                    # Next question
                    state["quiz_awaiting_answer"] = False
                    return _generate_quiz_question(call_sid, chapter, chapter_num, state, prefix=feedback + " Next question. ")
            else:
                return "Please press 1, 2, 3, or 4 to choose your answer."

        # ── CONCEPT ──────────────────────────────────────────────────────
        if mode == "explain":
            context = get_relevant_context(f"core educational concepts and important definitions of {chapter}", chapter=chapter)
            start = time.time()
            if context:
                prompt = (f"LOCKED CHAPTER: {chapter}. Mode: CONCEPT.\n"
                          f"USE ONLY this textbook context:\n---\n{context}\n---\n"
                          f"Extract up to 3 clear bullet points explaining the core concepts. If the context is limited, extract what you can.\n"
                          f"After the points, end your response with exactly this text: '{MODE_MENU}'")
            else:
                return f"I could not find content for {chapter.title()}. {MODE_MENU}"
            ai_text = "You have chosen Concept Explanation. " + _run_llm(
                sessions[call_sid] + [{"role": "user", "content": prompt}])
            print(f"--- [DEBUG] LLM took {time.time()-start:.2f}s | [AI] {ai_text} ---")
            sessions[call_sid].append({"role": "assistant", "content": ai_text})
            return ai_text

        # ── REVISION ─────────────────────────────────────────────────────
        if mode == "revision":
            context = get_relevant_context(f"important points summary of {chapter}", chapter=chapter)
            start = time.time()
            if context:
                prompt = (f"LOCKED CHAPTER: {chapter}. Mode: REVISION.\n"
                          f"USE ONLY this textbook context:\n---\n{context}\n---\n"
                          f"List exactly 5 numbered key exam points. "
                          f"After the points end with exactly: '{MODE_MENU}'")
            else:
                return f"I could not find revision content for {chapter.title()}. {MODE_MENU}"
            ai_text = "You have chosen Revision. " + _run_llm(
                sessions[call_sid] + [{"role": "user", "content": prompt}])
            print(f"--- [DEBUG] LLM took {time.time()-start:.2f}s | [AI] {ai_text} ---")
            sessions[call_sid].append({"role": "assistant", "content": ai_text})
            return ai_text

        # ── QUIZ: GENERATE NEW QUESTION ───────────────────────────────────
        if mode == "quiz":
            return _generate_quiz_question(call_sid, chapter, chapter_num, state, is_first=(state["quiz_q_num"] == 0))

        return f"Please press 1 for Concept, 2 for Quiz, or 3 for Revision."

    except Exception as e:
        print(f"--- [ERROR] Groq failed for {call_sid}: {e} ---")
        return "I'm sorry, I missed that. Can you say it again?"


def _generate_quiz_question(call_sid, chapter, chapter_num, state, is_first=False, prefix=""):
    """Generate one MCQ, store correct answer, return display text."""
    state["quiz_q_num"] = state.get("quiz_q_num", 0) + 1
    q_num = state["quiz_q_num"]
    context = get_relevant_context(f"questions answers examples of {chapter}", chapter=chapter)
    print(f"--- [QUIZ] Generating question {q_num} for '{chapter}' ---")

    prompt = (
        f"LOCKED CHAPTER: {chapter}. Mode: QUIZ. Question {q_num} of 3.\n"
        f"USE ONLY this textbook context:\n---\n{context}\n---\n"
        f"Generate 1 multiple choice question. IMPORTANT: place the correct answer at a RANDOM position (not always option 3 or 4).\n"
        f"Use this EXACT format with no extra text:\n"
        f"Question {q_num}: [question]\n"
        f"1. [option]\n2. [option]\n3. [option]\n4. [option]\n"
        f"[ANSWER:X]\n"
        f"Replace X with the digit 1, 2, 3, or 4 that is the correct option. [ANSWER:X] must be the very last line."
    )
    raw = _run_llm(sessions[call_sid] + [{"role": "user", "content": prompt}], max_tokens=200)
    print(f"--- [QUIZ RAW] {raw} ---")

    # Try multiple parsing patterns for robustness
    match = (re.search(r'\[ANSWER:(\d)\]', raw) or
             re.search(r'ANSWER:\s*(\d)', raw) or
             re.search(r'ANSWER\s+(\d)', raw))
    if match:
        state["quiz_correct_answer"] = match.group(1)
        display = re.sub(r'(\[ANSWER:\d\]|ANSWER:?\s*\d)', '', raw).strip()
    else:
        state["quiz_correct_answer"] = "1"
        display = raw.strip()
        print(f"--- [QUIZ WARNING] Could not parse answer from response, defaulting to 1 ---")

    state["quiz_awaiting_answer"] = True

    intro = "You have chosen Quiz. " if is_first else ""
    ai_text = f"{intro}{prefix}{display} Press 1, 2, 3, or 4 to answer."
    sessions[call_sid].append({"role": "assistant", "content": ai_text})
    print(f"--- [AI] Response: {ai_text} ---")
    return ai_text

def trigger_callback(user_number: str):
    time.sleep(3)
    try:
        print(f"--- [TELEPHONY] Calling back: {user_number} ---")
        client.calls.create(
            to=user_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}/voice-callback",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['completed']
        )
    except Exception as e:
        print(f"--- [ERROR] Callback failed for {user_number}: {e} ---")
# sending sms to user
def send_summary_sms(to_number, summary_text):
    try:
        message = client.messages.create(
            body=summary_text,
            from_=TWILIO_PHONE_NUMBER,
            to=to_number,
            status_callback=f"{BASE_URL}/sms-status"
        )

        print(f"--- [SMS SENT] SID: {message.sid} ---")

    except Exception as e:
        print(f"--- [SMS ERROR] {e} ---")

@app.api_route("/call-status", methods=["POST"])
async def call_status(background_tasks: BackgroundTasks, CallSid: str = Form(None), CallStatus: str = Form(None), To: str = Form(None), CallDuration: int = Form(None)):
    print(f"--- [CALL STATUS] Call {CallSid} is {CallStatus} to {To} ---")
    if CallStatus in ["completed", "canceled", "failed", "no-answer"]:
        if CallSid in session_state:
            state = session_state[CallSid]
            chapter = state.get("chapter", "None")
            score = state.get("quiz_score", 0)
            summary_text = f"CallSakhi Summary\n\nChapter: {chapter.title() if chapter else 'None'}\nScore: {score}/3"
            
            if chapter and chapter != "None":
                context = get_relevant_context(f"main concepts of {chapter}", chapter=chapter)
                prompt = (f"LOCKED CHAPTER: {chapter}.\n"
                          f"USE ONLY this textbook context:\n---\n{context}\n---\n"
                          f"Provide a brief 2-sentence summary of the main concepts of this chapter for a 10th-grade student. Do not include any conversational filler.")
                try:
                    concept_summary = _run_llm([{"role": "user", "content": prompt}], max_tokens=150)
                    summary_text += f"\n\nConcepts Discussed:\n{concept_summary.strip()}"
                except Exception as e:
                    print(f"--- [ERROR] Failed to generate concept summary for SMS: {e} ---")
            
            # Use 'To' phone number as it's the user's phone number
            if To:
                send_summary_sms(To, summary_text)
            
            # --- TRIGGER ANALYTICS ---
            from analytics.pipeline import process_analytics_post_call
            state_copy = state.copy()
            background_tasks.add_task(process_analytics_post_call, CallSid, To, state_copy, CallDuration)
            
            # Clean up sessions to avoid memory leak
            session_state.pop(CallSid, None)
            sessions.pop(CallSid, None)
    return Response(status_code=200)

@app.api_route("/sms-status", methods=["POST"])
async def sms_status(MessageSid: str = Form(None), MessageStatus: str = Form(None)):
    print(f"--- [SMS STATUS] Message {MessageSid} status: {MessageStatus} ---")
    return Response(status_code=200)
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(background_tasks: BackgroundTasks, From: str = Form(None), request: Request = None):
    # Get caller number
    if not From:
        From = request.query_params.get("From")
    
    if not From:
        return Response(content="<Response><Say>Server live!</Say></Response>", media_type="application/xml")
    
    print(f"--- [INCOMING] Call from: {From} ---")
    
    # Normalize phone number: Ensure it starts with '+'
    clean_from = From.strip()
    if not clean_from.startswith('+'):
        clean_from = '+' + clean_from
    
    background_tasks.add_task(trigger_callback, clean_from)
    
    response = VoiceResponse()
    response.reject(reason="busy") # Hang up so we can call them back
    return Response(content=str(response), media_type="application/xml")

@app.api_route("/voice-callback", methods=["GET", "POST"])
async def voice_callback(CallSid: str = Form(None), request: Request = None):
    if not CallSid:
        CallSid = request.query_params.get("CallSid", "unknown")
    
    print(f"--- [CALLBACK] CallSid: {CallSid} ---")
    
    # Initialize session if not exists
    if CallSid not in sessions:
        sessions[CallSid] = [{"role": "system", "content": SAVITRI_PROMPT}]
    
    response = VoiceResponse()
    greeting = "Namaste! I am Savitri, your teacher. Which Science chapter do you want to study today?"
    
    gather = response.gather(
        input="speech dtmf", 
        action=f"{BASE_URL}/handle-response", 
        timeout=3,
        numDigits=2, # Support up to chapter 13
        speechTimeout="1",
        speechModel="phone_call",
        language=LANGUAGE_CODE
    )
    gather.say(greeting, voice=VOICE_NAME, language=LANGUAGE_CODE)
    
    # If they don't say anything, wait and retry
    response.redirect(f"{BASE_URL}/voice-callback")
    return Response(content=str(response), media_type="application/xml")

@app.api_route("/handle-response", methods=["GET", "POST"])
async def handle_response(CallSid: str = Form(None), SpeechResult: str = Form(None), Digits: str = Form(None), request: Request = None):
    if not CallSid:
        CallSid = request.query_params.get("CallSid", "unknown")
    
    user_input = Digits or SpeechResult
    # call summary
    save_message(CallSid, "student", user_input)
    print(f"--- [RESPONSE] CallSid: {CallSid}, User said/typed: {user_input} ---")
    response = VoiceResponse()
    
    # Intercept "bye" early
    if user_input and "bye" in user_input.lower():
        response.say("Namaste and goodbye! Thank you for studying with Savitri.", voice=VOICE_NAME, language=LANGUAGE_CODE)
        response.hangup()
        print(f"--- [HANGUP] User said bye. Ending call for {CallSid} ---")
        return Response(content=str(response), media_type="application/xml")
    
    if not user_input:
        # Don't restart from beginning if student is in an active session
        current_stage = session_state.get(CallSid, {}).get("stage", "chapter_selection")
        quiz_waiting  = session_state.get(CallSid, {}).get("quiz_awaiting_answer", False)

        if current_stage in ["mode_selection", "learning"]:
            if quiz_waiting:
                repeat_msg = "I did not hear you. Please press 1, 2, 3, or 4 to answer."
            else:
                repeat_msg = "I did not hear you. Please press 1 for Concept, 2 for Quiz, or 3 for Revision."
        else:
            repeat_msg = None

        if repeat_msg:
            gather = response.gather(
                input="speech dtmf",
                action=f"{BASE_URL}/handle-response",
                timeout=8, numDigits=1,
                speechTimeout="2", speechModel="phone_call", language=LANGUAGE_CODE
            )
            gather.say(repeat_msg, voice=VOICE_NAME, language=LANGUAGE_CODE)
            response.redirect(f"{BASE_URL}/handle-response")
        else:
            response.redirect(f"{BASE_URL}/voice-callback")
        return Response(content=str(response), media_type="application/xml")

    ai_text = get_ai_response(CallSid, user_input)
    save_message(CallSid, "agent", ai_text)
    if any(bye in ai_text.lower() for bye in ["goodbye", "namaste and goodbye"]):
        response.say(ai_text, voice=VOICE_NAME, language=LANGUAGE_CODE)
        response.hangup()
        print(f"--- [HANGUP] Ending call for {CallSid} ---")
        return Response(content=str(response), media_type="application/xml")

    gather = response.gather(
        input="speech dtmf",
        action=f"{BASE_URL}/handle-response",
        timeout=8,        # longer wait after AI speaks
        numDigits=1,      # captures 1-4 (all single digits)
        speechTimeout="2",
        speechModel="phone_call",
        language=LANGUAGE_CODE
    )
    gather.say(ai_text, voice=VOICE_NAME, language=LANGUAGE_CODE)
    response.redirect(f"{BASE_URL}/handle-response")
    return Response(content=str(response), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

