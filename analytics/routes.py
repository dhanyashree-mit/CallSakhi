from fastapi import APIRouter
from analytics.pipeline import get_analytics_collection

router = APIRouter()

@router.get("/kpis")
async def get_kpis():
    collection = get_analytics_collection()
    if collection is None:
        return {"error": "Database not connected"}
    
    total_calls = collection.count_documents({})
    
    pipeline = [
        {"$group": {
            "_id": None,
            "total_duration": {"$sum": "$duration_seconds"},
            "avg_accuracy": {"$avg": "$accuracy_percentage"},
            "active_students": {"$addToSet": "$student_number_hash"}
        }}
    ]
    
    results = list(collection.aggregate(pipeline))
    if not results:
        return {
            "total_calls": total_calls,
            "total_hours": 0,
            "avg_accuracy": 0,
            "students_helped": 0
        }
        
    data = results[0]
    return {
        "total_calls": total_calls,
        "total_hours": round(data.get("total_duration", 0) / 3600, 2),
        "avg_accuracy": round(data.get("avg_accuracy", 0), 1),
        "students_helped": len(data.get("active_students", []))
    }

@router.get("/chapter-performance")
async def get_chapter_performance():
    collection = get_analytics_collection()
    if collection is None:
        return {"error": "Database not connected"}
        
    pipeline = [
        {"$group": {
            "_id": "$chapter",
            "calls": {"$sum": 1},
            "avg_score": {"$avg": "$quiz_score"},
            "avg_accuracy": {"$avg": "$accuracy_percentage"}
        }},
        {"$sort": {"calls": -1}}
    ]
    
    return list(collection.aggregate(pipeline))

@router.get("/live-monitor")
async def get_live_monitor():
    collection = get_analytics_collection()
    if collection is None:
        return {"error": "Database not connected"}
        
    recent_calls = list(collection.find(
        {},
        {"_id": 0, "call_sid": 1, "chapter": 1, "duration_seconds": 1, "accuracy_percentage": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(10))
    
    return recent_calls
