import os
import dashscope
from dashscope import Application
# Load .env manually or just assume env vars are set if I run in the same terminal session
# But for safety I'll use python-dotenv if available, or just rely on the user to ensure env is set.
# I'll try to load from .env file in parent dir.
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("BAILIAN_APP_ID")
API_KEY = os.getenv("DASHSCOPE_API_KEY")

print(f"App ID: {APP_ID}")
print(f"API Key present: {bool(API_KEY)}")

if not API_KEY:
    print("Error: DASHSCOPE_API_KEY not found")
    exit(1)

dashscope.api_key = API_KEY

def test_call():
    print("Testing call...")
    try:
        # Try passing timeout
        responses = Application.call(
            app_id=APP_ID,
            prompt="Hello",
            stream=True,
            timeout=10 # Try a short timeout to see if it's accepted
        )
        for r in responses:
            print(r)
            break # Just need one
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_call()
