# CallSakhi AI Voice Tutor 📞🎓

CallSakhi is a state-of-the-art AI-powered voice tutor designed to bridge the educational gap for students in India. It enables students to study Science chapters through a natural phone conversation—no internet or smartphone required on the student's end.

---

## 🌟 Key Features
- **Voice-First Learning**: Natural conversation with "Savitri," a strict but helpful Science tutor.
- **RAG Powered**: Uses **MongoDB Atlas Vector Search** to ensure the AI only teaches from verified textbook content.
- **Multi-Mode Education**:
  - **Concept Mode**: Explains core definitions and ideas.
  - **Quiz Mode**: Interactive MCQs with scoring.
  - **Revision Mode**: Summary of key exam points.
- **Analytics Dashboard**: A premium **Streamlit** dashboard to track student engagement, accuracy, and call telemetry.
- **Automated Summaries**: Sends a post-call SMS summary to the student via Twilio.

---

## 🛠️ Tech Stack
- **FastAPI**: High-performance Python backend.
- **Twilio**: Telephony and SMS API.
- **Groq (Llama 3.1)**: Ultra-fast AI inference.
- **MongoDB Atlas**: Vector database for RAG (Retrieval-Augmented Generation).
- **Supabase**: Session logging and message persistence.
- **Streamlit**: Real-time analytics dashboard.
- **Cloudflare Tunnels**: Secure local-to-internet bridging.

---

## 🚀 Setup Instructions

### 1. Prerequisites
- **Python 3.9+**
- **Twilio Account** (SID, Auth Token, and a Phone Number)
- **Groq API Key**
- **MongoDB Atlas Cluster** (with Vector Search enabled)
- **Cloudflared** installed on your machine.

### 2. Environment Configuration
Create a `.env` file in the root directory:

```env
# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=your_number

# AI & DB
GROQ_API_KEY=your_groq_key
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/callsakhi?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# Tunnel URL (Must match cloudflared output)
BASE_URL=https://your-unique-id.trycloudflare.com
```

### 3. Installation
```powershell
pip install -r requirements.txt
```

### 4. Knowledge Base Ingestion
Place your Science textbooks (PDFs) in the `knowledge_base/` folder, then run:
```powershell
python ingest.py
```
*Note: Ensure you create a Vector Index in Atlas UI named `vector_index` mapping the `embedding` field.*

---

## 🚦 How to Run

### Step 1: Start the Tunnel
```powershell
./cloudflared tunnel --url http://127.0.0.1:8000
```
**Copy the `https://...` URL** and update your `.env` (BASE_URL) and Twilio Webhook.

### Step 2: Start the Main Server
```powershell
python main.py
```

### Step 3: Start the Analytics Dashboard
```powershell
streamlit run dashboard/app.py
```

---

## 🔧 Troubleshooting

### "Application Error" on Call
1. **URL Mismatch**: Ensure your Cloudflare URL matches the one in your Twilio Console "A Call Comes In" webhook.
2. **Missing '+'**: Ensure you call with your full international number (e.g., `+91...`).
3. **Server Startup**: Wait for the "Uvicorn running" message before calling.

### SSL Handshake Errors (Windows)
If you see `SSL: TLSV1_ALERT_INTERNAL_ERROR`, ensure your `MONGODB_URI` contains `&tls=true&tlsAllowInvalidCertificates=true`. We have implemented a bypass in the code to handle these local certificate issues on Windows.

### Content Not Found
If Savitri says she can't find the chapter, ensure:
- The PDF filename matches the chapter name (e.g., `Electricity.pdf`).
- You have run `ingest.py` recently.
- Your Atlas Vector Search index is named `vector_index`.

---

## 📊 Analytics Dashboard
The dashboard provides real-time telemetry on:
- **Total Calls** & **Students Helped**.
- **Average Quiz Accuracy** per chapter.
- **Live Mission Monitor**: Real-time log of active sessions.

![CallSakhi Analytics Dashboard](dashboard_screenshot.jpeg)

---

## 📱 User Experience
After every session, students receive an automated SMS summary of their performance and the key concepts discussed:

![CallSakhi SMS Summary](sms_screenshot.jpeg)


