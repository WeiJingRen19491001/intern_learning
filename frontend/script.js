document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    
    // Q&A Elements
    const chatStreamContainer = document.getElementById('chat-stream-container');

    // View Elements
    const viewChat = document.getElementById('view-chat');
    const viewHistory = document.getElementById('view-history');
    const toHistoryBtn = document.getElementById('to-history-btn');
    const backToChatBtn = document.getElementById('back-to-chat-btn');
    const historyList = document.getElementById('history-list');

    // Config for marked.js
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true
        });
    }

    // Elements for History Sub-views
    const historyListView = document.getElementById('history-list-view');
    const historyDetailView = document.getElementById('history-detail-view');

    // --- Event Listeners ---
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            sendMessage();
        }
    });

    // Navigation Logic
    toHistoryBtn.addEventListener('click', () => {
        viewChat.style.display = 'none';
        viewHistory.style.display = 'flex'; // Use flex to maintain layout
        
        // Reset to list view
        historyListView.style.display = 'block';
        historyDetailView.style.display = 'none';
        
        loadHistory();
    });

    backToChatBtn.addEventListener('click', () => {
        // If we are in detail view, go back to list view first
        if (historyDetailView.style.display === 'block') {
            historyDetailView.style.display = 'none';
            historyListView.style.display = 'block';
        } else {
            // Otherwise go back to chat
            viewHistory.style.display = 'none';
            viewChat.style.display = 'flex';
        }
    });

    async function loadHistory() {
        historyList.innerHTML = '<li style="padding:20px;text-align:center;color:#666;">加载中...</li>';
        try {
            const res = await fetch('http://localhost:8000/api/v1/chat/history?limit=30');
            const data = await res.json();
            
            historyList.innerHTML = '';
            if (data.length === 0) {
                historyList.innerHTML = '<li style="padding:20px;text-align:center;color:#666;">暂无记录</li>';
                return;
            }

            data.forEach(item => {
                const li = document.createElement('li');
                li.className = 'history-entry';
                const dateC = new Date(item.created_at).toLocaleString();
                li.innerHTML = `
                    <div class="history-content-wrapper">
                        <div class="history-meta">${dateC}</div>
                        <div class="history-q">Q: ${escapeHtml(item.user_query)}</div>
                        <div class="history-a-preview">A: ${escapeHtml((item.ai_response || "").substring(0, 100))}${item.ai_response && item.ai_response.length > 100 ? '...' : ''}</div>
                    </div>
                    <div style="display:flex;align-items:center;">
                        <button class="delete-btn" title="删除记录">🗑️</button>
                        <div class="history-arrow">→</div>
                    </div>
                `;
                
                // Click to view detail
                li.addEventListener('click', () => {
                   showHistoryDetail(item);
                });

                // Click to delete
                const delBtn = li.querySelector('.delete-btn');
                delBtn.addEventListener('click', async (e) => {
                    e.stopPropagation(); // Prevent opening detail view
                    if (confirm('确认删除这条历史记录吗?')) {
                        await deleteHistoryLog(item.id, li);
                    }
                });

                historyList.appendChild(li);
            });

        } catch (e) {
            historyList.innerHTML = `<li style="padding:20px;color:red;text-align:center;">加载失败: ${e}</li>`;
        }
    }

    async function deleteHistoryLog(id, liElement) {
        try {
            const res = await fetch(`http://localhost:8000/api/v1/chat/history/${id}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                // Remove from UI with fade out
                liElement.style.transition = 'opacity 0.3s, transform 0.3s';
                liElement.style.opacity = '0';
                liElement.style.transform = 'translateX(20px)';
                setTimeout(() => {
                    liElement.remove();
                    // If list empty, reload to show "No records"
                    if (historyList.children.length === 0) loadHistory();
                }, 300);
            } else {
                alert('删除失败');
            }
        } catch (e) {
            console.error(e);
            alert('删除出错: ' + e.message);
        }
    }

    function showHistoryDetail(item) {
        historyListView.style.display = 'none';
        historyDetailView.style.display = 'block';
        
        // Extract Meta
        const dateC = new Date(item.created_at).toLocaleString();
        const usage = item.metadata_info?.usage || null;
        const latency = item.metadata_info?.latency || null;
        const sessionId = item.session_id || 'N/A';
        const sources = item.sources || [];

        // Build HTML
        let usageHtml = '未知';
        if (usage) {
             const input = usage.input_tokens || 0;
             const output = usage.output_tokens || 0;
             const total = input + output;
             usageHtml = `${total} (提问:${input} / 回答:${output})`;
        }
        
        let sourcesHtml = '';
        if (sources && sources.length > 0) {
            sourcesHtml = '<div class="meta-sources"><strong>参考来源:</strong><ul>';
            sources.forEach((source, index) => {
                const label = source.title || source.url || 'Document';
                const type = source.type || 'rag';
                // Unified source-link class and structure
                sourcesHtml += `<li><a href="#" class="history-source-link" data-idx="${index}" data-type="${type}">${escapeHtml(label)}</a></li>`;
            });
            sourcesHtml += '</ul></div>';
        } else {
             sourcesHtml = '<div style="margin-top:10px;color:#999;font-size:0.9em;">无参考来源</div>';
        }

        historyDetailView.innerHTML = `
            <div class="history-detail-card">
                <div class="detail-header">
                    <div class="detail-time">⏰ ${dateC}</div>
                    <div class="detail-id" style="font-size:0.8em;color:#999;">Session: ${sessionId}</div>
                </div>
                
                <div class="qa-item user">
                    <div class="qa-role-label">Q</div>
                    <div class="qa-content" style="font-weight:bold;">${escapeHtml(item.user_query)}</div>
                </div>
                
                <div class="separator"></div>
                
                <div class="qa-item ai">
                    <div class="qa-role-label">A</div>
                    <div class="qa-content markdown-body">
                        ${marked.parse(item.ai_response || "(无回答内容)")}
                    </div>
                </div>

                <div class="ai-meta" style="margin-top:20px; padding-top:15px; border-top:1px dashed #ddd;">
                    ${sourcesHtml}
                    <div class="meta-stats" style="margin-top:10px; font-size:0.9em; color:#666; background:#f5f5f5; padding:8px; border-radius:4px;">
                        <div>⏱️ 耗时: ${latency ? (latency > 1000 ? (latency/1000).toFixed(2)+'s' : latency+'ms') : '未知'}</div>
                        <div>📊 Token: ${usageHtml}</div>
                    </div>
                </div>
            </div>
        `;
        
        // Attach event listeners for history view sources
        const links = historyDetailView.querySelectorAll('.history-source-link');
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const idx = parseInt(e.target.getAttribute('data-idx'));
                if (sources && sources[idx]) {
                    showSourceModal(sources[idx]);
                }
            });
        });
    }

    // Helper to create and append a Q&A card
    function appendQACard(question, initialAnswer = '') {
        const card = document.createElement('div');
        card.className = 'qa-card';
        card.innerHTML = `
            <div class="qa-item user">
                <div class="qa-role-label">Q</div>
                <div class="qa-content">${escapeHtml(question)}</div>
            </div>
            <div class="separator"></div>
            <div class="qa-item ai">
                <div class="qa-role-label">A</div>
                <div class="qa-content markdown-body"></div>
            </div>
        `;
        chatStreamContainer.appendChild(card);
        
        const contentDiv = card.querySelector('.qa-item.ai .qa-content');
        
        // Create structure for text and metadata to coexist without overwriting
        const textContainer = document.createElement('div');
        textContainer.className = 'ai-text';
        
        const metaContainer = document.createElement('div');
        metaContainer.className = 'ai-meta';
        metaContainer.style.marginTop = '10px';
        metaContainer.style.fontSize = '0.85em';
        metaContainer.style.color = '#666';
        metaContainer.style.borderTop = '1px solid #eee';
        metaContainer.style.paddingTop = '8px';
        metaContainer.style.display = 'none'; // Hide until we have data

        contentDiv.appendChild(textContainer);
        contentDiv.appendChild(metaContainer);

        if (initialAnswer) {
            textContainer.innerHTML = marked.parse(initialAnswer);
        } else {
            textContainer.innerHTML = '<span class="thinking-status">正在努力检索中...</span><span class="cursor">|</span>';
        }

        // Scroll into view
        card.scrollIntoView({ behavior: 'smooth', block: 'end' });
        
        return { textContainer, metaContainer, card }; // Return containers
    }

    // --- Main Sending Logic ---
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        // Reset UI
        toggleInput(false);
        userInput.value = ''; // Clear immediately
        
        // 1. Create a new card in the stream
        const { textContainer, metaContainer } = appendQACard(text);
        
        let accumulatedText = "";
        let accumulatedSources = [];
        let finalUsage = null;
        let finalLatency = null;

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: text,
                    session_id: getSessionId()
                })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') break;
                        try {
                            const data = JSON.parse(dataStr);

                            // Handle Error from Backend
                            if (data.error) {
                                accumulatedText += `<br><span style="color:red">⚠️ ${data.error}</span>`;
                                textContainer.innerHTML = marked.parse(accumulatedText);
                            }
                            
                            // Handle Text
                            if (data.text) {
                                accumulatedText += data.text;
                                textContainer.innerHTML = marked.parse(accumulatedText);
                            }

                            // Handle Sources
                            if (data.sources && Array.isArray(data.sources)) {
                                // Merge logic: append new distinct sources instead of overwriting
                                data.sources.forEach(newSource => {
                                    // Deduplicate based on URL and Title to avoid duplicates if backend sends overlapping chunks
                                    const exists = accumulatedSources.some(s => 
                                        (s.url === newSource.url && s.title === newSource.title)
                                    );
                                    if (!exists) {
                                        accumulatedSources.push(newSource);
                                    }
                                });
                                updateMeta(metaContainer, accumulatedSources, finalUsage, finalLatency);
                            }

                            // Handle Usage/Latency
                            if (data.usage) finalUsage = data.usage;
                            if (data.latency) finalLatency = data.latency;
                            
                            if (data.usage || data.latency) {
                                updateMeta(metaContainer, accumulatedSources, finalUsage, finalLatency);
                            }

                        } catch (e) {
                            console.error('Parse Error', e);
                        }
                    }
                }
            }
        } catch (err) {
            textContainer.innerHTML += `<br><span style="color:red">[Error: ${err.message}]</span>`;
        } finally {
            toggleInput(true);
            userInput.focus();
        }
    }

    function updateMeta(container, sources, usage, latency) {
        // Only hide if absolutely no data
        if ((!sources || sources.length === 0) && !usage && !latency) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        let html = '';

        // Sources Rendering (Matching History Detail Style)
        if (sources && sources.length > 0) {
            html += '<div class="meta-sources"><strong>参考来源:</strong><ul>';
            sources.forEach((source, index) => {
                const label = source.title || source.url || 'Document';
                const type = source.type || 'rag';
                // Use data-type for icon selection in CSS
                html += `<li><a href="#" class="source-link" data-index="${index}" data-type="${type}">${escapeHtml(label)}</a></li>`;
            });
            html += '</ul></div>';
        }

        // Stats Rendering
        if (usage || latency) {
            let parts = [];
            if (latency) {
                // Format latency: if > 1000ms, show seconds, else ms
                const timeStr = latency > 1000 ? (latency / 1000).toFixed(2) + 's' : latency + 'ms';
                parts.push(`⏱️ ${timeStr}`);
            }
            if (usage) {
                const input = usage.input_tokens || 0;
                const output = usage.output_tokens || 0;
                const total = input + output;
                parts.push(`📊 ${total} tokens (In:${input}/Out:${output})`);
            }
            if (parts.length > 0) {
                html += `<div class="meta-stats" style="margin-top:10px; font-size:0.85em; opacity:0.8; color:#666; border-top:1px dashed #eee; padding-top:4px;">
                    ${parts.join(' &nbsp;|&nbsp; ')}
                </div>`;
            }
        }

        container.innerHTML = html;

        // Attach Click Listeners
        const links = container.querySelectorAll('.source-link');
        links.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const index = parseInt(e.target.getAttribute('data-index'));
                if (sources && sources[index]) {
                    showSourceModal(sources[index]);
                }
            });
        });
    }

    // Modal Logic
    function showSourceModal(sourceData) {
        let modalContainer = document.getElementById('modal-container');
        if (!modalContainer) {
            modalContainer = document.createElement('div');
            modalContainer.id = 'modal-container';
            document.body.appendChild(modalContainer);
        }

        const jsonString = JSON.stringify(sourceData, null, 2);
        const title = sourceData.title || 'Source Detail';

        modalContainer.innerHTML = `
            <div class="modal-overlay" id="source-modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>${escapeHtml(title)}</h3>
                        <button id="close-modal-btn">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="json-viewer"><pre><code>${escapeHtml(jsonString)}</code></pre></div>
                    </div>
                </div>
            </div>
        `;

        // Close handlers
        const overlay = document.getElementById('source-modal-overlay');
        const closeBtn = document.getElementById('close-modal-btn');
        
        const closeParams = () => {
            modalContainer.innerHTML = '';
        };

        closeBtn.onclick = closeParams;
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                closeParams();
            }
        };

        // Highlight if available
        if (typeof hljs !== 'undefined') {
            const codeBlock = modalContainer.querySelector('pre code');
            hljs.highlightElement(codeBlock);
        }
    }

    function getSessionId() {
        let sessionId = sessionStorage.getItem('lumi_session_id');
        if (!sessionId) {
            // Simple UUID-like generator
            sessionId = 'sess-' + Date.now().toString(36) + '-' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('lumi_session_id', sessionId);
        }
        return sessionId;
    }

    function toggleInput(enabled) {
        sendBtn.disabled = !enabled;
        userInput.disabled = !enabled;
        if (!enabled) {
            sendBtn.querySelector('.loading-spinner').style.display = 'inline-block';
            sendBtn.querySelector('.btn-text').textContent = '生成中';
        } else {
            sendBtn.querySelector('.loading-spinner').style.display = 'none';
            sendBtn.querySelector('.btn-text').textContent = '发送';
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
