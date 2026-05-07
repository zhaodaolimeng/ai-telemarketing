# 设计文档

## 目录

- [技术选型](01-技术选型.md) - 技术方案调研与选择
- [项目结构](02-project-structure.md) - 代码项目结构与模块说明
- [LLM Fallback架构](03-llm-fallback.md) - 规则引擎+LLM混合兜底架构
- [红黑对抗训练](04-robust-training.md) - 鲁棒性训练框架设计
- [用户画像与话术模板](05-user-profile-templating.md) - 个性化话术系统设计
- [意图处理矩阵](06-intent-matrix.md) - 19类意图处理规则与状态流转

---

## 核心技术选型
| 技术领域 | 选型 | 说明 |
|---------|------|------|
| **TTS** | Edge-TTS (优先) / Coqui TTS (自建备用) | 印尼语语音合成 |
| **ASR** | Faster-Whisper (规划中) | 印尼语语音识别 |
| **NLU** | 规则引擎 + 朴素贝叶斯 + LLM Fallback三级混合架构 | 自然语言理解与对话管理 |
| **后端框架** | Python + FastAPI | REST API服务 |
| **数据库** | SQLite + SQLAlchemy | 数据存储与ORM |
| **语音活动检测** | 能量基础VAD | 实时语音端点检测 |
| **翻译引擎** | MarianMT（本地模型） | 印尼文-中文互译 |
| **机器学习** | scikit-learn (LogisticRegression + TF-IDF) | 轻量级意图分类 |
