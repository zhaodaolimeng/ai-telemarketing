# 语音模式 (Voice Mode Demo)

## 概述

在现有"文本模式"和"自动模式"基础上，新增"语音模式"Demo。语音模式完全模拟真实打电话过程：测试者通过麦克风实时录入语音，经 ASR 转为文字后送入对话引擎，坐席回复以 TTS 语音播放，同时对话记录以文本形式实时呈现在聊天区域。

## 模式对比

| 维度 | 文本模式 (原"手动模式") | 语音模式 (新增) | 自动模式 |
|------|----------------------|----------------|---------|
| 客户输入 | 键盘打字 | 麦克风语音 | AI 自动生成 |
| 坐席输出 | 文字 (+ TTS 可选) | 文字 + TTS 语音 | 文字 (+ TTS 可选) |
| 对话节奏 | 手动控制 | 实时语音交互 | 自动连续 |
| 适用场景 | 调试对话逻辑 | 体验真实通话 | 批量仿真测试 |

## 架构设计

```
用户语音 (麦克风)
  → MediaRecorder 采集 (前端)
  → HTTP POST /voice/asr (音频分片)
  → ASR 引擎 (Whisper/Piper)
  → 转写文字
  → Chatbot.process(text)
  → 坐席回复文字
  → TTS 合成语音
  → 返回 { text, audio_url }
  → 前端: 渲染文字 + 自动播放语音
```

## 前端设计

### UI 布局

语音模式使用与文本模式相同的聊天区域布局。区别在于输入区域：

```
┌─────────────────────────────┐
│  [文本] [语音] [自动]  🔊   │  ← mode bar (三选一)
├─────────────────────────────┤
│  催收组别: [H2 ▼]           │  ← voice config
│  客户姓名: [Pak Budi    ]   │
│  [🎤 开始通话] / [📞 挂断]  │  ← 通话控制按钮
├─────────────────────────────┤
│  坐席: Selamat pagi...     │  ← chat area
│  客户 (语音转写): Pagi...  │
│  坐席: Apakah Bapak...    │
│  ...                       │
├─────────────────────────────┤
│  🎤 正在录音...  [挂断]     │  ← 录音状态栏
└─────────────────────────────┘
```

### 核心流程

1. **初始化**: 点击"开始通话" → POST `/voice/start` 获取坐席开场白 + TTS → 播放开场白语音 → 显示文字
2. **录音循环**: 
   - 按"开始说话"或自动 VAD 检测 → MediaRecorder 开始采集
   - 松开按钮 / VAD 检测到静音 → 停止采集 → 发送音频到后端
   - 后端 ASR 转写 → chatbot 处理 → TTS 合成
   - 前端收到回复 → 显示客户转写文字 + 坐席回复文字 → 自动播放坐席语音
3. **结束**: 点击"挂断"或对话自然结束 → 保存会话记录

### 关键组件

- **MediaRecorder API**: 浏览器原生录音，MIME type: `audio/webm;codecs=opus`
- **录音按钮**: 按住说话 / 点击切换（两种交互模式可选）
- **VAD 前端辅助**: 可选 - 使用 AudioContext 检测音量，自动判断说话结束
- **音频播放队列**: 复用现有 `pendingAudioQueue` 机制，确保坐席语音顺序播放

### 状态管理

```
voiceMode.state:
  IDLE          - 未连接
  CONNECTING    - 正在初始化通话
  LISTENING     - 等待用户说话
  RECORDING     - 正在录音
  PROCESSING    - ASR + Chatbot 处理中
  PLAYING       - 播放坐席 TTS
  FINISHED      - 通话结束
```

## 后端设计

### 新增 API

#### POST `/voice/asr`
上传音频分片，返回转写文字。

```
Request:
  - session_id: str
  - audio_data: bytes (webm/opus)
  
Response:
  - text: str (转写文字)
  - is_final: bool (是否为完整语句)
```

#### POST `/voice/turn/voice`
语音轮次 - 将转写文字送入 chatbot 并返回带 TTS 的回复。

```
Request:
  - session_id: str
  - customer_text: str (ASR 转写结果)
  
Response:
  - agent_text: str
  - audio_file: str (TTS 音频 URL)
  - state: str
  - is_finished: bool
  - conversation_log: [...]
```

实际上可以复用现有 `/voice/turn` 端点，前端只需将 ASR 结果作为 `customer_input` 传入。

### ASR 处理

复用现有 ASR 基础设施 (`VoiceSessionManager`)。关键模块：

- `src/core/voice/asr.py` - 现有 ASR 引擎（Whisper + VAD）
- 前端发送完整语音段（非流式分片），降低复杂度
- 后端对 webm/opus 格式解码后送入 ASR

## 实现步骤

### Step 1: 文本模式改名

- `index.html`: "手动模式" → "文本模式"，`data-mode="manual"` 保持不变
- `app.js`: 所有 `mode === 'manual'` 保持不变（内部标识不变）
- 欢迎文字更新

### Step 2: 语音模式 UI

- 新增 `data-mode="voice"` 标签页，排列在"文本模式"之后、"自动模式"之前
- 新增 `voiceConfig` 配置栏（与 `manualConfig` 结构相同）
- 新增通话控制按钮（开始通话 / 挂断）
- 新增录音状态栏

### Step 3: 语音模式前端逻辑

- `switchMode('voice')` - 切换时初始化语音模式
- `startVoiceCall()` - 初始化通话，获取坐席开场白
- `startRecording()` / `stopRecording()` - MediaRecorder 控制
- `processVoiceAudio(audioBlob)` - 发送音频 → 获取转写 → 发送 chatbot → 播放回复
- `endVoiceCall()` - 挂断，清理资源

### Step 4: 后端适配

- 确认 ASR 端点可处理前端 webm/opus 格式
- 如需要，添加 webm→wav 转码
- 或新增 `/voice/asr` 端点封装 ASR 处理

### Step 5: 集成测试

- 文本模式功能不受影响
- 自动模式功能不受影响
- 语音模式全链路：录音 → 转写 → 对话 → TTS 播放
