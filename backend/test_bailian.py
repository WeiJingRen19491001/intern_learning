import os
import sys
from dotenv import load_dotenv

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Load env manually to be sure
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

import dashscope
from dashscope import Application

def test_bailian():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    app_id = os.getenv("BAILIAN_APP_ID")
    
    print(f"API Key present: {bool(api_key)}")
    print(f"App ID present: {bool(app_id)}")
    
    if not api_key or not app_id:
        print("Missing credentials")
        return

    dashscope.api_key = api_key

    print("Sending request to Bailian...")
    try:
        responses = Application.call(
            app_id=app_id,
            prompt="你好",
            stream=True,
            incremental_output=True
        )
        for response in responses:
            if response.status_code == 200:
                print(f"Received chunk: {response.output.text[:20]}...")
            else:
                print(f"Error: {response.code} - {response.message}")
        print("Done.")
    except Exception as e:
        print(f"Exception happened: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bailian()
