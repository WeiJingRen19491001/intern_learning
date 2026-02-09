import requests
import json
import time

# Configuration
URL = "http://localhost:8000/api/v1/chat/ask"
QUESTION = "路觅的员工"

def test_stream_chunks():
    print(f"Testing stream endpoint: {URL}")
    print(f"Question: {QUESTION}")
    print("-" * 50)

    try:
        start_time = time.time()
        response = requests.post(
            URL, 
            json={"question": QUESTION}, 
            headers={"Content-Type": "application/json"},
            stream=True
        )

        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            print(response.text)
            return

        chunk_count = 0
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data_str = decoded_line[6:]
                    
                    if data_str == '[DONE]':
                        print("\n" + "-" * 50)
                        print("[Stream Completed]")
                        break
                    
                    try:
                        data = json.loads(data_str)
                        chunk_count += 1
                        
                        # Pretty print the chunk, highlighting key fields
                        print(f"\n[Chunk #{chunk_count}]")
                        print(f"  Text: {repr(data.get('text', ''))}")
                        print(f"  Is Finish: {data.get('is_finish')}")
                        
                        if data.get('latency'):
                            print(f"  >>> LATENCY: {data['latency']} ms <<<")
                        
                        if data.get('usage'):
                            print(f"  >>> USAGE: {data['usage']} <<<")
                            
                        # Print full raw JSON for verification if it's the last one or contains latency
                        if data.get('latency') or data.get('is_finish'):
                             print(f"  Raw: {json.dumps(data, ensure_ascii=False)}")
                             
                    except json.JSONDecodeError:
                        print(f"Raw (Parse Error): {data_str}")
                else:
                    # Heartbeats or comments
                    pass

        total_time = (time.time() - start_time) * 1000
        print("-" * 50)
        print(f"Client-side measured Total Time: {int(total_time)}ms")

    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to localhost:8000. Is the server running?")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    test_stream_chunks()
