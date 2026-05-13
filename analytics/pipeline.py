import os
import hashlib
import time
from datetime import datetime
from pymongo import MongoClient
import certifi

_mongo_client = None

def get_analytics_collection():
    global _mongo_client
    if not _mongo_client:
        uri = os.getenv("MONGODB_URI")
        if not uri:
            return None
        _mongo_client = MongoClient(
            uri,
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=15000
        )
    try:
        _mongo_client.admin.command('ping')
    except Exception:
        # Reconnect on ping failure
        _mongo_client = MongoClient(
            os.getenv("MONGODB_URI"),
            tls=True,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=15000
        )
    return _mongo_client["callsakhi_analytics"]["call_analytics"]

def process_analytics_post_call(call_sid: str, student_number: str, state_data: dict, call_duration: int = None):
    """
    Idempotent, decoupled background task to extract metrics from session state.
    Guaranteed not to affect live telephony or SMS logic.
    """
    try:
        print(f"--- [ANALYTICS] Starting background processing for {call_sid} ---")
        collection = get_analytics_collection()
        if collection is None:
            print("--- [ANALYTICS ERROR] MongoDB URI missing ---")
            return

        # 1. Privacy Hashing
        student_number_hash = None
        if student_number:
            # Add a secret salt if desired, but standard SHA-256 is okay for this scope
            student_number_hash = hashlib.sha256(student_number.encode('utf-8')).hexdigest()

        # 2. Extract metrics incrementally from state
        chapter = state_data.get("chapter", "Unknown")
        quiz_score = state_data.get("quiz_score", 0)
        engagement_score = state_data.get("engagement_score", 0)
        
        # Calculate duration if Twilio didn't provide it
        start_time_iso = state_data.get("start_time")
        if call_duration is None and start_time_iso:
            try:
                # Handle Z at the end if present
                clean_iso = start_time_iso.replace("Z", "+00:00")
                start_dt = datetime.fromisoformat(clean_iso)
                call_duration = int((datetime.utcnow() - start_dt.replace(tzinfo=None)).total_seconds())
            except Exception:
                call_duration = 0
        elif call_duration is None:
            call_duration = 0
            
        accuracy = 0
        total_questions = state_data.get("quiz_q_num", 0)
        if total_questions > 0:
             accuracy = (quiz_score / total_questions) * 100

        analytics_doc = {
            "call_sid": call_sid,
            "student_number_hash": student_number_hash,
            "chapter": chapter,
            "duration_seconds": call_duration,
            "quiz_score": quiz_score,
            "total_questions": total_questions if total_questions > 0 else 3,
            "accuracy_percentage": round(accuracy, 2),
            "engagement_score": engagement_score,
            "call_status": "completed",
            "start_time": start_time_iso,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # 3. Idempotent Upsert (Protects against Twilio retry duplicates)
        result = collection.update_one(
            {"call_sid": call_sid},
            {"$setOnInsert": analytics_doc},
            upsert=True
        )
        
        if result.upserted_id:
            print(f"--- [ANALYTICS SUCCESS] Upserted new record for {call_sid} ---")
        else:
            print(f"--- [ANALYTICS IDEMPOTENCY] Record already exists for {call_sid} ---")

    except Exception as e:
        # Massive try/except block ensures complete isolation.
        print(f"--- [ANALYTICS ERROR] Silently handled failure: {e} ---")
