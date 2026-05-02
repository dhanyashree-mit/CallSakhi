# CallSakhi AI Voice Tutor 📞🎓

CallSakhi is an AI-powered voice tutor designed to help students in India study Science chapters through a simple phone call. It uses Twilio for telephony, Groq for the AI brain, and FastAPI for the backend.

## 🚀 Setup Instructions

### 1. Prerequisites
- Python 3.8 or higher installed.
- A Twilio Account (Sign up at [twilio.com](https://www.twilio.com)).
- A Groq API Key (Get it from [console.groq.com](https://console.groq.com)).
- `cloudflared` installed (To expose your local server to the internet).

### 2. Twilio Configuration
1. Log in to your **Twilio Console**.
2. Buy or get a **Trial Phone Number**.
3. Note down your **Account SID**, **Auth Token**, and your **Twilio Phone Number**.
4. (Optional) For high-quality Indian English voice, ensure "Polly" voices are enabled in your Twilio account settings.

### 3. Local Project Setup
1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd CallSakhi
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure Environment Variables**:
   Create a file named `.env` in the root folder and copy the following (replacing with your own keys):
   ```env
   # Twilio Credentials
   TWILIO_ACCOUNT_SID=your_account_sid_here
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_PHONE_NUMBER=your_twilio_number_here

   # AI API Keys
   GROQ_API_KEY=your_groq_api_key_here

   # Tunnel URL (Update this every time you restart your tunnel)
   BASE_URL=https://your-unique-tunnel-id.trycloudflare.com
   ```

### 4. Running the Application

Follow these steps in order:

#### Step A: Start the Tunnel
In a new terminal window, run:
```bash
./cloudflared tunnel --url http://127.0.0.1:8000
```
Look for a line in the output that looks like:
`https://random-words-here.trycloudflare.com`
**Copy this URL** and paste it as your `BASE_URL` in the `.env` file.

#### Step B: Start the Server
In another terminal window, run:
```bash
python main.py
```

#### Step C: Configure Twilio


**Option 2: TwiML Bin**
1. Go to **Twilio Console** > **Runtime** > **TwiML Bins** > **Create New Bin**.
2. **Friendly Name**: `CallSakhi Trigger`.
3. **TwiML Value**:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
       <!-- This notifies your server then rejects the call -->
       <Redirect method="POST">https://your-tunnel.trycloudflare.com/incoming-call</Redirect>
   </Response>
   ```
4. Go to your **Phone Number** settings.
5. Under "A CALL COMES IN", select **TwiML Bin** and pick `CallSakhi Trigger`.
6. Click **Save**.

### 5. Start a Lesson!

**Method A: Call the Number**
This will cost 0.5 for each call .Instaed try the second option of triggering the call from terminal 
Just call your Twilio phone number from your mobile. The call will hang up immediately, and Savitri will call you back in 3 seconds.

**Method B: Trigger from Terminal (Quick Test)**
If you don't want to call the number, you can "force" a callback from your terminal. Replace `+91XXXXXXXXXX` with your actual phone number:

**Windows (PowerShell):**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/incoming-call" -Method Post -Body "From=+91XXXXXXXXXX"
```



---
## 🛠️ Tech Stack
- **FastAPI**: Backend framework.
- **Twilio**: Voice API.
- **Groq (Llama 3.1)**: AI Model for conversation.
- **Cloudflare Tunnels**: Secure local-to-internet access.
