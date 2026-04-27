# 智能催收对话系统 - 项目结构

## 项目概述
智能语音催收系统 - 基于AI的自动化债务提醒与协商对话平台

---

## 目录结构

```
ai-telemarketing/
├── api/                          # FastAPI后端服务
│   ├── __init__.py
│   ├── main.py                  # API主入口 + 端点定义
│   ├── database.py              # SQLAlchemy模型和数据库连接
│   ├── schemas.py               # Pydantic请求/响应模型
│   └── README.md
├── experiments/                  # 实验和核心算法
│   ├── README.md
│   ├── collection_chatbot_v3.py  # 对话机器人（状态机）
│   ├── real_customer_simulator_v2.py  # 客户模拟器
│   ├── evaluation_framework_v2.py  # 评估框架
│   ├── voice_activity_detection.py  # VAD语音活动检测
│   ├── interruption_handler.py  # 打断处理
│   ├── translator.py            # 翻译引擎抽象
│   ├── metrics.py               # 指标收集系统
│   ├── voice_activity_detection.py
│   └── [其他实验脚本]
├── static/                       # 前端静态文件
│   ├── index.html               # 对话Demo网页
│   └── app.js                   # 前端交互逻辑
├── tests/                        # 测试文件
│   ├── README.md
│   └── test_api.py
├── docs/                         # 项目文档（已提交）
│   ├── requirements/            # 需求文档
│   │   ├── 00-项目概述.md
│   │   ├── 01-业务流程.md
│   │   ├── 02-功能需求.md
│   │   ├── 03-核心能力需求.md
│   │   ├── 04-场景特定需求.md
│   │   ├── 05-性能指标要求.md
│   │   ├── 06-催收策略需求.md
│   │   ├── 07-用户画像与标签体系.md
│   │   ├── 08-话术选择与动态调整需求.md
│   │   ├── 09-催收效果评估与分析需求.md
│   │   └── README.md
│   ├── design/                  # 设计文档
│   │   ├── 01-技术选型.md
│   │   └── README.md
│   ├── project_structure.md      # 本文件
│   ├── short_term_completion_report.md  # 短期完成报告
│   ├── 业务背景.md
│   └── 分析总结.md
├── data/                         # 数据目录（Git忽略）
│   ├── tts_output/              # TTS生成的音频
│   ├── chatbot_tests/           # 对话测试结果
│   └── evaluations/             # 评估报告
├── experiments/data/             # 实验数据（Git忽略）
├── experiments/docs/             # 实验文档（Git忽略）
├── init_db.py                    # 数据库初始化脚本
├── start_demo.py                 # Demo启动脚本
├── run_small_scale_test.py        # 小范围生产测试脚本
├── test_api.py                   # API测试脚本（已移动到tests/）
├── requirements.txt               # 依赖列表
├── PROJECT_SUMMARY.md             # 项目总结
├── PROJECT_STRUCTURE.md          # 本文件
├── INSTALL_TRANSLATION.md        # 翻译安装指南
└── .gitignore                   # Git忽略规则
```

---

## 核心模块说明

### 1. API层 (api/)
**职责**: 提供REST接口，服务化对话功能

| 文件 | 说明 |
|------|------|
| main.py | API端点 + 应用初始化 |
| database.py | 数据库模型 (ChatSession, ChatTurn, ScriptLibrary, TestScenario, TestResult, MetricLog) |
| schemas.py | 请求/响应数据结构 |

### 2. 核心逻辑层 (experiments/)
**职责**: 对话机器人、客户模拟、评估框架

| 文件 | 说明 |
|------|------|
| collection_chatbot_v3.py | 11状态对话机器人，TTS集成，变量替换 |
| real_customer_simulator_v2.py | 7种客户类型，5级抗拒程度，40+拒绝话术 |
| evaluation_framework_v2.py | 多维度评估框架，成功率统计 |
| voice_activity_detection.py | 能量基础VAD，语音检测 |
| interruption_handler.py | 智能打断处理，播放控制 |
| translator.py | TTS引擎抽象，支持本地/在线翻译 |
| metrics.py | 监控指标收集系统 |

### 3. 前端层 (static/)
**职责**: Web界面演示，对话交互

| 文件 | 说明 |
|------|------|
| index.html | 聊天界面，响应式设计 |
| app.js | 前端交互，翻译集成，仿真模式 |

### 4. 测试层 (tests/)
**职责**: 单元测试、集成测试

---

## 数据库设计

```
表结构:
1. ChatSession         # 会话记录
   - session_id, chat_group, customer_name, is_finished, is_successful, commit_time
   
2. ChatTurn            # 对话回合
   - session_id, turn_number, agent_text, customer_text, timestamp
   
3. ScriptLibrary       # 话术库
   - category, chat_group, script_key, script_text, variables, is_active
   
4. TestScenario        # 测试场景
   - scenario_name, persona, chat_group, description
   
5. TestResult          # 测试结果
   - session_id, success, metrics, timestamp
   
6. MetricLog           # 指标日志
   - metric_name, metric_value, tags, timestamp
```

---

## 已完成的里程碑

### 短期 (1-2个月) - ✅ 完成
1. 完整对话状态机 (11状态)
2. Edge-TTS语音合成
3. 14个测试场景，92.9%成功率
4. 对话日志记录

### 中期 (2-4个月) - 基本完成
1. FastAPI服务封装 ✅
2. 数据库设计 ✅
3. VAD语音活动检测 ✅
4. 智能打断处理 ✅
5. 翻译引擎抽象 ✅
6. 管理后台API ✅
7. 监控指标 ✅
8. 小范围生产测试框架 ✅

### 待完成 (按优先级)
| P0 | T2.4 优化ASR延迟（流式） |
|----|----------------------------|
| P0 | T2.9 小范围生产测试执行 |
| P1 | T3.1 接入真实ASR服务 |
| P1 | T3.2 完善打断策略 |
| P2 | T3.3 对话流程可视化编排 |
| P2 | T3.4 数据分析仪表板 |
| P3 | T3.5 大规模生产测试（10000通） |

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt

# 本地翻译模型（推荐）
pip install transformers torch sentencepiece
```

### 2. 初始化数据库
```bash
python init_db.py
```

### 3. 启动服务
```bash
python start_demo.py
# 或
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 访问Demo
- 网页: http://localhost:8000/
- API文档: http://localhost:8000/docs

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Pydantic |
| 数据库 | SQLite + SQLAlchemy |
| 语音合成 | Edge-TTS (优先) / Coqui-TTS (自建) |
| 语音活动检测 | 能量基础VAD |
| 翻译 | MarianMT (本地) / Google/MyMemory (在线) |
| 前端 | 原生HTML/JS |

---

## 安全说明

- 所有敏感文档（对话记录、客户数据）已排除在Git之外
- .gitignore包含完整的安全规则
- 仅技术文档提交到仓库
