# 项目TODO列表

## experiments/scripts/transcribe.py

### 1. transcribe_audio() - 第18行
**状态**: ✅ 已完成  
**参考**: `tiny_transcribe.py`, `simple_transcribe.py`  
**描述**: 使用 faster-whisper 实现语音转写逻辑

### 2. diarize_speakers() - 第76行
**状态**: ✅ 已完成  
**技术选型**: whisperx (可选) + 启发式规则  
**描述**: 实现说话人分离（agent/customer）

### 3. merge_transcript_and_diarization() - 第146行
**状态**: ✅ 已完成  
**描述**: 合并转写结果和说话人分离结果

---

## experiments/scripts/analyze.py

### 4. load_dialogues() - 第18行
**状态**: ✅ 已完成  
**描述**: 合并 cases.csv 的元数据

### 5. analyze_utterance_effectiveness() - 第83行
**状态**: 待实现  
**描述**: 实现话术有效性分析逻辑

---

## 阶段目标

### 短期目标 (Phase 1)
- [x] 实现 `transcribe_audio()` 函数
- [x] 完成 exp/data/chat-sample/ 中所有语音文件的印尼语转写

### 中期目标 (Phase 2)
- [x] 实现说话人分离
- [x] 实现合并逻辑

### 长期目标 (Phase 3)
- [ ] 实现会话分析功能
- [ ] 实现话术有效性分析
