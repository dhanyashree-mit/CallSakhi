import requests

BASE_URL = "http://localhost:8000"

def test_endpoint(path, data):
    print(f"Testing {path}...")
    try:
        response = requests.post(f"{BASE_URL}{path}", data=data)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

print("--- Testing /incoming-call ---")
test_endpoint("/incoming-call", {"From": "+918431065602"})

print("\n--- Testing /voice-callback ---")
test_endpoint("/voice-callback", {"CallSid": "CA12345"})

print("\n--- Testing /handle-response ---")
test_endpoint("/handle-response", {"CallSid": "CA12345", "SpeechResult": "Chapter 2"})
