# 项目结构说明

## 项目概述
AI-Telemarketing - 面向印尼信贷场景的智能语音催收系统，基于AI技术实现自动化债务提醒与协商对话平台

---

## 目录结构

```
ai-telemarketing/
├── src/                           # 源代码
│   ├── api/                       # FastAPI后端服务
│   │   ├── __init__.py
│   │   ├── main.py               # API主入口 + 端点定义
│   │   ├── database.py           # SQLAlchemy模型和数据库连接
│   │   ├── schemas.py            # Pydantic请求/响应模型
│   │   └── README.md
│   ├── core/                      # 生产引擎（核心算法）
│   │   ├── __init__.py
│   │   ├── chatbot.py            # 12状态对话机器人（规则+ML混合意图识别+LLM Fallback）
│   │   ├── simple_classifier.py   # 轻量级朴素贝叶斯意图分类器
│   │   ├── simulator.py           # 7种客户类型模拟器（5级抗拒）
│   │   ├── evaluation.py          # 增强版评测框架
│   │   ├── translator.py          # 翻译引擎
│   │   ├── metrics.py             # 指标收集系统
│   │   ├── logger.py              # 统一日志系统（毫秒精度，文件+控制台双输出）
│   │   ├── llm_fallback.py        # LLM Fallback架构
│   │   └── voice/                 # 语音处理子包
│   │       ├── __init__.py
│   │       ├── vad.py             # 语音活动检测（VAD）
│   │       ├── asr.py             # Faster-Whisper ASR引擎（印尼语实时识别）
│   │       ├── tts.py             # TTS引擎抽象（Edge-TTS / Piper-TTS / Coqui-TTS 三引擎）
│   │       ├── audio_io.py        # 麦克风录音 + 扬声器播放
│   │       ├── interruption.py    # 智能打断处理
│   │       ├── conversation.py    # 全链路串联：麦克风→VAD→ASR→纠错→Chatbot→TTS→扬声器
│   │       └── customer_simulator.py  # 客户语音仿真器（TTS→VAD→ASR端到端闭环）
│   ├── experiments/               # 实验和Demo
│   │   ├── __init__.py
│   │   ├── README.md
│   │   ├── test_llm_fallback.py         # LLM Fallback 功能测试
│   │   ├── evaluate_llm_fallback.py     # LLM Fallback 对比评估
│   │   ├── train_classifier.py          # ML分类器训练
│   │   ├── demo_ml_classifier.py        # ML分类器使用示例
│   │   ├── voice_demo.py                # 语音对话 Demo
│   │   ├── voice_simulate_demo.py       # 语音仿真 Demo
│   │   ├── analysis/                    # 分析脚本 (18个)
│   │   │   ├── analyze_all.py
│   │   │   ├── extract_customer_behavior.py
│   │   │   └── ...
│   │   ├── archive/                     # 历史版本归档
│   │   │   ├── baseline_test.py
│   │   │   ├── enhanced_test.py
│   │   │   └── training_loop.py
│   │   └── notebooks/                   # Jupyter Notebooks
│   │   ├── docs/                  # 实验文档
│   │   ├── check_labels.py        # 标签检查
│   │   ├── enhanced_customer_simulator.py
│   │   ├── user_profile.py
│   │   └── verify_short_term.py
│   ├── tests/                     # 测试文件
│   │   ├── __init__.py
│   │   ├── test_api.py
│   │   ├── test_voice_mode.py         # 语音模式 (21个测试)
│   │   ├── test_regression.py         # 回归测试
│   │   ├── playback_test.py           # 回放测试
│   │   ├── robustness_test.py         # 鲁棒性测试 (119用例)
│   │   ├── test_simulator.py          # 模拟器测试
│   │   ├── test_voice_corner_cases.py # 语音边缘场景
│   │   ├── voice_simulation_test.py   # 语音仿真测试
│   │   ├── test_auto_mode_e2e.py      # 自动模式端到端
│   │   ├── offline_evaluation.py      # 离线评估
│   │   └── run_small_scale_test.py    # 批量生产测试
│   └── static/                    # 前端Web Demo
│       ├── index.html            # 两栏布局（左侧会话列表 + 右侧聊天面板）
│       └── app.js                # 前端逻辑（自动/手动模式、SSE流式、语音播放、双语翻译）
├── scripts/                       # 工具脚本
│   ├── batch_asr_transcribe.py    # 批量ASR转写
│   └── annotation/                # 标注工具（12个，已完成使命归档）
│       ├── annotation_tool.py     # 标注工具
│       ├── batch_annotate.py      # 批量标注
│       ├── prepare_gold_dataset.py # 准备黄金数据集
│       └── ...
├── data/                          # 所有数据（Git忽略）
├── docs/                          # 项目文档
│   ├── README.md                  # 文档总览
│   ├── ROADMAP.md                 # 开发路线图
│   ├── 业务背景.md                 # 业务背景
│   ├── DEPLOYMENT_GUIDE.md        # 部署指南
│   ├── requirements/              # 需求文档
│   ├── design/                    # 设计文档
│   ├── evaluation/                # 评估体系
│   ├── experiments/               # 实验报告
│   ├── annotation/                # 标注指南
│   └── archive/                   # 历史归档
├── init_db.py                     # 数据库初始化
├── start_demo.py                  # Demo启动脚本
├── requirements.txt               # 依赖列表
└── README.md                      # 项目说明
```

---

## 核心模块说明

### 1. API层 (src/api/)
**职责**: 提供REST接口，服务化对话功能

| 文件 | 说明 |
|------|------|
| main.py | API端点 + 应用初始化 |
| database.py | 数据库模型 (ChatSession, ChatTurn, ScriptLibrary 等) |
| schemas.py | 请求/响应数据结构 |

### 2. 核心引擎层 (src/core/)
**职责**: 对话机器人、客户模拟、语音处理、评测框架

| 文件 | 说明 |
|------|------|
| chatbot.py | 12状态对话状态机（含LLM_FALLBACK状态），TTS集成，变量替换 |
| simple_classifier.py | 轻量级朴素贝叶斯意图分类器（规则系统补充） |
| simulator.py | 7种客户类型，5级抗拒程度，40+拒绝借口 |
| evaluation.py | 多维度评测框架，成功率统计 |
| translator.py | 翻译引擎（MarianMT 本地模型，支持印尼文-英文互译） |
| metrics.py | 监控指标收集系统 |
| logger.py | 统一日志系统（毫秒精度，文件+控制台双输出） |
| llm_fallback.py | LLM Fallback 混合架构（v4） |
| voice/vad.py | 能量基础VAD，语音活动检测 |
| voice/asr.py | Faster-Whisper ASR引擎（印尼语实时语音识别） |
| voice/tts.py | TTS引擎抽象（Edge-TTS / Piper-TTS / Coqui-TTS 三引擎支持） |
| voice/audio_io.py | 麦克风录音 + 扬声器播放 |
| voice/interruption.py | 智能打断处理，播放控制 |
| voice/conversation.py | 全链路串联：麦克风→VAD→ASR→纠错→Chatbot→TTS→扬声器 |
| voice/customer_simulator.py | 客户语音仿真器（TTS→VAD→ASR端到端闭环） |

### 3. 实验层 (src/experiments/)
**职责**: 数据分析、对抗训练、历史版本归档

---

## 数据库设计

```
表结构:
1. ChatSession         # 会话记录
2. ChatTurn            # 对话回合
3. ScriptLibrary       # 话术库
4. TestScenario        # 测试场景
5. TestResult          # 测试结果
6. MetricLog           # 指标日志
```

---

## 已完成的里程碑

### 阶段1: MVP验证 - ✅ 全部完成
1. 完整对话状态机（12状态，包含LLM_FALLBACK）
2. Edge-TTS语音合成集成
3. 14个基础测试场景，85.7%成功率
4. 对话日志记录与存储
5. 7种客户类型模拟器

### 阶段2: 能力增强 - ✅ 已完成
| 任务 | 状态 |
|------|------|
| FastAPI服务封装 | ✅ 完成 |
| 数据库设计与ORM实现 | ✅ 完成 |
| VAD语音活动检测 | ✅ 完成 |
| 智能打断处理 | ✅ 完成 |
| 翻译引擎（MarianMT印尼文-英文互译） | ✅ 完成 |
| 监控指标系统 | ✅ 完成 |
| 统一日志系统（毫秒精度） | ✅ 完成 |
| LLM Fallback混合架构 | ✅ 完成 |
| 红黑对抗训练框架 | ✅ 完成 |
| 小范围生产测试框架 | ✅ 完成 |
| Faster-Whisper ASR服务接入（本地GPU加速） | ✅ 完成 |
| Piper-TTS本地语音合成引擎集成 | ✅ 完成 |
| 客户语音仿真器（TTS→VAD→ASR闭环） | ✅ 完成 |
| Web Demo UI重构（两栏布局 + 自动/手动模式） | ✅ 完成 |
| 坐席/客户语音分离（不同引擎+不同音色） | ✅ 完成 |
| 完善打断策略 | 🔄 进行中 |
| 小范围生产测试执行 | ⏳ 规划中 |

### 阶段3: 生产落地 - 规划中（按优先级）
| 优先级 | 任务 |
|--------|------|
| P0 | 接入SIP真实电话线路 |
| P1 | 对话流程可视化编排 |
| P1 | 数据分析仪表板 |
| P2 | 智能质检与合规检查 |
| P2 | 预测性外呼策略优化 |
| P3 | 大规模生产测试（10000通） |

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 初始化数据库
```bash
python init_db.py
```

### 3. 启动服务
```bash
python start_demo.py
```

### 4. 访问Demo
- 网页: http://localhost:8000/
- API文档: http://localhost:8000/docs

### 5. 运行评测
```bash
# 基础评测（14个 golden case）
python src/core/evaluation.py --num-tests 0

# 批量测试
python src/tests/run_small_scale_test.py 50
```

---

## 技术栈

| 技术领域 | 选型 | 说明 |
|---------|------|------|
| 后端框架 | FastAPI + Pydantic | REST API服务开发 |
| 数据库 | SQLite + SQLAlchemy | 数据存储与对象关系映射 |
| 语音合成 | Edge-TTS (优先) / Piper-TTS (本地离线) / Coqui-TTS (自建备用) | 印尼语语音合成 |
| 语音识别 | Faster-Whisper (本地GPU加速) | 印尼语实时语音识别 |
| 语音活动检测 | 能量基础VAD | 实时语音端点检测 |
| 翻译引擎 | MarianMT (Helsinki-NLP opus-mt-id-en 本地模型) | 印尼文-英文互译 |
| 对话引擎 | 规则状态机 + LLM Fallback混合架构 | 对话管理与语义理解 |
| 前端 | 原生HTML/JavaScript（SSE流式 + Web Audio API） | Web Demo页面开发 |

---

## 安全说明

- 所有敏感文档（对话记录、客户数据）已排除在Git之外
- .gitignore包含完整的安全规则
- 仅技术文档提交到仓库
