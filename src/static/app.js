/**
 * 智能催收对话系统 - Web Demo
 * Two-column layout: session list (left) + chat panel (right)
 * Text mode: human types customer replies
 * Voice mode: human speaks via microphone, ASR + TTS
 * Auto mode: fully automatic simulation via SSE
 * Bilingual display: Indonesian + English translation
 */

class TelemarketingApp {
    constructor() {
        this.sessionId = null;
        this.mode = 'manual';
        this.isFinished = false;
        this.isLoading = false;

        this.autoSimRunning = false;
        this.eventSource = null;
        this.autoSimTurnCount = 0;

        this.currentAudio = null;
        this.pendingAudioQueue = [];
        this._processingQueue = false;
        this.turnBuffer = [];
        this.processingBuffer = false;
        this._pollingActive = false;
        this._playedUrls = new Set();
        this._greetingAudioReceived = false;
        this.translationCache = {};
        this.viewingSessionId = null;

        // Voice mode state
        this.voiceCallActive = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.voiceTimerInterval = null;
        this.voiceRecordingStart = null;
        this._voiceProcessing = false;

        this._localSessions = [];

        this._names = [
            'Pak Budi', 'Bu Siti', 'Pak Ahmad', 'Bu Dewi', 'Pak Rudi',
            'Bu Ratna', 'Pak Hendra', 'Bu Lina', 'Pak Agus', 'Bu Yanti',
            'Pak Dedi', 'Bu Fitri', 'Pak Andi', 'Bu Rina', 'Pak Tono',
            'Bu Wati', 'Pak Bambang', 'Bu Indah', 'Pak Eko', 'Bu Sri',
        ];

        this.init();
    }

    /* ========== Initialization ========== */

    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadSessionList();
    }

    cacheElements() {
        this.sessionList = document.getElementById('sessionList');
        this.refreshSessionsBtn = document.getElementById('refreshSessionsBtn');
        this.newSessionBtn = document.getElementById('newSessionBtn');
        this.panelPlaceholder = document.getElementById('panelPlaceholder');
        this.sessionPanel = document.getElementById('sessionPanel');
        this.activeEmpty = document.getElementById('activeEmpty');
        this.completedEmpty = document.getElementById('completedEmpty');

        this.manualModeTab = document.getElementById('manualModeTab');
        this.voiceModeTab = document.getElementById('voiceModeTab');
        this.autoModeTab = document.getElementById('autoModeTab');

        this.manualConfig = document.getElementById('manualConfig');
        this.voiceConfig = document.getElementById('voiceConfig');
        this.autoConfig = document.getElementById('autoConfig');

        this.chatGroup = document.getElementById('chatGroup');
        this.customerName = document.getElementById('customerName');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');

        // Voice mode elements
        this.voiceChatGroup = document.getElementById('voiceChatGroup');
        this.voiceCustomerName = document.getElementById('voiceCustomerName');
        this.startCallBtn = document.getElementById('startCallBtn');
        this.voiceStatus = document.getElementById('voiceStatus');
        this.voiceStatusText = document.getElementById('voiceStatusText');
        this.voiceRecDot = document.getElementById('voiceRecDot');
        this.voiceTimer = document.getElementById('voiceTimer');
        this.hangupBtn = document.getElementById('hangupBtn');
        this.voiceControls = document.getElementById('voiceControls');
        this.recordBtn = document.getElementById('recordBtn');
        this.recordBtnText = document.getElementById('recordBtnText');

        this.simPersona = document.getElementById('simPersona');
        this.simResistance = document.getElementById('simResistance');
        this.autoChatGroup = document.getElementById('autoChatGroup');
        this.autoCustomerName = document.getElementById('autoCustomerName');
        this.autoSimBtn = document.getElementById('autoSimBtn');

        this.modeBar = document.getElementById('modeBar');
        this.chatArea = document.getElementById('chatArea');
        this.welcomeMessage = document.getElementById('welcomeMessage');
        this.inputArea = document.getElementById('inputArea');
        this.simStatus = document.getElementById('simStatus');
        this.simStatusText = document.getElementById('simStatusText');
    }

    randomName() {
        const idx = Math.floor(Math.random() * this._names.length);
        return this._names[idx];
    }

    openNewSession() {
        // Reset state
        if (this.autoSimRunning) this.stopAutoSimulation();
        if (this.voiceCallActive) this.endVoiceCall();
        this.sessionId = null;
        this.isFinished = false;
        this.autoSimRunning = false;

        // Set random names
        this.customerName.value = this.randomName();
        this.autoCustomerName.value = this.randomName();
        this.voiceCustomerName.value = this.randomName();

        // Show session panel, hide placeholder
        this.panelPlaceholder.classList.add('hidden');
        this.sessionPanel.classList.remove('hidden');

        // Restore mode bar
        this.modeBar.classList.remove('hidden');

        // Reset to manual mode
        this.switchMode('manual');
        this.resetChat();

        // Disable input until chat starts
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        this.messageInput.placeholder = '请先点击「开始对话」...';

        // Pre-warm ASR in background
        this._warmupASR();
    }

    async _warmupASR() {
        try {
            await fetch('/voice/warmup', { method: 'POST' });
        } catch (e) { /* silent */ }
    }

    bindEvents() {
        this.newSessionBtn.addEventListener('click', () => this.openNewSession());

        this.manualModeTab.addEventListener('click', () => this.switchMode('manual'));
        this.voiceModeTab.addEventListener('click', () => this.switchMode('voice'));
        this.autoModeTab.addEventListener('click', () => this.switchMode('auto'));

        this.newChatBtn.addEventListener('click', () => this.startNewChat());
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Voice mode events
        this.startCallBtn.addEventListener('click', () => {
            if (this.voiceCallActive) {
                this.endVoiceCall();
            } else {
                this.startVoiceCall();
            }
        });
        this.hangupBtn.addEventListener('click', () => this.endVoiceCall());

        // Recording button: press-and-hold or toggle
        this.recordBtn.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            this.startRecording();
        });
        this.recordBtn.addEventListener('pointerup', (e) => {
            e.preventDefault();
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                this.stopRecording();
            }
        });
        this.recordBtn.addEventListener('pointerleave', (e) => {
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                this.stopRecording();
            }
        });

        this.autoSimBtn.addEventListener('click', () => {
            if (this.autoSimRunning) {
                this.stopAutoSimulation();
            } else {
                this.startAutoSimulation();
            }
        });

        this.refreshSessionsBtn.addEventListener('click', () => this.loadSessionList());
        setInterval(() => this.loadSessionList(), 10000);
    }

    /* ========== Mode Switching ========== */

    switchMode(mode) {
        if (this.autoSimRunning) this.stopAutoSimulation();
        if (this.voiceCallActive) this.endVoiceCall();
        this.stopAllAudio();

        this.mode = mode;
        this.manualModeTab.classList.toggle('active', mode === 'manual');
        this.voiceModeTab.classList.toggle('active', mode === 'voice');
        this.autoModeTab.classList.toggle('active', mode === 'auto');
        this.manualConfig.classList.toggle('hidden', mode !== 'manual');
        this.voiceConfig.classList.toggle('hidden', mode !== 'voice');
        this.autoConfig.classList.toggle('hidden', mode !== 'auto');
        this.voiceStatus.classList.toggle('hidden', mode !== 'voice');
        this.voiceControls.classList.toggle('hidden', mode !== 'voice');

        if (mode === 'auto') {
            this.inputArea.classList.add('hidden');
            this.resetChat();
            this._warmupASR();
        } else if (mode === 'voice') {
            this.inputArea.classList.add('hidden');
            this.resetChat();
            this._warmupASR();
            this.messageInput.disabled = true;
            this.sendBtn.disabled = true;
        } else {
            this.inputArea.classList.remove('hidden');
            if (!this.sessionId) {
                this.resetChat();
                this.messageInput.disabled = true;
                this.sendBtn.disabled = true;
                this.messageInput.placeholder = '请先点击「开始对话」...';
            }
        }
    }

    /* ========== Voice Mode ========== */

    async startVoiceCall() {
        if (this.isLoading || this.voiceCallActive) return;

        this.voiceCallActive = true;
        this.isLoading = true;
        this.startCallBtn.textContent = '⏹ 结束通话';
        this.startCallBtn.classList.add('running');
        this.resetChat();
        this.welcomeMessage.style.display = 'none';
        this.isFinished = false;
        this.sessionId = null;

        const group = this.voiceChatGroup.value;
        const name = this.voiceCustomerName.value.trim() || this.randomName();
        this.voiceCustomerName.value = this.randomName();

        try {
            const resp = await fetch('/voice/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_group: group, customer_name: name }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Failed to start voice call');
            }

            const data = await resp.json();
            this.sessionId = data.session_id;

            // Cache in sidebar
            this._localSessions.unshift({
                session_id: data.session_id,
                chat_group: group,
                customer_name: name,
                is_finished: false,
                is_successful: false,
                state: data.current_state || null,
                conversation_length: 1,
                start_time: new Date().toISOString(),
                end_time: null,
            });

            // Show agent greeting
            const audioUrl = data.audio_file || null;
            this.renderMessage('agent', data.agent_text, audioUrl);
            this.scrollToBottom();

            if (data.is_finished) {
                this.handleConversationEnd(data);
                this.endVoiceCall();
                return;
            }

            // Show recording controls and status
            this.voiceStatus.classList.remove('hidden');
            this.voiceControls.classList.remove('hidden');
            this.voiceStatusText.textContent = '按住按钮说话...';
            this.voiceTimer.textContent = '00:00';
            this.startCallBtn.classList.add('hidden');
            this.voiceConfig.classList.add('hidden');

            // Setup media recorder
            await this._setupMediaRecorder();

            this.loadSessionList();
        } catch (err) {
            alert('语音通话初始化失败: ' + err.message);
            this.endVoiceCall();
        } finally {
            this.isLoading = false;
        }
    }

    async _setupMediaRecorder() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('您的浏览器不支持麦克风访问。请使用 Chrome 或 Edge。');
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });

            // Check supported MIME types
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            this.mediaRecorder = new MediaRecorder(stream, { mimeType });
            this._voiceStream = stream;

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                if (this.audioChunks.length > 0) {
                    const audioBlob = new Blob(this.audioChunks, { type: mimeType });
                    this.audioChunks = [];
                    await this._processVoiceAudio(audioBlob);
                }
            };

            this.mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
                this.voiceStatusText.textContent = '录音出错，请重试';
                this._resetRecordButton();
            };
        } catch (err) {
            console.error('Microphone access denied:', err);
            alert('无法访问麦克风: ' + err.message);
        }
    }

    startRecording() {
        if (!this.mediaRecorder || this.mediaRecorder.state === 'recording') return;
        if (this._voiceProcessing) return;
        if (!this.sessionId || this.isFinished) return;

        this.audioChunks = [];
        this.mediaRecorder.start(250); // timeslice: collect data every 250ms
        this.voiceRecordingStart = Date.now();

        this.recordBtn.classList.add('recording');
        this.recordBtnText.textContent = '松开发送';
        this.voiceRecDot.classList.add('recording');
        this.voiceStatusText.textContent = '正在录音...';
        this._updateVoiceTimer();
        this.voiceTimerInterval = setInterval(() => this._updateVoiceTimer(), 200);
    }

    stopRecording() {
        if (!this.mediaRecorder || this.mediaRecorder.state !== 'recording') return;

        this.mediaRecorder.stop();
        this._resetRecordButton();

        if (this.voiceTimerInterval) {
            clearInterval(this.voiceTimerInterval);
            this.voiceTimerInterval = null;
        }
        this.voiceRecDot.classList.remove('recording');
    }

    _resetRecordButton() {
        this.recordBtn.classList.remove('recording');
        this.recordBtnText.textContent = '按住说话';
    }

    async _processVoiceAudio(audioBlob) {
        if (!this.sessionId || this.isFinished) return;
        if (this._voiceProcessing) return;

        this._voiceProcessing = true;
        this.voiceStatusText.textContent = '识别中...';

        try {
            // Step 1: Send audio for ASR
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            formData.append('session_id', this.sessionId);

            const asrResp = await fetch('/voice/asr', {
                method: 'POST',
                body: formData,
            });

            if (!asrResp.ok) {
                throw new Error('ASR failed: ' + asrResp.status);
            }

            const asrData = await asrResp.json();
            const customerText = asrData.text || '';

            if (!customerText || customerText.trim() === '') {
                this.voiceStatusText.textContent = '未识别到语音，请重试...';
                this._voiceProcessing = false;
                return;
            }

            // Show transcribed customer speech
            this.renderMessage('customer', customerText);
            this.voiceStatusText.textContent = '坐席回复中...';
            this.scrollToBottom();

            // Step 2: Process through chatbot
            const turnResp = await fetch('/voice/turn', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    customer_input: customerText,
                }),
            });

            if (!turnResp.ok) {
                const err = await turnResp.json();
                throw new Error(err.detail || 'Turn failed');
            }

            const turnData = await turnResp.json();

            // Render agent response
            const audioUrl = turnData.audio_file || null;
            this.renderMessage('agent', turnData.agent_text, audioUrl);
            this.scrollToBottom();

            if (turnData.is_finished) {
                this.handleConversationEnd(turnData);
                this.endVoiceCall();
                return;
            }

            this.voiceStatusText.textContent = '按住按钮说话...';
        } catch (err) {
            console.error('Voice processing error:', err);
            this.voiceStatusText.textContent = '处理出错: ' + err.message;
        } finally {
            this._voiceProcessing = false;
        }
    }

    async endVoiceCall() {
        // Mark session as finished on the server
        if (this.sessionId && !this.isFinished) {
            try {
                await fetch('/voice/end', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: this.sessionId }),
                });
            } catch (e) {
                console.warn('Failed to end voice session:', e);
            }
        }
        this.isFinished = true;

        // Update local session cache
        const local = this._localSessions.find(s => s.session_id === this.sessionId);
        if (local) {
            local.is_finished = true;
            local.end_time = new Date().toISOString();
        }

        this.voiceCallActive = false;

        // Stop media recorder
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        if (this.mediaRecorder) {
            this.mediaRecorder = null;
        }
        // Stop mic stream
        if (this._voiceStream) {
            this._voiceStream.getTracks().forEach(track => track.stop());
            this._voiceStream = null;
        }

        // Reset UI
        this.startCallBtn.textContent = '📞 开始通话';
        this.startCallBtn.classList.remove('running', 'hidden');
        this.startCallBtn.disabled = false;
        this.voiceConfig.classList.remove('hidden');
        this.voiceStatus.classList.add('hidden');
        this.voiceControls.classList.add('hidden');
        this.inputArea.classList.remove('hidden');
        this._resetRecordButton();

        if (this.voiceTimerInterval) {
            clearInterval(this.voiceTimerInterval);
            this.voiceTimerInterval = null;
        }
        this.voiceRecordingStart = null;
        this._voiceProcessing = false;
        this.audioChunks = [];

        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        this.messageInput.placeholder = '查看历史会话 (只读)';

        this.loadSessionList();
    }

    _updateVoiceTimer() {
        if (!this.voiceRecordingStart) return;
        const elapsed = Math.floor((Date.now() - this.voiceRecordingStart) / 1000);
        const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const secs = (elapsed % 60).toString().padStart(2, '0');
        this.voiceTimer.textContent = `${mins}:${secs}`;
    }

    /* ========== Session List ========== */

    async loadSessionList() {
        try {
            const resp = await fetch('/chat/sessions/active');
            if (!resp.ok) return;
            const data = await resp.json();

            // Clean up local sessions already on server
            const serverIds = new Set([
                ...data.active.map(s => s.session_id),
                ...data.completed.map(s => s.session_id),
            ]);
            this._localSessions = this._localSessions.filter(
                s => !serverIds.has(s.session_id)
            );

            this.renderSessionList(data);
        } catch (err) {
            console.error('Failed to load session list:', err);
        }
    }

    renderSessionList(data) {
        const { active, completed } = data;

        // Split active sessions into truly active vs finished
        const trulyActive = active.filter(s => !s.is_finished);
        const finishedActive = active.filter(s => s.is_finished);

        // Merge finished active into completed (dedup by session_id)
        const completedIds = new Set(completed.map(s => s.session_id));
        for (const s of finishedActive) {
            if (!completedIds.has(s.session_id)) {
                completed.unshift(s);
            }
        }

        const activeIds = new Set(trulyActive.map(s => s.session_id));
        const allCompletedIds = new Set(completed.map(s => s.session_id));

        // Inject local sessions not yet on server
        for (const local of this._localSessions) {
            if (!activeIds.has(local.session_id) && !allCompletedIds.has(local.session_id)) {
                if (local.is_finished) {
                    completed.unshift(local);
                } else {
                    trulyActive.unshift(local);
                }
            }
        }

        let html = '';

        // 进行中 section - always visible
        html += '<div class="session-section-title">进行中</div>';
        if (trulyActive.length > 0) {
            for (const s of trulyActive) {
                html += this.renderSessionCard(s, true);
            }
        } else {
            html += '<div class="empty-state" id="activeEmpty">暂无进行中的会话</div>';
        }

        // 已完成 section - always visible
        html += '<div class="session-section-title" style="margin-top:12px;">已完成</div>';
        if (completed.length > 0) {
            for (const s of completed) {
                html += this.renderSessionCard(s, false);
            }
        } else {
            html += '<div class="empty-state" id="completedEmpty">暂无已完成的会话</div>';
        }

        this.sessionList.innerHTML = html;

        this.sessionList.querySelectorAll('.session-card').forEach(card => {
            card.addEventListener('click', () => {
                this.viewSession(card.dataset.sessionId);
            });
        });

        this.sessionList.querySelectorAll('.card-delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showDeleteConfirm(btn, btn.dataset.deleteId);
            });
        });
    }

    renderSessionCard(s, isActive) {
        const shortId = s.session_id.substring(0, 8);
        const badgeClass = `badge-${s.chat_group.toLowerCase()}`;
        const dotClass = isActive ? 'active-dot' : (s.is_successful ? 'success-dot' : 'failed-dot');
        const activeClass = (s.session_id === this.sessionId) ? ' active' : '';
        const stateLabel = s.state ? this.formatState(s.state) : '';
        const endTimeStr = s.end_time ? new Date(s.end_time).toLocaleString('zh-CN', {
            month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        }) : '';

        return `
            <div class="session-card${activeClass}" data-session-id="${s.session_id}">
                <button class="card-delete-btn" data-delete-id="${s.session_id}" title="删除会话">×</button>
                <div class="card-top">
                    <span class="card-name">${this.escapeHtml(s.customer_name || 'Unknown')}</span>
                    <span class="card-badge ${badgeClass}">${s.chat_group}</span>
                </div>
                <div class="card-meta">
                    <span><span class="status-dot-sm ${dotClass}"></span>${shortId}</span>
                    <span>${s.conversation_length}轮</span>
                </div>
                ${stateLabel ? `<div class="card-state">状态: ${stateLabel}</div>` : ''}
                ${!isActive && endTimeStr ? `<div class="card-state">${endTimeStr}</div>` : ''}
            </div>`;
    }

    formatState(state) {
        const map = {
            'INIT': '初始化', 'GREETING': '问候', 'IDENTITY_VERIFY': '身份验证',
            'PURPOSE': '说明目的', 'ASK_TIME': '询问时间', 'PUSH_FOR_TIME': '推动承诺',
            'COMMIT_TIME': '确认时间', 'CONFIRM_EXTENSION': '协商延期',
            'HANDLE_OBJECTION': '处理异议', 'HANDLE_BUSY': '处理忙碌',
            'HANDLE_WRONG_NUMBER': '号码错误', 'CLOSE': '已关闭', 'FAILED': '失败'
        };
        return map[state] || state;
    }

    async viewSession(sessionId) {
        if (this.autoSimRunning) this.stopAutoSimulation();

        // Ensure session panel is visible
        this.panelPlaceholder.classList.add('hidden');
        this.sessionPanel.classList.remove('hidden');

        try {
            const resp = await fetch(`/chat/session/${sessionId}`);
            if (!resp.ok) {
                const errText = resp.status === 404 ? '会话不存在或已过期' : `加载失败 (${resp.status})`;
                this.chatArea.innerHTML = '';
                this.welcomeMessage.style.display = '';
                this.renderMessage('system', errText);
                return;
            }
            const data = await resp.json();

            this.chatArea.innerHTML = '';
            this.welcomeMessage.style.display = 'none';

            const isFinished = data.is_finished;

            // Banner
            const infoDiv = document.createElement('div');
            infoDiv.className = 'result-banner';
            infoDiv.style.background = isFinished ? (data.is_successful ? '#dcfce7' : '#fee2e2') : '#fef3c7';
            infoDiv.style.color = isFinished ? (data.is_successful ? '#166534' : '#991b1b') : '#92400e';
            infoDiv.textContent = (isFinished ? '已完成' : '进行中') +
                ` | ${data.customer_name || 'Unknown'} | ${data.chat_group} | ${data.conversation_length}轮`;
            this.chatArea.appendChild(infoDiv);

            // Render conversation
            for (const entry of data.conversation_log) {
                this.renderMessage(entry.role, entry.text, null, entry.timestamp);
            }

            this.scrollToBottom();

            // If session is active (not finished), reconnect for interaction
            if (!isFinished) {
                this.sessionId = sessionId;
                this.isFinished = false;
                this.viewingSessionId = null;
                this.modeBar.classList.remove('hidden');
                this.switchMode('manual');
                this.messageInput.disabled = false;
                this.sendBtn.disabled = false;
                this.messageInput.placeholder = '输入客户回复...';
                this.newChatBtn.textContent = '新对话';
                this.inputArea.classList.remove('hidden');
            } else {
                // Viewing completed session: hide mode/config, disable input
                this.sessionId = null;
                this.isFinished = true;
                this.modeBar.classList.add('hidden');
                this.manualConfig.classList.add('hidden');
                this.autoConfig.classList.add('hidden');
                this.messageInput.disabled = true;
                this.sendBtn.disabled = true;
                this.messageInput.placeholder = '查看历史会话 (只读)';
                this.newChatBtn.textContent = '新对话';
                this.inputArea.classList.remove('hidden');
            }
            this.loadSessionList();
        } catch (err) {
            console.error('Failed to load session:', err);
            this.renderMessage('system', '加载会话失败: ' + err.message);
        }
    }

    showDeleteConfirm(btn, sessionId) {
        // Remove any existing confirm popups
        this.dismissDeleteConfirm();

        const card = btn.closest('.session-card');
        const popup = document.createElement('div');
        popup.className = 'delete-confirm';
        popup.innerHTML = `
            <span>确认删除?</span>
            <button class="btn-confirm-yes">删除</button>
            <button class="btn-confirm-no">取消</button>
        `;
        card.appendChild(popup);
        this._deleteConfirmPopup = popup;
        this._deleteConfirmCard = card;

        popup.querySelector('.btn-confirm-yes').addEventListener('click', (e) => {
            e.stopPropagation();
            this.dismissDeleteConfirm();
            this.executeDelete(sessionId);
        });

        popup.querySelector('.btn-confirm-no').addEventListener('click', (e) => {
            e.stopPropagation();
            this.dismissDeleteConfirm();
        });

        // Dismiss on click outside
        const outsideHandler = (e) => {
            if (!popup.contains(e.target) && e.target !== btn) {
                this.dismissDeleteConfirm();
                document.removeEventListener('click', outsideHandler);
            }
        };
        setTimeout(() => document.addEventListener('click', outsideHandler), 0);
    }

    dismissDeleteConfirm() {
        if (this._deleteConfirmPopup) {
            this._deleteConfirmPopup.remove();
            this._deleteConfirmPopup = null;
        }
        if (this._deleteConfirmCard) {
            this._deleteConfirmCard = null;
        }
    }

    async executeDelete(sessionId) {
        try {
            const resp = await fetch(`/chat/session/${sessionId}`, { method: 'DELETE' });
            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || '删除失败');
            }

            this._localSessions = this._localSessions.filter(s => s.session_id !== sessionId);

            // If viewing this session, reset
            if (this.sessionId === sessionId || this.viewingSessionId === sessionId) {
                this.openNewSession();
            }

            this.loadSessionList();
        } catch (err) {
            alert('删除失败: ' + err.message);
        }
    }

    renderHistorySession(data) {
        this.chatArea.innerHTML = '';
        this.welcomeMessage.style.display = 'none';

        const infoDiv = document.createElement('div');
        infoDiv.className = 'result-banner ' + (data.is_successful ? 'success' : 'failed');
        const name = data.customer_name || 'Unknown';
        infoDiv.textContent = `查看历史会话 | ${name} | ${data.chat_group} | ${data.conversation_length}轮 | ${data.is_successful ? '成功' : '未成功'}`;
        this.chatArea.appendChild(infoDiv);

        for (const entry of data.conversation_log) {
            this.renderMessage(entry.role, entry.text, null, entry.timestamp);
        }

        this.scrollToBottom();
    }

    /* ========== Manual Mode: Chat ========== */

    resetChat() {
        this.chatArea.innerHTML = '';
        this.welcomeMessage.style.display = '';
        this.chatArea.appendChild(this.welcomeMessage);
        const banners = this.chatArea.querySelectorAll('.result-banner');
        banners.forEach(b => b.remove());
    }

    async startNewChat() {
        if (this.isLoading) return;

        this.isLoading = true;
        this.newChatBtn.disabled = true;
        this.resetChat();
        this.welcomeMessage.style.display = 'none';
        this.isFinished = false;

        const group = this.chatGroup.value;
        const name = this.customerName.value.trim() || this.randomName();
        this.customerName.value = this.randomName();
        const endpoint = this.voiceEnabled ? '/voice/start' : '/chat/start';

        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chat_group: group, customer_name: name }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Failed to start chat');
            }

            const data = await resp.json();
            this.sessionId = data.session_id;
            this.viewingSessionId = null;

            // Immediately cache and show in sidebar
            this._localSessions.unshift({
                session_id: data.session_id,
                chat_group: group,
                customer_name: name,
                is_finished: false,
                is_successful: false,
                state: data.current_state || null,
                conversation_length: data.conversation_length || 1,
                start_time: new Date().toISOString(),
                end_time: null,
            });

            this.messageInput.disabled = false;
            this.sendBtn.disabled = false;
            this.messageInput.placeholder = '输入客户回复...';
            this.messageInput.focus();

            const audioUrl = data.audio_file || null;
            this.renderMessage('agent', data.agent_response, audioUrl);

            if (data.is_finished) {
                this.handleConversationEnd(data);
            }

            this.loadSessionList();
        } catch (err) {
            alert('开始对话失败: ' + err.message);
        } finally {
            this.isLoading = false;
            this.newChatBtn.disabled = false;
        }
    }

    async sendMessage() {
        if (this.isLoading || !this.sessionId || this.isFinished) return;

        const text = this.messageInput.value.trim();
        if (!text) return;

        this.isLoading = true;
        this.sendBtn.disabled = true;
        this.messageInput.disabled = true;

        this.renderMessage('customer', text);
        this.messageInput.value = '';

        const loadingMsg = this.showLoading();
        const endpoint = this.voiceEnabled ? '/voice/turn' : '/chat/turn';

        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    customer_input: text,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Failed to process turn');
            }

            const data = await resp.json();
            this.removeElement(loadingMsg);

            const audioUrl = data.audio_file || null;
            this.renderMessage('agent', data.agent_response, audioUrl);

            if (data.is_finished) {
                this.handleConversationEnd(data);
            }
        } catch (err) {
            this.removeElement(loadingMsg);
            this.renderMessage('system', 'Error: ' + err.message);
        } finally {
            this.isLoading = false;
            this.sendBtn.disabled = false;
            this.messageInput.disabled = false;
            this.messageInput.focus();
        }
    }

    handleConversationEnd(data) {
        this.isFinished = true;
        this.messageInput.disabled = true;
        this.sendBtn.disabled = true;
        this.messageInput.placeholder = '对话已结束';

        // Update local session cache
        const local = this._localSessions.find(s => s.session_id === this.sessionId);
        if (local) {
            local.is_finished = true;
            local.is_successful = data.is_successful;
            local.end_time = new Date().toISOString();
        }

        const banner = document.createElement('div');
        banner.className = 'result-banner ' + (data.is_successful ? 'success' : 'failed');
        banner.textContent = data.is_successful
            ? `对话成功 - 承诺时间: ${data.commit_time || 'N/A'}`
            : '对话失败，未能达成还款约定';
        this.chatArea.appendChild(banner);
        this.scrollToBottom();

        this.loadSessionList();
    }

    /* ========== Auto Mode: Simulation ========== */

    async startAutoSimulation() {
        if (this.isLoading || this.autoSimRunning) return;

        this.autoSimRunning = true;
        this.autoSimTurnCount = 0;
        this.autoSimBtn.textContent = '⏹ 停止';
        this.autoSimBtn.classList.add('running');
        this.resetChat();
        this.welcomeMessage.style.display = 'none';
        this.isFinished = false;
        this.sessionId = null;

        const persona = this.simPersona.value;
        const resistance = this.simResistance.value;
        const group = this.autoChatGroup.value;
        const customerName = this.autoCustomerName.value.trim() || this.randomName();

        this.showSimStatus('正在启动自动仿真（加载ASR模型...）');

        const params = new URLSearchParams({
            persona,
            resistance,
            chat_group: group,
            max_turns: '15',
            asr_model: 'tiny',
            customer_name: customerName,
        });

        this.eventSource = new EventSource(`/voice/simulate/stream?${params}`);
        console.log('[SSE] Connecting to /voice/simulate/stream', { persona, resistance, group, customerName });

        this.eventSource.onopen = () => {
            console.log('[SSE] Connection opened');
            this.autoSimBtn.disabled = false;
            this.hideSimStatus();
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleSimEvent(data);
            } catch (e) {
                console.error('[SSE] Parse error:', e, event.data);
            }
        };

        this.eventSource.onerror = () => {
            const state = this.eventSource?.readyState;
            console.warn('[SSE] onerror fired, readyState=', state,
                '(0=CONNECTING, 1=OPEN, 2=CLOSED), _pendingDone=', !!this._pendingDone);

            // If 'done' was already received and audio is still playing,
            // immediately close the EventSource to cancel the browser's
            // auto-reconnect. (Server finished cleanly → browser fires onerror
            // with CONNECTING state → would reconnect without this.)
            if (this._pendingDone) {
                console.log('[SSE] Deferred done pending — closing to cancel reconnect');
                if (this.eventSource) {
                    this.eventSource.close();
                    this.eventSource = null;
                }
                return;
            }

            if (this.eventSource && state === EventSource.CLOSED) {
                console.warn('[SSE] Connection permanently closed');
                if (this.autoSimRunning) {
                    this.finishAutoSimulation(null);
                }
            }
        };
    }

    handleSimEvent(data) {
        this.hideSimStatus();

        switch (data.type) {
            case 'greeting':
                // Guard: if auto-simulation is already running with messages rendered,
                // this is an SSE reconnect — clear previous state to avoid duplicates
                if (this.autoSimRunning && this.sessionId && data.session_id !== this.sessionId) {
                    console.warn('[SSE] Duplicate greeting detected (reconnect?), old session=',
                        this.sessionId, 'new session=', data.session_id, '- resetting chat');
                    this.chatArea.innerHTML = '';
                    this.welcomeMessage.style.display = 'none';
                    this.turnBuffer = [];
                    this.pendingAudioQueue = [];
                    this.stopAllAudio();
                }

                this.autoSimTurnCount = 0;
                this.sessionId = data.session_id || null;
                this.turnBuffer = [];
                this.processingBuffer = false;
                this._playedUrls.clear();
                this._greetingAudioReceived = false;
                this._pollingActive = false;
                this._pendingDone = null;

                // Cache auto session in sidebar (dedup by session_id)
                if (data.session_id) {
                    this._localSessions = this._localSessions.filter(
                        s => s.session_id !== data.session_id
                    );
                    this._localSessions.unshift({
                        session_id: data.session_id,
                        chat_group: this.autoChatGroup.value,
                        customer_name: this.autoCustomerName.value.trim() || 'Test',
                        is_finished: false,
                        is_successful: false,
                        state: data.state || null,
                        conversation_length: 1,
                        start_time: new Date().toISOString(),
                        end_time: null,
                    });
                    this.loadSessionList();
                }

                this.renderMessage('agent', data.agent_text, null);
                console.log('[SSE] Greeting rendered, session_id=', data.session_id);
                break;

            case 'greeting_audio':
                if (this._greetingAudioReceived) break;
                this._greetingAudioReceived = true;
                if (data.agent_audio_url && this.voiceEnabled) {
                    this.pendingAudioQueue.push(data.agent_audio_url);
                    this.processAudioQueue();
                }
                // Start processing buffered turns after greeting audio
                if (this.voiceEnabled && this.turnBuffer.length > 0 && !this.processingBuffer) {
                    this._waitForAudioThenProcess();
                }
                break;

            case 'turn':
                this.autoSimTurnCount++;
                const autoLocal = this._localSessions.find(s => s.session_id === data.session_id);
                if (autoLocal) autoLocal.conversation_length = this.autoSimTurnCount + 1;

                if (this.voiceEnabled) {
                    // Buffer turns, display one at a time after audio playback
                    this.turnBuffer.push(data);
                    if (!this.processingBuffer) {
                        // Start processing immediately if idle, otherwise wait for audio
                        if (this.pendingAudioQueue.length === 0 && !this._processingQueue
                            && (!this.currentAudio || this.currentAudio.paused || this.currentAudio.ended)) {
                            this._processNextBufferedTurn();
                        } else {
                            this._waitForAudioThenProcess();
                        }
                    }
                } else {
                    // Without voice, render immediately
                    this._renderTurnMessages(data);
                }

                if (data.is_finished && !this.voiceEnabled) {
                    const finishedLocal = this._localSessions.find(s => s.session_id === data.session_id);
                    if (finishedLocal) {
                        finishedLocal.is_finished = true;
                        finishedLocal.is_successful = true;
                        finishedLocal.end_time = new Date().toISOString();
                    }
                    this.finishAutoSimulation(null);
                }
                break;

            case 'done':
                console.log('[SSE] Done event received, voiceEnabled=', this.voiceEnabled,
                    'turnBuffer.length=', this.turnBuffer.length,
                    'processingBuffer=', this.processingBuffer);
                // For voice mode, finish after all buffered turns are processed
                if (this.voiceEnabled && (this.turnBuffer.length > 0 || this.processingBuffer)) {
                    this._pendingDone = data;
                } else {
                    this.finishAutoSimulation(data);
                }
                break;

            case 'error':
                this.renderMessage('system', 'Error: ' + data.message);
                this.finishAutoSimulation(null);
                break;
        }
    }

    _renderTurnMessages(data) {
        this.renderMessage('customer', data.customer_text,
            this.voiceEnabled ? data.customer_audio_url : null,
            null, `Turn ${this.autoSimTurnCount}`);

        if (data.asr_text && !data.asr_exact_match) {
            this.renderMessage('system',
                `ASR: "${data.asr_text}" (CER: ${(data.asr_cer * 100).toFixed(1)}%)`);
        }

        this.renderMessage('agent', data.agent_text,
            this.voiceEnabled ? data.agent_audio_url : null);
    }

    async _processNextBufferedTurn() {
        if (this.processingBuffer) return;
        // Wait for any in-flight processAudioQueue (greeting audio) to finish
        if (this._processingQueue) {
            this._waitForAudioThenProcess();
            return;
        }
        this.processingBuffer = true;
        this._processingQueue = true;

        try {
            while (this.turnBuffer.length > 0) {
                const data = this.turnBuffer.shift();

                try {
                    // Render turn messages
                    this._renderTurnMessages(data);
                } catch (e) {
                    console.error('Error rendering turn:', e);
                }

                // Queue and drain audio sequentially before next turn
                if (data.customer_audio_url) {
                    this.pendingAudioQueue.push(data.customer_audio_url);
                }
                if (data.agent_audio_url) {
                    this.pendingAudioQueue.push(data.agent_audio_url);
                }

                while (this.pendingAudioQueue.length > 0) {
                    const url = this.pendingAudioQueue.shift();
                    try {
                        await this._playOne(url);
                    } catch (e) {
                        console.error('Audio play error:', e);
                    }
                }

                if (data.is_finished) {
                    const finishedLocal = this._localSessions.find(s => s.session_id === data.session_id);
                    if (finishedLocal) {
                        finishedLocal.is_finished = true;
                        finishedLocal.is_successful = true;
                        finishedLocal.end_time = new Date().toISOString();
                    }
                }
            }
        } finally {
            this._processingQueue = false;
            this.processingBuffer = false;
        }

        // Handle pending done event
        if (this._pendingDone) {
            const doneData = this._pendingDone;
            this._pendingDone = null;
            this.finishAutoSimulation(doneData);
        }
    }

    _waitForAudioThenProcess() {
        // Prevent duplicate polling loops
        if (this._pollingActive) return;
        this._pollingActive = true;
        const check = () => {
            const audioDone = this.pendingAudioQueue.length === 0
                && !this._processingQueue
                && (!this.currentAudio || this.currentAudio.paused || this.currentAudio.ended);
            if (audioDone) {
                this._pollingActive = false;
                this._processNextBufferedTurn();
            } else {
                setTimeout(check, 150);
            }
        };
        setTimeout(check, 100);
    }

    finishAutoSimulation(reportData) {
        console.log('[SSE] finishAutoSimulation called, reportData=', reportData);
        this.autoSimRunning = false;
        this.isFinished = true;

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.autoSimBtn.textContent = '▶ 开始自动对话';
        this.autoSimBtn.classList.remove('running');
        this.autoSimBtn.disabled = false;
        this.processingBuffer = false;
        this._pollingActive = false;
        this._greetingAudioReceived = false;
        this.stopAllAudio();
        this.pendingAudioQueue = [];
        this.turnBuffer = [];
        this._pendingDone = null;
        this._playedUrls.clear();
        this.hideSimStatus();

        // Hide mode/config bars — completed session should be read-only
        this.modeBar.classList.add('hidden');
        this.manualConfig.classList.add('hidden');
        this.autoConfig.classList.add('hidden');

        if (reportData) {
            this.showSimReport(reportData);
        }

        this.loadSessionList();
    }

    stopAutoSimulation() {
        this.showSimStatus('正在停止...');
        this.finishAutoSimulation(null);
    }

    showSimReport(data) {
        const isSuccess = data.final_state !== 'FAILED';
        const banner = document.createElement('div');
        banner.className = 'result-banner ' + (isSuccess ? 'success' : 'failed');

        let summary = `总轮数: ${data.total_turns || 'N/A'}`;
        if (data.asr_exact_match_rate !== undefined) {
            summary += ` | ASR匹配率: ${(data.asr_exact_match_rate * 100).toFixed(0)}%`;
        }
        if (data.avg_cer !== undefined) {
            summary += ` | 平均CER: ${(data.avg_cer * 100).toFixed(1)}%`;
        }
        if (data.avg_tts_time !== undefined) {
            summary += ` | TTS: ${data.avg_tts_time}s`;
        }
        if (data.avg_asr_time !== undefined) {
            summary += ` | ASR: ${data.avg_asr_time}s`;
        }
        banner.textContent = summary;
        this.chatArea.appendChild(banner);

        if (data.committed_time) {
            const commitDiv = document.createElement('div');
            commitDiv.className = 'sim-report';
            commitDiv.innerHTML = `<h3>承诺时间: ${data.committed_time}</h3>`;
            this.chatArea.appendChild(commitDiv);
        }

        this.scrollToBottom();
    }

    showSimStatus(text) {
        this.simStatus.classList.add('visible');
        this.simStatusText.textContent = text;
    }

    hideSimStatus() {
        this.simStatus.classList.remove('visible');
    }

    /* ========== Message Rendering ========== */

    renderMessage(role, text, audioUrl, timestamp, label) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const now = timestamp ? new Date(timestamp) : new Date();
        const timeStr = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper';

        if (label) {
            const labelDiv = document.createElement('div');
            labelDiv.className = 'message-label';
            labelDiv.textContent = label;
            wrapper.appendChild(labelDiv);
        }

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        const originalSpan = document.createElement('span');
        originalSpan.className = 'original-text';
        originalSpan.textContent = text;
        bubble.appendChild(originalSpan);

        const transSpan = document.createElement('span');
        transSpan.className = 'translation-text';
        bubble.appendChild(transSpan);

        wrapper.appendChild(bubble);

        if (audioUrl && role === 'agent') {
            const actions = document.createElement('div');
            actions.className = 'message-actions';

            const playBtn = document.createElement('button');
            playBtn.className = 'play-btn';
            playBtn.textContent = '🔊 播放';
            playBtn.dataset.audioUrl = audioUrl;
            playBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.playAudioFromButton(playBtn, audioUrl);
            });
            actions.appendChild(playBtn);
            wrapper.appendChild(actions);
        }

        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = timeStr;
        wrapper.appendChild(timeDiv);

        msgDiv.appendChild(wrapper);
        this.chatArea.appendChild(msgDiv);
        this.scrollToBottom();

        this.translateMessage(transSpan, text, role);

        // Voice mode: auto-play agent TTS, highlight play button if blocked
        if (audioUrl && role === 'agent' && this.mode === 'voice') {
            this._playOne(audioUrl).then((played) => {
                if (!played) {
                    // Autoplay blocked — pulse the play button to draw attention
                    const btn = msgDiv.querySelector('.play-btn');
                    if (btn) {
                        btn.textContent = '▶ 点击播放';
                        btn.style.animation = 'pulse-record 1.5s ease-in-out 3';
                    }
                }
            });
        }

        return msgDiv;
    }

    /* ========== Translation ========== */

    async translateMessage(transSpan, text, role) {
        // In auto mode, both agent and customer speak Indonesian → translate to English
        // In manual mode, agent speaks Indonesian (→EN), customer types English (→ID)
        const bothIndonesian = this.mode === 'auto';
        const source = (role === 'agent' || bothIndonesian) ? 'id' : 'en';
        const target = (role === 'agent' || bothIndonesian) ? 'en' : 'id';
        const cacheKey = `${text}|${source}|${target}`;

        if (this.translationCache[cacheKey]) {
            this.applyTranslation(transSpan, this.translationCache[cacheKey]);
            return;
        }

        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 8000);

            const resp = await fetch('/api/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, source, target }),
                signal: controller.signal,
            });
            clearTimeout(timeout);

            if (!resp.ok) return;

            const data = await resp.json();
            if (data.success && data.translated_text && data.translated_text !== text) {
                this.translationCache[cacheKey] = data.translated_text;
                this.applyTranslation(transSpan, data.translated_text);
            }
        } catch (err) {
            // Translation failed silently - non-critical
        }
    }

    applyTranslation(transSpan, translated) {
        transSpan.textContent = translated;
        transSpan.classList.add('visible');
    }

    /* ========== Audio Playback ========== */

    playAudioFromButton(btn, url) {
        if (this.currentAudio && !this.currentAudio.paused) {
            const playingUrl = this.currentAudio.src;
            if (playingUrl && playingUrl.includes(url)) {
                this.currentAudio.pause();
                btn.textContent = '🔊 播放';
                btn.classList.remove('playing');
                this.currentAudio = null;
                return;
            }
        }

        this.stopAllAudio();
        btn.textContent = '⏸ 播放中...';
        btn.classList.add('playing');
        this._playOne(url).then(() => {
            btn.textContent = '🔊 播放';
            btn.classList.remove('playing');
        });
    }

    _playOne(url) {
        // Skip if this URL was already played in this simulation
        if (this._playedUrls.has(url)) return Promise.resolve(false);
        this._playedUrls.add(url);

        return new Promise((resolve) => {
            if (this.currentAudio) {
                this.currentAudio.pause();
                this.currentAudio = null;
            }

            const audio = new Audio(url);
            this.currentAudio = audio;
            let resolved = false;

            audio.onended = () => {
                if (this.currentAudio === audio) this.currentAudio = null;
                if (!resolved) { resolved = true; resolve(true); }
            };

            audio.onerror = (e) => {
                console.warn('Audio playback error:', url, audio.error?.message || e);
                if (this.currentAudio === audio) this.currentAudio = null;
                if (!resolved) { resolved = true; resolve(false); }
            };

            audio.play().then(() => {
                // Playback started successfully
            }).catch((err) => {
                console.warn('Audio autoplay blocked:', url, err.message);
                if (this.currentAudio === audio) this.currentAudio = null;
                if (!resolved) { resolved = true; resolve(false); }
            });
        });
    }

    async processAudioQueue() {
        if (this._processingQueue) return;
        this._processingQueue = true;

        while (this.pendingAudioQueue.length > 0) {
            const url = this.pendingAudioQueue.shift();
            await this._playOne(url);
        }

        this._processingQueue = false;
    }

    stopAllAudio() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        this.pendingAudioQueue = [];
        this._processingQueue = false;

        this.chatArea.querySelectorAll('.play-btn.playing').forEach(btn => {
            btn.textContent = '🔊 播放';
            btn.classList.remove('playing');
        });
    }

    /* ========== Utilities ========== */

    showLoading() {
        const div = document.createElement('div');
        div.className = 'message agent';
        div.id = 'loading-' + Date.now();

        const wrapper = document.createElement('div');
        wrapper.className = 'message-wrapper';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        const indicator = document.createElement('div');
        indicator.className = 'loading-indicator';
        indicator.innerHTML = 'Agent is thinking <div class="loading-dots"><span></span><span></span><span></span></div>';
        bubble.appendChild(indicator);

        wrapper.appendChild(bubble);
        div.appendChild(wrapper);
        this.chatArea.appendChild(div);
        this.scrollToBottom();
        return div;
    }

    removeElement(el) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    scrollToBottom() {
        this.chatArea.scrollTop = this.chatArea.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/* ========== Bootstrap ========== */
document.addEventListener('DOMContentLoaded', () => {
    window.app = new TelemarketingApp();
});
