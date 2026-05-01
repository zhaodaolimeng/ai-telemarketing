# 设计文档

## 目录

- [技术选型](01-技术选型.md) - 技术方案调研与选择

> 注: 系统架构、API设计等文档尚未编写（规划中）。当前系统设计参见:
> - [`docs/PROJECT_STRUCTURE.md`](/docs/PROJECT_STRUCTURE.md) - 项目结构与模块详细说明
> - [`docs/LLM_FALLBACK_DESIGN.md`](/docs/LLM_FALLBACK_DESIGN.md) - LLM Fallback混合架构设计
> - [`docs/ROBUST_TRAINING.md`](/docs/ROBUST_TRAINING.md) - 红黑对抗训练框架设计

## 核心技术选型
| 技术领域 | 选型 | 说明 |
|---------|------|------|
| **TTS** | Edge-TTS (优先) / Coqui TTS (自建备用) | 印尼语语音合成 |
| **ASR** | Faster-Whisper (规划中) | 印尼语语音识别 |
| **NLU** | 规则引擎 + LLM Fallback混合架构 | 自然语言理解与对话管理 |
| **后端框架** | Python + FastAPI | REST API服务 |
| **数据库** | SQLite + SQLAlchemy | 数据存储与ORM |
| **语音活动检测** | 能量基础VAD | 实时语音端点检测 |
| **翻译引擎** | MarianMT（本地模型） | 印尼文-中文互译 |
| **支持语言** | 印尼文 | 面向印尼信贷市场 |

## 架构发展路线
- **阶段1：MVP验证**（已完成）- 验证核心语音对话能力，12状态机实现，85%+成功率
- **阶段2：能力增强**（进行中）- 优化性能，LLM兜底架构，鲁棒性训练，ASR接入
- **阶段3：生产落地**（规划中）- 接入真实电话线路，大规模外呼，全功能完善
