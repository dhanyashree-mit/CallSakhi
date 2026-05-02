import os
import time
from groq import Groq
from fastapi import FastAPI, Form, Response, BackgroundTasks, Request
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

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

# NEW: Super Simple English Persona
SAVITRI_PROMPT = """
You are Savitri, a very kind and simple AI teacher for girls in India.
- Use VERY SIMPLE English words.
- Speak slowly in your mind so you use short sentences.
- Use only common words that a 10th-grade girl in a village would know.
1. First, ask for the Chapter.
2. Then, ask for the Mode (Concept, Practice, or Revision).
3. Then, start the lesson.
"""

# Voice Settings
VOICE_NAME = "Polly.Aditi" # Premium Indian Female Voice
LANGUAGE_CODE = "en-IN"

# Session storage (Key: CallSid)
sessions = {}

def get_ai_response(call_sid, user_input):
    try:
        if call_sid not in sessions:
            sessions[call_sid] = [{"role": "system", "content": SAVITRI_PROMPT}]
        
        sessions[call_sid].append({"role": "user", "content": user_input})
        
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=sessions[call_sid],
            max_tokens=150
        )
        
        ai_text = completion.choices[0].message.content
        sessions[call_sid].append({"role": "assistant", "content": ai_text})
        return ai_text
    except Exception as e:
        print(f"--- [ERROR] Groq failed for {call_sid}: {e} ---")
        return "I'm sorry, I missed that. Can you say it again?"

def trigger_callback(user_number: str):
    time.sleep(3)
    try:
        print(f"--- [TELEPHONY] Calling back: {user_number} ---")
        client.calls.create(
            to=user_number,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}/voice-callback"
        )
    except Exception as e:
        print(f"--- [ERROR] Callback failed for {user_number}: {e} ---")

@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(background_tasks: BackgroundTasks, From: str = Form(None), request: Request = None):
    # Get caller number
    if not From:
        From = request.query_params.get("From")
    
    if not From:
        return Response(content="<Response><Say>Server live!</Say></Response>", media_type="application/xml")
    
    print(f"--- [INCOMING] Call from: {From} ---")
    background_tasks.add_task(trigger_callback, From)
    
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
        input="speech", 
        action=f"{BASE_URL}/handle-response", 
        timeout=5, 
        language=LANGUAGE_CODE
    )
    gather.say(greeting, voice=VOICE_NAME, language=LANGUAGE_CODE)
    
    # If they don't say anything, wait and retry
    response.redirect(f"{BASE_URL}/voice-callback")
    return Response(content=str(response), media_type="application/xml")

@app.api_route("/handle-response", methods=["GET", "POST"])
async def handle_response(CallSid: str = Form(None), SpeechResult: str = Form(None), request: Request = None):
    if not CallSid:
        CallSid = request.query_params.get("CallSid", "unknown")
    if not SpeechResult:
        SpeechResult = request.query_params.get("SpeechResult")

    print(f"--- [RESPONSE] CallSid: {CallSid}, User said: {SpeechResult} ---")
    response = VoiceResponse()
    
    if not SpeechResult:
        response.say("I did not hear you. Please speak again.", voice=VOICE_NAME, language=LANGUAGE_CODE)
        response.redirect(f"{BASE_URL}/voice-callback")
        return Response(content=str(response), media_type="application/xml")

    ai_text = get_ai_response(CallSid, SpeechResult)
    
    gather = response.gather(
        input="speech", 
        action=f"{BASE_URL}/handle-response", 
        timeout=5, 
        language=LANGUAGE_CODE
    )
    gather.say(ai_text, voice=VOICE_NAME, language=LANGUAGE_CODE)
    
    # Ensure call doesn't just end if they stay silent after AI speaks
    response.redirect(f"{BASE_URL}/handle-response")
    
    return Response(content=str(response), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

