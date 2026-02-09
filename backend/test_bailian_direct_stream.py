import sys
import os
import time
import dashscope
from dashscope import Application
# Ensure we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings

# Configure DashScope
dashscope.api_key = settings.DASHSCOPE_API_KEY

def test_bailian_direct_stream():
    query = "路觅的员工" # 使用您出问题的同一个 Query
    print(f"Testing Bailian App Direct Stream")
    print(f"App ID: {settings.BAILIAN_APP_ID}")
    print(f"Query: {query}")
    print("-" * 60)

    start_time = time.time()
    
    try:
        responses = Application.call(
            app_id=settings.BAILIAN_APP_ID,# 替换为实际的应用 ID
            base_address="https://dashscope.aliyuncs.com/api/v1/",
            stream=True, # 开启流式输出
            flow_stream_mode="message_format",# 消息模式，输出/结束节点的流式结果
            incremental_output=False,
            prompt=query)
        
        chunk_count = 0
        last_chunk_time = start_time
        last_len = 0
        
        for response in responses:
            chunk_count += 1
            curr_time = time.time()
            interval = (curr_time - last_chunk_time) * 1000
            total_elapsed = (curr_time - start_time) * 1000
            last_chunk_time = curr_time
            
            # Extract Text
            # raw_text = getattr(response.output, 'text', '') or ""
            raw_text = response.output.workflow_message["message"]["content"] or ""
            if chunk_count == 1:
                print(f"response: {response.output}")
            # break
            curr_len = len(raw_text)
            delta = curr_len - last_len
            
            # Print Status
            status = "WAITING"
            if delta > 0:
                status = f"GROWING (+{delta})"
            elif delta == 0:
                status = "NO CHANGE"
                
            print(f"[Chunk #{chunk_count:03d}] T+{int(total_elapsed):5d}ms (Diff: {int(interval):4d}ms) | Len: {curr_len:5d} | {status}")
            
            # Optional: Peek at content if it suddenly grows a lot
            if delta > 1:
                print(f"    >>> SUDDEN BURST DETECTED! First 50 chars: {raw_text[:30]}...")

            last_len = curr_len

        print("-" * 60)
        print(f"Total Latency: {int((time.time() - start_time) * 1000)}ms")
        
    except Exception as e:
        print(f"Failed to call Bailian API: {e}")

if __name__ == "__main__":
    test_bailian_direct_stream()
