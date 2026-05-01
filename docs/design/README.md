# 设计文档

## 目录

- [技术选型](01-技术选型.md) - 技术方案调研与选择

> 注: 系统架构、API设计等文档尚未编写（规划中）。当前系统设计参见:
> - `docs/PROJECT_STRUCTURE.md` - 项目结构与模块说明
> - `docs/LLM_FALLBACK_DESIGN.md` - LLM Fallback 架构设计
> - `docs/ROBUST_TRAINING.md` - 红黑对抗训练框架设计

## 快速查看

### 核心技术选型
- **TTS**：Edge-TTS (优先) / Coqui TTS (自建备用)
- **ASR**：Faster-Whisper (规划中)
- **NLU**：规则引擎 + LLM Fallback
- **后端**：Python + FastAPI
- **数据库**：SQLite + SQLAlchemy
- **语言**：印尼文

### 架构路线
- **阶段1**：MVP，验证核心语音能力 (已完成)
- **阶段2**：优化，提升音质和准确率 (进行中)
- **阶段3**：扩展，多语种和能力增强 (规划中)
