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
│   │   ├── chatbot.py            # 11状态对话机器人（TTS集成）
│   │   ├── simulator.py           # 7种客户类型模拟器（5级抗拒）
│   │   ├── evaluation.py          # 增强版评测框架
│   │   ├── translator.py          # 翻译引擎
│   │   ├── metrics.py             # 指标收集系统
│   │   ├── llm_fallback.py        # LLM Fallback架构
│   │   └── voice/                 # 语音处理子包
│   │       ├── __init__.py
│   │       ├── vad.py             # 语音活动检测（VAD）
│   │       ├── interruption.py    # 智能打断处理
│   │       └── tts.py             # TTS引擎抽象
│   ├── experiments/               # 实验和分析
│   │   ├── __init__.py            # 向后兼容 re-export core 模块
│   │   ├── README.md
│   │   ├── scripts/               # 数据处理脚本
│   │   │   ├── __init__.py
│   │   │   ├── transcribe.py      # 语音转写
│   │   │   ├── diarize.py         # 说话人分离
│   │   │   ├── analyze.py         # 分析脚本
│   │   │   └── extract_features.py # 特征提取
│   │   ├── analysis/              # 分析脚本归档
│   │   │   ├── analyze_all.py
│   │   │   ├── analyze_all_287.py
│   │   │   ├── analyze_by_chat_group.py
│   │   │   ├── analyze_by_ctm.py
│   │   │   └── ...
│   │   ├── training/              # 对抗训练脚本
│   │   │   ├── baseline_test.py
│   │   │   ├── enhanced_test.py
│   │   │   └── training_loop.py
│   │   ├── archive/               # 历史版本归档
│   │   │   ├── collection_chatbot.py        # v1
│   │   │   ├── collection_chatbot_v2.py     # v2
│   │   │   ├── real_customer_simulator.py   # v1
│   │   │   └── evaluation_framework.py      # v1
│   │   ├── notebooks/             # Jupyter Notebooks
│   │   ├── docs/                  # 实验文档
│   │   ├── check_labels.py        # 标签检查
│   │   ├── enhanced_customer_simulator.py
│   │   ├── user_profile.py
│   │   └── verify_short_term.py
│   ├── tests/                     # 测试文件
│   │   ├── __init__.py
│   │   ├── test_api.py
│   │   └── run_small_scale_test.py # 批量生产测试
│   └── static/                    # 前端静态文件
│       ├── index.html            # 对话Demo网页
│       └── app.js                # 前端交互逻辑
├── data/                          # 所有数据（Git忽略）
├── docs/                          # 项目文档
│   ├── requirements/             # 需求文档
│   ├── design/                   # 设计文档
│   ├── 业务背景.md
│   ├── 分析总结.md
│   └── ...
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
| simulator.py | 7种客户类型，5级抗拒程度，40+拒绝借口 |
| evaluation.py | 多维度评测框架，成功率统计 |
| translator.py | 翻译引擎（MarianMT 本地模型，支持印尼文-中文互译） |
| metrics.py | 监控指标收集系统 |
| llm_fallback.py | LLM Fallback 混合架构（v4） |
| voice/vad.py | 能量基础VAD，语音活动检测 |
| voice/interruption.py | 智能打断处理，播放控制 |
| voice/tts.py | TTS引擎抽象（Edge-TTS / Coqui-TTS 双引擎支持） |

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

### 阶段2: 能力增强 - 进行中
| 任务 | 状态 |
|------|------|
| FastAPI服务封装 | ✅ 完成 |
| 数据库设计与ORM实现 | ✅ 完成 |
| VAD语音活动检测 | ✅ 完成 |
| 智能打断处理 | ✅ 完成 |
| 翻译引擎抽象 | ✅ 完成 |
| 监控指标系统 | ✅ 完成 |
| LLM Fallback混合架构 | ✅ 完成 |
| 红黑对抗训练框架 | ✅ 完成 |
| 小范围生产测试框架 | ✅ 完成 |
| 接入真实ASR服务 | 🔄 进行中 |
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
| 语音合成 | Edge-TTS (优先) / Coqui-TTS (自建备用) | 印尼语语音合成 |
| 语音识别 | Faster-Whisper（规划中） | 印尼语语音识别 |
| 语音活动检测 | 能量基础VAD | 实时语音端点检测 |
| 翻译引擎 | MarianMT (本地模型) | 印尼文-中文互译 |
| 对话引擎 | 规则状态机 + LLM Fallback混合架构 | 对话管理与语义理解 |
| 前端 | 原生HTML/JavaScript | Demo页面开发 |

---

## 安全说明

- 所有敏感文档（对话记录、客户数据）已排除在Git之外
- .gitignore包含完整的安全规则
- 仅技术文档提交到仓库
