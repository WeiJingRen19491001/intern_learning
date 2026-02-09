import json
import asyncio
import threading
import time
from http import HTTPStatus
from typing import AsyncGenerator
import dashscope
from loguru import logger
from app.core.config import settings

# Configure DashScope
dashscope.api_key = settings.DASHSCOPE_API_KEY

class BailianService:
    @staticmethod
    async def stream_chat(query: str, session_id: str = None) -> AsyncGenerator[str, None]:
        """
        Call Bailian Application (Agent) API with streaming.
        Returns a generator of JSON strings (SSE data).
        Uses a separate thread to handle the synchronous DashScope API call
        to prevent blocking the asyncio event loop.
        """
        start_time = time.time()
        # Explicitly set maxsize=0 for infinite capacity, though it is the default
        queue = asyncio.Queue(maxsize=0)
        loop = asyncio.get_running_loop()

        def producer():
            # Retry logic for connection setup or early failures
            max_retries = 2
            for attempt in range(max_retries + 1):
                has_yielded = False
                try:
                    # Set a reasonable timeout (e.g., 60s connect, 120s read)
                    # DashScope 'timeout' arg applies to requests.
                    responses = dashscope.Application.call(
                        app_id=settings.BAILIAN_APP_ID,
                        prompt=query,
                        session_id=session_id,
                        stream=True,
                        flow_stream_mode="message_format",
                        incremental_output=True, # Ensure we get full text states for delta calculation
                        timeout=120  # 2 minutes timeout to prevent infinite hangs
                    )
                    
                    for response in responses:
                        has_yielded = True
                        loop.call_soon_threadsafe(queue.put_nowait, response)
                    
                    # If completed successfully
                    loop.call_soon_threadsafe(queue.put_nowait, None) # Sentinel
                    return

                except Exception as e:
                    is_last_attempt = (attempt == max_retries)
                    
                    # Only retry if we haven't sent any partial data yet (to avoid duplicate text on UI)
                    if not has_yielded and not is_last_attempt:
                        logger.warning(f"Bailian API Attempt {attempt+1} failed: {e}. Retrying...")
                        time.sleep(1) # Brief pause
                        continue
                    
                    # Otherwise, propagate error
                    logger.error(f"Bailian API failed (Attempt {attempt+1}, yielded={has_yielded}): {e}")
                    loop.call_soon_threadsafe(queue.put_nowait, e)
                    return

        # Start the producer thread
        logger.info(f"Starting Bailian thread for query: {query}")
        thread = threading.Thread(target=producer, daemon=True)
        thread.start()

        yield json.dumps({"text": "", "is_finish": False, "request_id": "init"}) # Keep-alive / Start

        # Keep track of length to calculate delta
        last_text_len = 0
        finished_emitted = False
        
        # Diagnostic Timers
        t0 = time.time()
        last_chunk_time = t0
        chunk_count = 0
        
        # Buffer for Workflow specific message accumulation
        accumulated_workflow_content = ""
        last_workflow_seq_id = -1

        try:
            while True:
                # Measure waiting time for API
                wait_start = time.time()
                item = await queue.get()
                wait_duration_ms = (time.time() - wait_start) * 1000
                
                if item is None:
                    break
                
                chunk_count += 1
                current_time = time.time()
                interval_ms = (current_time - last_chunk_time) * 1000
                last_chunk_time = current_time
                
                # Log first packet specifically (Time To First Token)
                if chunk_count == 1:
                    logger.info(f"[Perf] TTFT (Time To First Token): {int((current_time - t0) * 1000)}ms. Request ID: {getattr(item, 'request_id', 'unknown')}")
                elif wait_duration_ms > 1000:
                    # If we waited more than 1 second for the NEXT chunk from API
                    logger.warning(f"[Perf] Slow API Detected! Waited {int(wait_duration_ms)}ms for chunk #{chunk_count} from Bailian")
                
                if isinstance(item, Exception):
                    logger.error(f"Error in Bailian thread: {item}")
                    yield json.dumps({"error": str(item), "request_id": getattr(item, 'request_id', 'unknown')})
                    break

                response = item
                
                # processing start
                proc_start = time.time()
                
                if response.status_code == HTTPStatus.OK:
                    full_text = ""
                    rag_res = None
                    web_res = None
                    
                    # RAW OUTPUT from Bailian (this might be the JSON string)
                    raw_output_text = getattr(response.output, 'text', '')
                    if raw_output_text is None:
                        raw_output_text = ""
                    
                    # Log raw text growth to see if parsing is lagging
                    # logger.debug(f"[Perf] Chunk #{chunk_count} Raw Len: {len(raw_output_text)}")
                    
                    # --- NEW PARSING LOGIC FOR Workflow 2.0 --- #
                    # Target: extract 'llm_result' from correct source.
                    # Source 1: Standard 'text' field (for normal Chat or simple Workflow)
                    # Source 2: 'workflow_message.message.content' (for Complex Workflow)
                    
                    parse_source_text = raw_output_text
                    
                    # Heuristic: Check if response.output has workflow_message
                    # This handles the case where 'text' is null but 'workflow_message' is populated
                    wf_msg = getattr(response.output, 'workflow_message', None)
                    if wf_msg and isinstance(wf_msg, dict):
                         # If we have a workflow message, check if it has content
                         inner_msg = wf_msg.get('message', {})
                         # Check Sequence ID
                         seq_id = wf_msg.get('node_msg_seq_id', -1)
                         
                         if isinstance(inner_msg, dict):
                             content_str = inner_msg.get('content')
                             if content_str:
                                 # Log content to verify behavior
                                 # logger.debug(f"[Workflow] Seq: {seq_id} Content: {content_str}")
                                 
                                 # Only append if this is a new sequence to avoid duplicates if any
                                 # (Assuming strict incremental streaming)
                                 if seq_id > last_workflow_seq_id:
                                     accumulated_workflow_content += content_str
                                     last_workflow_seq_id = seq_id
                                 elif seq_id == -1:
                                     # No ID, just append?
                                     accumulated_workflow_content += content_str

                    # If we have accumulated workflow content, use it as the source
                    if accumulated_workflow_content:
                        parse_source_text = accumulated_workflow_content

                    # Initialize parsing variables
                    is_finish = False
                    f_reason = getattr(response.output, 'finish_reason', None)
                    if f_reason and f_reason != "null":
                        is_finish = True

                    # 1. Try to Parse if it is a JSON String
                    is_json_parsed = False
                    try:
                        # Try parsing full text as JSON first
                        json_data = json.loads(parse_source_text)
                        
                        if isinstance(json_data, dict):
                            llm_result = json_data.get('llm_result')
                            
                            # Note: rag_result/web_result might still be in raw_output_text or response.output
                            # We check those in Step 3/Manual Helper separately or assume they are extracted elsewhere.
                            # But if they are inside this json_data (because parse_source_text was the container), grab them.
                            if not rag_res: rag_res = json_data.get('rag_result')
                            if not web_res: web_res = json_data.get('web_result')
                            
                            if llm_result:
                                full_text = llm_result
                                is_json_parsed = True
                    except:
                        pass
                        
                    # 2. If parsing failed, try Manual Extraction from partial string (For Streaming 'llm_result')
                    # We use 'parse_source_text' which now points to the correct container
                    if not is_json_parsed and parse_source_text:
                         # Heuristic: Extract content of "llm_result"
                         import re
                         # Look for "llm_result": " ...
                         match_start = parse_source_text.find('"llm_result"')
                         if match_start != -1:
                             # Locate start of value quote
                             val_start = parse_source_text.find('"', match_start + 12) # length of "llm_result"
                             if val_start != -1:
                                 # We are inside the string value.
                                 # This logic extracts until non-escaped quote
                                 curr = val_start + 1 
                                 chars = []
                                 while curr < len(parse_source_text):
                                     c = parse_source_text[curr]
                                     if c == '\\':
                                         if curr + 1 < len(parse_source_text):
                                             next_c = parse_source_text[curr+1]
                                             chars.append('\\' + next_c) 
                                             curr += 2
                                         else:
                                             break
                                     elif c == '"':
                                         break
                                     else:
                                         chars.append(c)
                                         curr += 1
                                 
                                 partial_json_str = '"' + "".join(chars) + '"'
                                 try:
                                     full_text = json.loads(partial_json_str)
                                 except:
                                     full_text = "".join(chars).replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')

                    # 3. Fallback: If no llm_result found, use raw text ONLY if it's not a JSON structure
                    is_workflow_like = parse_source_text.strip().startswith('{') and ('"llm_result"' in parse_source_text or '"rag_result"' in parse_source_text)
                    
                    if not full_text and not is_json_parsed and not is_workflow_like:
                         full_text = parse_source_text
                    
                    # Log parsing state for debugging
                    if not full_text and is_workflow_like and not is_finish:
                         # This explains "NO content" chunks: Workflow is streaming internal state (like RAG) but LLM hasn't started correcting text yet.
                         # logger.debug(f"[Perf] Workflow state update (No LLM text yet). Raw head: {raw_output_text[:50]}...")
                         pass

                    # Manual Helper to extract JSON fields from string (Balanced Bracket)
                    def extract_balanced_json(text, key_name):
                        import re
                        # Find key followed by colon
                        key_pat = f'"{key_name}"\s*:\s*'
                        match = re.search(key_pat, text)
                        if not match:
                            return None
                        
                        start_idx = match.end()
                        if start_idx >= len(text): return None
                        
                        # Check start char
                        start_char = text[start_idx]
                        if start_char not in ['{', '[']:
                             # Maybe it's null or string or number. For rag/web result we expect obj or list.
                             return None
                        
                        # Balance counting
                        stack = [start_char]
                        curr = start_idx + 1
                        in_quote = False
                        escape = False
                        
                        while curr < len(text) and stack:
                            c = text[curr]
                            if not in_quote:
                                if c == '"':
                                    in_quote = True
                                elif c == '{' or c == '[':
                                    stack.append(c)
                                elif c == '}' or c == ']':
                                    # Check match
                                    last = stack[-1]
                                    if (last == '{' and c == '}') or (last == '[' and c == ']'):
                                        stack.pop()
                                    else:
                                        # Mismatch? Malformed?
                                        pass
                            else:
                                # In quote
                                if escape:
                                    escape = False
                                elif c == '\\':
                                    escape = True
                                elif c == '"':
                                    in_quote = False
                            
                            curr += 1
                        
                        if not stack:
                            # Complete
                            json_substr = text[start_idx:curr]
                            try:
                                return json.loads(json_substr)
                            except:
                                return None
                        return None

                    # If not fully parsed via json.loads, try to extract rag/web result incrementally
                    # Use 'parse_source_text' to support both direct and workflow modes
                    if not is_json_parsed and parse_source_text:
                        if not rag_res:
                            rag_res = extract_balanced_json(parse_source_text, "rag_result")
                        if not web_res:
                            web_res = extract_balanced_json(parse_source_text, "web_result")

                    # Manual Delta Calculation
                    delta_text = full_text[last_text_len:]
                    last_text_len = len(full_text)

                    # (is_finish logic moved up)
                    
                    # Log delta status to debug "invisible" chunks
                    if not delta_text and not is_finish and not rag_res and not web_res:
                        # logger.debug(f"[Perf] Chunk #{chunk_count} yielded NO content. FullTextLen: {len(full_text)}")
                        pass
                    elif delta_text:
                        # NEW: Measure Real TTFT (Time To First Text)
                        if last_text_len == len(delta_text): # This is the FIRST chunk with text content (since last_text_len was 0 before this block)
                            real_ttft = int((time.time() - start_time) * 1000)
                            logger.info(f"[Perf] REAL TTFT (Content Arrived): {real_ttft}ms at Chunk #{chunk_count}")
                        if chunk_count % 42 == 0:
                            logger.debug(f"[Perf] Chunk #{chunk_count} Delta: {len(delta_text)} chars")

                    # --- Sources Extraction (Standard + Workflow JSON) ---
                    sources_list = []

                    # Helper to safely get
                    def safe_get(obj, key):
                        try:
                            if isinstance(obj, dict): return obj.get(key)
                            if hasattr(obj, key): return getattr(obj, key)
                        except:
                            return None
                        return None
                    
                    # COMMENTED OUT: Do not eagerly fetch from response.output if we are in string parsing mode (implied by non-empty raw_output_text which is a dict string)
                    # This respects the User's claim that sources come "from complete json" and prevents "fake" early display if SDK returns them early.
                    # However, we only do this if we haven't found them yet, to allow the manual extraction to take precedence if successful.
                    # Actually, if we couldn't extract them manually (still streaming), and we block this, we get "True Streaming" (delayed sources).
                    # But checking raw_output_text content is safer.
                    
                    # Heuristic: If raw_output_text looks like a JSON object starting with {, prefer manual extraction logic.
                    is_workflow_json_stream = raw_output_text.strip().startswith('{') and '"llm_result"' in raw_output_text
                    
                    if not rag_res and not is_workflow_json_stream:
                        rag_res = safe_get(response.output, 'rag_result')
                    if not web_res and not is_workflow_json_stream:
                        web_res = safe_get(response.output, 'web_result')

                    # === SOURCES BUFFERING LOGIC ===
                    # User request: "Separate these two, append reference sources AFTER real stream output"
                    # Solution: We calculate sources as we find them, but we only YIELD them when is_finish=True.
                    
                    # A. Standard Bailian sources
                    std_refs = safe_get(response.output, 'doc_references')
                    if std_refs:
                        sources_list.extend(std_refs)

                    # B. Workflow: "rag_result" (Knowledge Base)
                    if rag_res:
                        if isinstance(rag_res, dict) and 'chunkList' in rag_res:
                            chunk_list = rag_res['chunkList']
                            if isinstance(chunk_list, list):
                                for item in chunk_list:
                                    s_item = item.copy() if isinstance(item, dict) else {"raw": item}
                                    if isinstance(item, dict):
                                        s_item["title"] = item.get('title') or item.get('documentName') or '知识库文档'
                                        s_item["url"] = item.get('docUrl') or item.get('url') or '#'
                                    else:
                                        s_item["title"] = '知识库文档'
                                        s_item["url"] = '#'
                                    sources_list.append(s_item)
                        elif isinstance(rag_res, list):
                            for item in rag_res:
                                if isinstance(item, dict):
                                    s_item = item.copy()
                                    s_item["title"] = item.get('title') or item.get('doc_name') or '知识库文档'
                                    s_item["url"] = item.get('url') or item.get('docUrl') or item.get('doc_id') or '#'
                                    sources_list.append(s_item)
                        elif isinstance(rag_res, dict):
                             s_item = rag_res.copy()
                             s_item["title"] = rag_res.get('title') or rag_res.get('documentName') or '知识库文档'
                             s_item["url"] = rag_res.get('docUrl') or rag_res.get('url') or '#'
                             sources_list.append(s_item)

                    # C. Workflow: "web_result" (Search)
                    if web_res:
                         if not isinstance(web_res, list): web_res = [web_res]
                         for item in web_res:
                             if isinstance(item, dict):
                                 s_item = item.copy()
                                 s_item["title"] = item.get('title') or '网络搜索结果'
                                 s_item["url"] = item.get('link') or item.get('url') or '#'
                                 sources_list.append(s_item)

                    # KEY CHANGE: Do not assign to 'sources' variable for immediate yield unless finished
                    # But we also need to pass rag_res/web_res to router for DB only at the end?
                    # Actually, router accumulates whenever it sees them.
                    # But the frontend only renders what it sees.
                    # So we HIDE it from frontend by sending None, but we need to eventually send it.
                    
                    current_sources = sources_list if sources_list else None
                    yield_sources = None # Default to None for intermediate chunks
                    
                    # Capture raw results for DB storage
                    # rag_res and web_res are already extracted above via safe_get

                    # Extract usage if available

                    usage_info = None
                    if hasattr(response, 'usage'):
                        # Temporarily remove DEBUG log
                        usage_obj = response.usage
                        
                        # Helper to safely get attributes
                        def get_token_count(obj, attr):
                            try:
                                val = getattr(obj, attr, 0)
                                return val if val is not None else 0
                            except (KeyError, AttributeError):
                                return 0

                        # Try direct access first
                        in_tokens = get_token_count(usage_obj, 'input_tokens')
                        out_tokens = get_token_count(usage_obj, 'output_tokens')

                        # If zero, try accessing via 'models' list if it exists (common in Agent responses)
                        if in_tokens == 0 and out_tokens == 0:
                            models = getattr(usage_obj, 'models', None)
                            if models and isinstance(models, list) and len(models) > 0:
                                # Sum up usage from all models
                                for m in models:
                                    in_tokens += get_token_count(m, 'input_tokens')
                                    out_tokens += get_token_count(m, 'output_tokens')

                        usage_info = {
                            "input_tokens": in_tokens,
                            "output_tokens": out_tokens
                        }

                    # Smoothing Logic: If chunk is large (e.g. > 5 chars), split it to simulate typing
                    # This prevents "jumps" when model buffer flushes.
                    # Speed control: Adaptive to prevent large latency
                    # Base: ~500-1000 chars/sec to ensure we don't lag behind model too much
                    SMOOTH_THRESHOLD = 5
                    
                    if len(delta_text) > SMOOTH_THRESHOLD: 
                        # Adaptive step size: if chunk is huge, step bigger to drain faster
                        # Target ~0.5s to drain any chunk size
                        step = max(5, int(len(delta_text) / 20)) 
                        
                        total_len = len(delta_text)
                        curr_idx = 0
                        
                        while curr_idx < total_len:
                            end_idx = min(curr_idx + step, total_len)
                            sub_chunk = delta_text[curr_idx:end_idx]
                            curr_idx = end_idx
                            
                            is_last_sub = (curr_idx >= total_len)
                            
                            # Inherit finish state only on the very last sub-chunk
                            sub_is_finish = is_finish and is_last_sub
                            
                            # Handle Finish State for this sub-packet
                            sub_latency = None
                            if sub_is_finish:
                                 if finished_emitted:
                                     sub_is_finish = False
                                 else:
                                     finished_emitted = True
                                     sub_latency = int((time.time() - start_time) * 1000)
                                     logger.info(f"[Perf] Request Finished [ID:{response.request_id}] - Latency: {sub_latency}ms - Usage: {usage_info}")
                            
                            chunk_data = {
                                "text": sub_chunk,
                                "is_finish": sub_is_finish,
                                "sources": current_sources, # Update sources live
                                "request_id": response.request_id,
                                "usage": usage_info if sub_is_finish else None,
                                "latency": sub_latency,
                                "rag_result": rag_res if sub_is_finish and rag_res else None,
                                "web_result": web_res if sub_is_finish and web_res else None
                            }
                            yield json.dumps(chunk_data)
                            # Minimal sleep to yield control but resume fast
                            await asyncio.sleep(0.015)

                    elif delta_text or is_finish or (current_sources and not last_text_len) or (is_finish and (rag_res or web_res)):
                        
                        latency_ms = None
                        # Handle Finish State
                        if is_finish:
                             if finished_emitted:
                                 # Already finished, just end
                                 is_finish = False
                             else:
                                 finished_emitted = True
                                 latency_ms = int((time.time() - start_time) * 1000)
                                 logger.info(f"[Perf] Request Finished [ID:{response.request_id}] - Latency: {latency_ms}ms - Usage: {usage_info}")

                        chunk_data = {
                            "text": delta_text,
                            "is_finish": is_finish,
                            "sources": current_sources, # Live streaming of sources
                            "request_id": response.request_id,
                            "usage": usage_info if is_finish else None,
                            "latency": latency_ms,
                            "rag_result": rag_res if is_finish and rag_res else None,
                            "web_result": web_res if is_finish and web_res else None
                        }
                        yield json.dumps(chunk_data)

                else:
                    # Non-OK status loop
                    error_msg = response.message
                    if isinstance(error_msg, str):
                        try:
                            # Try to parse inner JSON error info if possible
                            # e.g. {"nodeName":...}
                            err_json = json.loads(error_msg)
                            if "errorInfo" in err_json:
                                error_msg = f"{err_json.get('nodeName', 'Node')}: {err_json['errorInfo']}"
                        except:
                            pass
                    
                    logger.error(f"Bailian API Error: {response.code} - {error_msg}")
                    yield json.dumps({"error": f"Error: {response.code} - {error_msg}"})
        except Exception as e:
            logger.exception("Exception in BailianService async loop")
            yield json.dumps({"error": str(e)})

