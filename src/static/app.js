// 智能催收对话系统 - 前端JavaScript
class ChatDemo {
    constructor() {
        this.sessionId = null;
        this.isLoading = false;
        this.isFinished = false;
        this.simulationMode = false;
        this.pendingSimulatedReply = null;
        this.voiceMode = false;
        this.autoSimRunning = false;
        this.autoSimEventSource = null;
        this.currentAudio = null;
        this.pendingAudioUrls = [];

        this.initElements();
        this.bindEvents();
    }

    initElements() {
        this.chatArea = document.getElementById('chatArea');
        this.welcomeMessage = document.getElementById('welcomeMessage');
        this.sessionInfo = document.getElementById('sessionInfo');
        this.sessionIdEl = document.getElementById('sessionId');
        this.chatGroupEl = document.getElementById('chatGroup');
        this.currentStateEl = document.getElementById('currentState');

        this.chatGroupSelect = document.getElementById('chatGroup');
        this.customerNameInput = document.getElementById('customerName');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.translateBtn = document.getElementById('translateBtn');

        this.simulationPanel = document.getElementById('simulationPanel');
        this.toggleSimulationBtn = document.getElementById('toggleSimulation');
        this.simPersonaSelect = document.getElementById('simPersona');
        this.simResistanceSelect = document.getElementById('simResistance');
        this.generateReplyBtn = document.getElementById('generateReply');
        this.simulationResult = document.getElementById('simulationResult');
        this.simResultText = document.getElementById('simResultText');
        this.useSimReplyBtn = document.getElementById('useSimReply');

        this.voiceToggle = document.getElementById('voiceToggle');
        this.autoSimBtn = document.getElementById('autoSimBtn');
        this.simStatus = document.getElementById('simStatus');
        this.simStatusText = document.getElementById('simStatusText');
    }

    bindEvents() {
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.newChatBtn.addEventListener('click', () => this.newChat());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        this.translateBtn.addEventListener('click', () => this.translateInput());
        this.toggleSimulationBtn.addEventListener('click', () => this.toggleSimulation());
        this.generateReplyBtn.addEventListener('click', () => this.generateSimulatedReply());
        this.useSimReplyBtn.addEventListener('click', () => this.useSimulatedReply());
        this.voiceToggle.addEventListener('click', () => this.toggleVoiceMode());
        this.autoSimBtn.addEventListener('click', () => {
            if (this.autoSimRunning) {
                this.stopAutoSimulation();
            } else {
                this.startAutoSimulation();
            }
        });
    }

    async newChat() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.chatArea.innerHTML = '';
        this.isFinished = false;
        this.simulationResult.style.display = 'none';

        const chatGroup = this.chatGroupSelect.value;
        const customerName = this.customerNameInput.value || 'Pak / Bu';

        try {
            const endpoint = this.voiceMode ? '/voice/start' : '/chat/start';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    chat_group: chatGroup,
                    customer_name: customerName
                })
            });

            if (!response.ok) {
                throw new Error('开始对话失败');
            }

            const data = await response.json();
            this.sessionId = data.session_id;

            // 显示会话信息
            this.sessionInfo.style.display = 'flex';
            this.sessionIdEl.textContent = this.sessionId;
            this.chatGroupEl.textContent = data.chat_group || chatGroup;
            this.currentStateEl.textContent = data.state || data.current_state;

            // 启用输入
            this.messageInput.disabled = false;
            this.sendBtn.disabled = false;
            this.translateBtn.disabled = false;
            this.newChatBtn.textContent = '新对话';
            this.newChatBtn.classList.add('secondary');
            this.messageInput.placeholder = '输入客户回复...';

            // 添加agent消息
            const agentText = data.agent_text || data.agent_response;
            const msgId = this.addMessage('agent', agentText);

            // 语音模式：添加播放按钮并自动播放
            const audioUrl = data.audio_file || data.agent_audio_url;
            if (this.voiceMode && audioUrl) {
                this.addPlayButton(msgId, audioUrl);
                this.playAudio(audioUrl);
            }

        } catch (error) {
            console.error('Error:', error);
            alert('开始对话失败: ' + error.message);
        } finally {
            this.isLoading = false;
        }
    }

    async sendMessage() {
        if (this.isLoading || !this.sessionId || this.isFinished) return;

        const message = this.messageInput.value.trim();
        if (!message) return;

        this.isLoading = true;
        this.sendBtn.disabled = true;

        // 添加客户消息
        await this.addMessage('customer', message);
        this.messageInput.value = '';

        // 添加加载状态
        const loadingId = this.addLoadingMessage();

        try {
            const endpoint = this.voiceMode ? '/voice/turn' : '/chat/turn';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    customer_input: message
                })
            });

            if (!response.ok) {
                throw new Error('发送消息失败');
            }

            const data = await response.json();

            // 移除加载消息
            this.removeMessage(loadingId);

            // 更新状态
            this.currentStateEl.textContent = data.state || data.current_state;

            // 添加agent回复
            const agentText = data.agent_text || data.agent_response;
            const msgId = this.addMessage('agent', agentText);

            // 语音模式：添加播放按钮并自动播放
            const audioUrl = data.audio_file || data.agent_audio_url;
            if (this.voiceMode && audioUrl) {
                this.addPlayButton(msgId, audioUrl);
                this.playAudio(audioUrl);
            }

            // 检查是否结束
            if (data.is_finished) {
                this.isFinished = true;
                this.messageInput.disabled = true;
                this.sendBtn.disabled = true;
                this.addResultBanner(
                    data.is_successful !== undefined ? data.is_successful : !this.isFinished,
                    data.commit_time
                );
            }

        } catch (error) {
            console.error('Error:', error);
            this.removeMessage(loadingId);
            alert('发送消息失败: ' + error.message);
        } finally {
            this.isLoading = false;
            if (!this.isFinished) {
                this.sendBtn.disabled = false;
            }
        }
    }

    addMessage(role, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        const msgId = 'msg-' + Date.now();
        messageDiv.id = msgId;

        const time = new Date().toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });

        // 先显示消息，不等待翻译
        messageDiv.innerHTML = `
            <div class="message-content">
                <div>${this.escapeHtml(text)}</div>
                <div class="translation" id="trans-${msgId}" style="display:none"></div>
                <div class="message-time">${time}</div>
            </div>
        `;

        this.chatArea.appendChild(messageDiv);
        this.scrollToBottom();

        // 异步加载翻译，不阻塞
        this.loadTranslation(msgId, text, role);

        return msgId;
    }

    async loadTranslation(msgId, text, role) {
        try {
            const targetLang = role === 'agent' ? 'en' : 'id';
            const sourceLang = role === 'agent' ? 'id' : 'en';

            // 超时控制：3秒
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);

            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    source: sourceLang,
                    target: targetLang
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.translated_text !== text) {
                    const transDiv = document.getElementById('trans-' + msgId);
                    if (transDiv) {
                        transDiv.textContent = data.translated_text;
                        transDiv.style.display = 'block';
                    }
                }
            }
        } catch (e) {
            console.log('Translation skipped or failed:', e.message);
        }
    }

    async translateText(text, source, target) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);

            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    source: source,
                    target: target
                }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.translated_text !== text) {
                    return data.translated_text;
                }
            }
        } catch (e) {
            console.error('Translation error:', e);
        }
        return '';
    }

    async translateInput() {
        const text = this.messageInput.value.trim();
        if (!text) return;

        try {
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    source: 'zh',
                    target: 'id'
                })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    this.messageInput.value = data.translated_text;
                }
            }
        } catch (e) {
            console.error('Translation error:', e);
        }
    }

    toggleSimulation() {
        this.simulationMode = !this.simulationMode;
        if (this.simulationMode) {
            this.simulationPanel.classList.add('active');
            this.toggleSimulationBtn.textContent = '关闭仿真';
        } else {
            this.simulationPanel.classList.remove('active');
            this.toggleSimulationBtn.textContent = '仿真模式';
        }
    }

    async generateSimulatedReply() {
        if (!this.sessionId) {
            alert('请先开始对话');
            return;
        }

        const persona = this.simPersonaSelect.value;
        const resistance = this.simResistanceSelect.value;

        try {
            const response = await fetch('/api/simulate-customer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    persona: persona,
                    resistance_level: resistance
                })
            });

            if (!response.ok) {
                throw new Error('生成回复失败');
            }

            const data = await response.json();

            if (data.success) {
                this.pendingSimulatedReply = data.customer_response;
                this.simResultText.textContent = data.customer_response;
                this.simulationResult.style.display = 'block';
            } else {
                alert('生成回复失败');
            }

        } catch (error) {
            console.error('Error:', error);
            alert('生成回复失败: ' + error.message);
        }
    }

    useSimulatedReply() {
        if (this.pendingSimulatedReply) {
            this.messageInput.value = this.pendingSimulatedReply;
            this.simulationResult.style.display = 'none';
            this.pendingSimulatedReply = null;
        }
    }

    addLoadingMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message agent';
        messageDiv.id = 'loading-' + Date.now();

        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="loading">
                    <span class="loading-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                    </span>
                </div>
            </div>
        `;

        this.chatArea.appendChild(messageDiv);
        this.scrollToBottom();

        return messageDiv.id;
    }

    removeMessage(id) {
        const el = document.getElementById(id);
        if (el) {
            el.remove();
        }
    }

    addResultBanner(success, commitTime) {
        const banner = document.createElement('div');
        banner.className = `result-banner ${success ? 'success' : 'failed'}`;

        if (success) {
            banner.innerHTML = `
                ✅ 对话成功！约定还款时间: <strong>${this.escapeHtml(commitTime || '-')}</strong>
            `;
        } else {
            banner.innerHTML = '❌ 对话失败，未能达成还款约定';
        }

        this.chatArea.appendChild(banner);
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.chatArea.scrollTop = this.chatArea.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ============ 语音模式 ============

    toggleVoiceMode() {
        this.voiceMode = !this.voiceMode;
        if (this.voiceMode) {
            this.voiceToggle.classList.add('active');
            this.voiceToggle.textContent = '🔊 语音:开';
            this.messageInput.placeholder = '输入客户回复（Agent将语音播报）...';
        } else {
            this.voiceToggle.classList.remove('active');
            this.voiceToggle.textContent = '🔊 语音';
            this.messageInput.placeholder = '输入客户回复...';
            this.stopAllAudio();
        }
    }

    addPlayButton(msgId, audioUrl) {
        const msgEl = document.getElementById(msgId);
        if (!msgEl) return;
        const contentEl = msgEl.querySelector('.message-content');
        if (!contentEl) return;

        const btn = document.createElement('span');
        btn.className = 'play-audio-btn';
        btn.textContent = '🔊 播放';
        btn.dataset.audioUrl = audioUrl;
        btn.dataset.msgId = msgId;
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.playAudioFromButton(btn, audioUrl);
        });
        contentEl.appendChild(btn);
    }

    playAudioFromButton(btn, url) {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
            // Reset all buttons
            document.querySelectorAll('.play-audio-btn.playing').forEach(b => {
                b.classList.remove('playing');
                b.textContent = '🔊 播放';
            });
        }

        btn.classList.add('playing');
        btn.textContent = '⏸ 播放中...';

        this.currentAudio = new Audio(url);
        this.currentAudio.onended = () => {
            btn.classList.remove('playing');
            btn.textContent = '🔊 播放';
            this.currentAudio = null;
        };
        this.currentAudio.onerror = () => {
            btn.classList.remove('playing');
            btn.textContent = '🔊 播放';
            this.currentAudio = null;
        };
        this.currentAudio.play();
    }

    playAudio(url) {
        // Stop any currently playing audio
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }

        this.currentAudio = new Audio(url);
        this.currentAudio.onended = () => { this.currentAudio = null; };
        this.currentAudio.onerror = () => { this.currentAudio = null; };
        this.currentAudio.play().catch(() => {});
    }

    async playAudioSequence(urls) {
        for (const url of urls) {
            if (!url || this.autoSimRunning === false) break;
            await new Promise((resolve) => {
                this.currentAudio = new Audio(url);
                this.currentAudio.onended = () => {
                    this.currentAudio = null;
                    resolve();
                };
                this.currentAudio.onerror = () => {
                    this.currentAudio = null;
                    resolve();
                };
                this.currentAudio.play().catch(() => resolve());
            });
        }
    }

    stopAllAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        // Reset play buttons
        document.querySelectorAll('.play-audio-btn.playing').forEach(b => {
            b.classList.remove('playing');
            b.textContent = '🔊 播放';
        });
    }

    // ============ 自动语音仿真 ============

    async startAutoSimulation() {
        if (this.autoSimRunning) return;

        // 先开始对话
        if (!this.sessionId) {
            await this.newChat();
            if (!this.sessionId) return;
        }

        const persona = this.simPersonaSelect.value;
        const resistance = this.simResistanceSelect.value;
        const chatGroup = this.chatGroupSelect.value;
        const customerName = this.customerNameInput.value || 'Budi';

        this.autoSimRunning = true;
        this.autoSimBtn.textContent = '⏹ 停止仿真';
        this.autoSimBtn.classList.add('running');
        this.generateReplyBtn.disabled = true;
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        this.voiceToggle.disabled = true;
        this.isLoading = true;

        // 清屏
        this.chatArea.innerHTML = '';
        this.welcomeMessage.style.display = 'none';
        this.simStatus.classList.add('active');
        this.simStatusText.textContent = '⏳ 加载ASR模型...';

        // 连接SSE
        const params = new URLSearchParams({
            persona, resistance, chat_group: chatGroup,
            max_turns: 15, asr_model: 'tiny', customer_name: customerName,
        });
        const url = `/voice/simulate/stream?${params.toString()}`;

        this.autoSimEventSource = new EventSource(url);
        let turnCount = 0;

        this.autoSimEventSource.onmessage = async (event) => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'greeting') {
                    this.simStatusText.textContent = '🟢 对话进行中...';
                    const agentText = data.agent_text || data.agent_response;
                    const msgId = this.addMessage('agent', agentText);
                    if (data.agent_audio_url) {
                        this.addPlayButton(msgId, data.agent_audio_url);
                        await this.playAudio(data.agent_audio_url);
                    }
                } else if (data.type === 'turn') {
                    turnCount++;
                    this.simStatusText.textContent = `🟢 第 ${turnCount} 轮...`;

                    // 客户消息
                    if (data.customer_text) {
                        this.addMessage('customer', data.customer_text);
                    }
                    if (data.customer_audio_url) {
                        await this.playAudio(data.customer_audio_url);
                    }

                    // ASR状态
                    if (data.asr_text) {
                        const matchIcon = data.asr_exact_match ? '✅' : '⚠️';
                        const asrNote = document.createElement('div');
                        asrNote.className = 'message agent';
                        asrNote.style.opacity = '0.7';
                        asrNote.style.fontSize = '12px';
                        asrNote.innerHTML = `
                            <div class="message-content" style="background:#f0fdf4; max-width:85%;">
                                ${matchIcon} ASR: "${this.escapeHtml(data.asr_text)}"
                                ${data.asr_exact_match ? '' : ' (原文: "' + this.escapeHtml(data.customer_text) + '")'}
                                <span style="color:#94a3b8; margin-left:8px;">CER:${data.asr_cer.toFixed(3)}</span>
                            </div>
                        `;
                        this.chatArea.appendChild(asrNote);
                    }

                    // Agent回复
                    if (data.agent_text) {
                        const msgId = this.addMessage('agent', data.agent_text);
                        if (data.agent_audio_url) {
                            this.addPlayButton(msgId, data.agent_audio_url);
                            await this.playAudio(data.agent_audio_url);
                        }
                    }

                    if (data.is_finished) {
                        this.finishAutoSimulation(data);
                    }
                } else if (data.type === 'done') {
                    this.simStatusText.textContent = `✅ 完成: ${data.total_turns}轮, ASR匹配率: ${(data.asr_exact_match_rate*100).toFixed(0)}%`;
                } else if (data.type === 'error') {
                    this.simStatusText.textContent = '❌ 错误: ' + data.message;
                    this.autoSimRunning = false;
                }
            } catch (e) {
                console.error('SSE parse error:', e);
            }
        };

        this.autoSimEventSource.onerror = (event) => {
            console.log('SSE connection closed');
            this.autoSimEventSource.close();
            this.autoSimEventSource = null;
            this.finishAutoSimulation();
        };
    }

    finishAutoSimulation(reportData) {
        this.autoSimRunning = false;
        this.isLoading = false;
        this.autoSimBtn.textContent = '▶ 自动语音仿真';
        this.autoSimBtn.classList.remove('running');
        this.generateReplyBtn.disabled = false;
        this.voiceToggle.disabled = false;
        this.isFinished = true;
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;

        if (this.autoSimEventSource) {
            this.autoSimEventSource.close();
            this.autoSimEventSource = null;
        }

        if (reportData && reportData.conversation_ended !== undefined) {
            this.addResultBanner(
                reportData.final_state !== 'FAILED',
                reportData.committed_time
            );
        }

        if (this.simStatus) {
            setTimeout(() => {
                this.simStatus.classList.remove('active');
            }, 5000);
        }
    }

    stopAutoSimulation() {
        if (this.autoSimEventSource) {
            this.autoSimEventSource.close();
            this.autoSimEventSource = null;
        }
        this.autoSimRunning = false;
        this.isLoading = false;
        this.autoSimBtn.textContent = '▶ 自动语音仿真';
        this.autoSimBtn.classList.remove('running');
        this.generateReplyBtn.disabled = false;
        this.voiceToggle.disabled = false;
        this.simStatusText.textContent = '⏹ 已停止';
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    window.chatDemo = new ChatDemo();
});
