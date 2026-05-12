from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

def save_message(call_sid, speaker, message):
    data = {
        "call_sid": call_sid,
        "speaker": speaker,
        "message": message
    }

    supabase.table("call_messages").insert(data).execute()

    print(f"[DB] Saved {speaker} message")