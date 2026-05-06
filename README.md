# 🏦 AI-Telemarketing - 印尼智能语音催收系统

## 🎯 项目定位
面向印尼信贷市场的全阶段自动化语音催收系统，通过状态机驱动的规则引擎整合TTS/VAD/ASR等语音技术，结合LLM Fallback兜底架构，实现从M0（刚逾期）到M2+（逾期30天以上）的全流程自动化债务提醒、还款协商与客户服务。

## ✨ 核心价值
- **降本**：替代人工完成80%的重复性催收工作，人力成本降低60%
- **提效**：支持7x24小时不间断外呼，人均处理效率是人工的3-5倍
- **标准化**：话术和流程100%标准化，避免人为因素导致的合规风险和效果波动
- **数据闭环**：完整记录所有通话和对话数据，持续优化催收策略

## 🚀 当前进展
| 模块 | 状态 | 完成度 |
|------|------|--------|
| 需求分析与业务调研 | ✅ 完成 | 100% |
| 12状态核心对话机器人（含TTS集成） | ✅ 完成 | 100% |
| VAD语音活动检测与智能打断处理 | ✅ 完成 | 100% |
| LLM Fallback混合兜底架构 | ✅ 完成 | 100% |
| 用户画像与个性化话术模板引擎 | ✅ 完成 | 100% |
| 红黑对抗训练框架 | ✅ 完成 | 100% |
| 全链路评估体系 | ✅ 完成 | 100% |
| FastAPI后端服务与数据库设计 | ✅ 完成 | 100% |
| 真实ASR服务接入 | 🔄 进行中 | 70% |
| 生产电话线路对接 | ⏳ 规划中 | 0% |
| 前端管理后台 | ⏳ 规划中 | 0% |

## 🎯 核心能力
- **三阶段覆盖**：支持H2（M0，刚逾期）、H1（M1，逾期30天内）、S0（M2+，逾期30天以上）全业务场景
- **超低延迟**：端到端响应延迟≤300ms，接近真人对话体验
- **智能打断**：实时识别用户说话，支持中途打断，自然交互
- **个性化话术**：基于用户画像、逾期阶段、历史记录动态生成最优话术
- **合规安全**：所有话术100%符合印尼当地金融监管要求，全程录音可追溯
- **高鲁棒性**：通过红黑对抗训练，覆盖各种边界场景和对抗性行为

## 目录结构
```
ai-telemarketing/
├── src/                           # 源代码
│   ├── api/                       # FastAPI后端服务
│   │   ├── main.py               # API端点定义
│   │   ├── database.py           # ORM模型与数据库连接
│   │   ├── schemas.py            # Pydantic请求/响应模型
│   │   └── README.md
│   ├── core/                      # 核心生产引擎
│   │   ├── chatbot.py            # 12状态对话机器人（含规则+ML混合意图识别、LLM Fallback）
│   │   ├── simple_classifier.py   # 轻量级朴素贝叶斯意图分类器（规则系统补充）
│   │   ├── simulator.py           # 7种客户类型模拟器（5级抗拒）
│   │   ├── evaluation.py          # 多维度评测框架
│   │   ├── translator.py          # 印尼文-中文翻译引擎
│   │   ├── metrics.py             # 监控指标收集系统
│   │   ├── llm_fallback.py        # LLM兜底混合架构
│   │   └── voice/                 # 语音处理子模块
│   │       ├── vad.py             # 语音活动检测（VAD）
│   │       ├── interruption.py    # 智能打断处理
│   │       └── tts.py             # TTS引擎抽象（Edge-TTS/Coqui-TTS）
│   ├── experiments/               # 数据分析与实验
│   │   ├── train_classifier.py   # ML分类器训练脚本
│   │   ├── example_ml_usage.py   # ML功能使用示例
│   │   ├── scripts/               # 数据处理脚本
│   │   ├── analysis/              # 分析脚本归档
│   │   ├── training/               # 红黑对抗训练脚本
│   │   ├── archive/                # 历史版本归档
│   │   ├── notebooks/             # Jupyter分析笔记
│   │   └── README.md
│   ├── tests/                     # 自动化测试
│   │   ├── test_api.py
│   │   ├── test_intent_accuracy.py # 意图识别准确率测试
│   │   ├── test_full_demo.py      # 完整对话流程Demo测试
│   │   ├── test_demo_functionality.py # Demo功能测试
│   │   └── run_small_scale_test.py # 批量生产测试
│   └── static/                    # 前端Demo页面
├── scripts/                       # 工具脚本（标注、数据处理）
│   ├── annotation_tool.py         # 标注工具
│   ├── batch_annotate.py          # 批量标注脚本
│   ├── quick_annotate.py          # 快速标注脚本
│   ├── annotation_helper.py       # 标注辅助工具
│   ├── extract_unknown_for_annotation.py # 提取unknown意图用于标注
│   ├── fix_annotation_issues.py   # 修复标注问题
│   ├── prepare_gold_dataset.py    # 准备黄金数据集
│   └── ci_playback_test.py        # CI回放测试
├── data/                          # 数据文件（Git忽略，包含录音、转写等）
├── docs/                          # 项目文档
│   ├── requirements/              # 需求文档
│   ├── design/                     # 设计文档
│   ├── evaluation/                 # 评估体系与测试报告
│   ├── PROJECT_STRUCTURE.md       # 项目结构详细说明
│   ├── LLM_FALLBACK_DESIGN.md     # LLM兜底架构设计
│   ├── ROBUST_TRAINING.md         # 红黑对抗训练框架
│   └── 业务背景.md                 # 业务背景资料
├── start_demo.py                  # Demo启动脚本
├── init_db.py                     # 数据库初始化脚本
├── requirements.txt               # Python基础依赖列表
└── requirements_ml.txt            # ML扩展依赖列表
```

## 技术栈
| 技术领域 | 选型 |
|---------|------|
| 后端框架 | FastAPI + Pydantic |
| 数据库 | SQLite + SQLAlchemy |
| 语音合成 | Edge-TTS（优先）/ Coqui-TTS（自建备用） |
| 语音识别 | Faster-Whisper（规划中） |
| 自然语言理解 | 规则引擎 + 朴素贝叶斯ML分类器 + LLM Fallback三级混合架构 |
| 机器学习 | scikit-learn（轻量级意图分类） |
| 语音活动检测 | 能量基础VAD |
| 翻译引擎 | MarianMT（本地模型） |
| 前端 | 原生HTML/JavaScript |

## 🚀 快速开始

### CI/CD 状态
[![CI/CD Pipeline](https://github.com/your-username/ai-telemarketing/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/your-username/ai-telemarketing/actions/workflows/ci-cd.yml)

### 本地开发启动
```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装ML分类器可选依赖（启用意图分类增强）
pip install -r requirements_ml.txt

# 初始化数据库
python init_db.py

# 训练ML意图分类器（可选，需要黄金数据集已包含预训练模型）
python src/experiments/train_classifier.py

# 启动Demo服务
python start_demo.py
```
- 访问Demo页面: http://localhost:8000/
- 访问API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### Docker部署
```bash
# 直接启动
docker-compose up -d

# 或者手动构建
docker build -t ai-telemarketing-api .
docker run -d -p 8000:8000 ai-telemarketing-api
```

### 运行评测
```bash
# 意图识别准确率测试
python src/tests/test_intent_accuracy.py          # 纯规则系统测试
python src/tests/test_intent_accuracy.py --use-ml  # 规则+ML混合系统测试

# 14个基础场景评测（golden case）- 使用默认规则模拟器
python src/core/evaluation.py --num-tests 0

# 使用数据驱动生成式模拟器进行评测（基于真实对话语料）
python src/core/evaluation.py --num-tests 0 --use-generative

# 真实对话回放测试 - 基于标注的真实对话数据进行多维度评估
python src/core/evaluation.py --playback

# 运行单个指定ID的回放测试用例
python src/core/evaluation.py --case-id <case_id>

# 批量生产测试（50次随机场景）
python src/tests/run_small_scale_test.py 50

# 完整对话流程Demo测试
python src/tests/test_full_demo.py

# 运行单元测试
python src/tests/test_simulator.py
```

## 发展路线
### 阶段1: MVP验证（已完成）
- ✅ 核心12状态对话状态机
- ✅ Edge-TTS语音合成集成
- ✅ 14个测试场景，85.7%成功率
- ✅ 对话日志记录与存储

### 阶段2: 能力增强（进行中）
- ✅ FastAPI服务封装
- ✅ 数据库设计与ORM实现
- ✅ VAD语音活动检测
- ✅ 智能打断处理
- ✅ 翻译引擎抽象
- ✅ LLM Fallback混合架构
- ✅ 红黑对抗训练框架
- ✅ 规则+ML混合意图识别架构（准确率提升~25%）
- ✅ 意图识别准确率优化（纯规则50.8% → 混合系统~77%）
- ✅ 机器人重复回复问题修复（多版本话术+去重逻辑）
- ✅ 印尼语ASR错误纠正优化（全字匹配替换，避免误改业务词汇）
- 🔄 真实ASR服务接入
- 🔄 小范围生产测试
- 🔄 打断策略优化

### 阶段3: 生产落地（规划中）
- 接入SIP电话线路
- 对话流程可视化编排
- 数据分析仪表板
- 智能质检与合规检查
- 预测性外呼策略
- 大规模生产测试（10000通）

## 文档导航
- [需求文档](docs/requirements/README.md) - 完整业务需求说明
- [设计文档](docs/design/README.md) - 系统设计与技术选型
- [项目结构说明](docs/project_structure.md) - 详细目录结构与模块说明
- [LLM Fallback架构设计](docs/LLM_FALLBACK_DESIGN.md) - 混合对话架构设计
- [红黑对抗训练框架](docs/ROBUST_TRAINING.md) - 鲁棒性训练体系
- [用户画像与话术模板](docs/USER_PROFILE_TEMPLATING.md) - 个性化话术系统设计
- [实验文档](docs/experiments/) - 数据分析与实验报告（7份）
- [API文档](http://localhost:8000/docs)（启动服务后访问）

---

## 📜 项目核心规范
### 🔴 1. 合规红线规范（最高优先级，催收行业生命线）
**适用场景**：所有话术、对话逻辑、系统对外输出
**核心要求：**
- 严禁任何威胁、辱骂、误导、泄露用户隐私的内容
- 所有话术必须符合印尼金融服务管理局（OJK）催收规范
- 对外输出必须经过业务+合规双重审核才能上线
- 内置敏感词过滤机制，所有TTS输出必须先校验
- 禁止承诺任何不符合公司政策的内容（未经审批的减免、豁免等）

### 🔒 2. 数据安全规范（合规要求，违反有法律风险）
**适用场景**：所有用户数据、业务数据处理
**核心要求：**
- 用户个人信息（姓名、电话、欠款信息等）属于敏感数据，严禁泄露
- Git仓库严禁提交任何真实用户数据、业务数据、配置密钥
- 测试数据必须脱敏，不能使用真实用户的姓名、电话等信息
- 通话录音加密存储，仅限授权人员查看，严禁私自下载传播
- 敏感配置全部走环境变量，禁止硬编码到代码中

### 🧑‍💻 3. 开发提交规范
**适用场景**：所有代码提交、版本迭代
**核心要求：**
- Git提交信息格式：`类型: 具体内容`，比如`feat: 新增生成式客户模拟器` / `fix: 修复打断延迟问题`
- 功能提交必须附带测试报告，未通过测试的代码不能合入主分支
- 核心逻辑修改必须说明影响范围和测试覆盖情况
- 生产环境修改必须先在测试环境验证通过，禁止直接改生产代码
- **单元测试要求**：
  - 小变更（bug修复、小功能优化）：必须补充对应的单元测试，确保新增/修改代码有测试覆盖
  - 大变更（核心逻辑重构、架构调整、新增功能模块）：必须先补充完整的单元测试，再提交代码评审
  - 新增代码测试覆盖率不低于80%，核心逻辑必须100%覆盖

### 🧪 4. 测试发布规范（上线质量保障）
**适用场景**：所有功能上线前测试
**核心要求：**
- 上线必须同时通过三类测试：
  1. 黄金对话用例回放测试：100%通过，核心流程无错误
  2. 鲁棒性边界测试：≥95%通过，高风险场景无错误
  3. 语音链路专项测试：ASR准确率≥90%，端到端延迟≤300ms
- 重大功能上线必须做离线效果评估，预测回款率不低于人工80%才能上线
- 上线前必须准备回滚预案，出现问题可立刻切回旧版本
- **回归测试要求**：
  - 大变更（核心逻辑重构、架构调整、版本发布）必须执行全量回归测试
  - 回归测试范围包含：所有单元测试、黄金用例回放测试、鲁棒性测试、语音链路测试
  - 回归测试不通过不得上线，必须修复所有失败用例后重新执行全量回归

### 📝 5. 文档更新规范
> **核心规则：所有与@Meng Li讨论后明确的结论、决策、需求、方案，必须第一时间同步更新到对应的文档中。**
- **内容对应关系：**
  | 内容类型 | 记录位置 |
  |----------|----------|
  | 项目路线、整体规划、任务拆解 | `docs/ROADMAP.md` |
  | 业务需求、催收策略、场景说明 | `docs/requirements/`目录 |
  | 系统架构、技术选型、模块设计 | `docs/design/`目录 |
  | 评估方案、测试用例、效果指标 | `docs/evaluation/`目录 |
  | 实验分析、数据报告、调研结果 | `docs/experiments/`目录 |
- **更新要求：** 讨论结论24小时内同步，保持文档结构一致，重大变更保留Git追溯历史

---

### 🚧 后续待完善规范（上线前逐步补充）
- 语音交互规范：TTS/ASR/打断等语音相关体验标准
- 话术管理规范：话术模板、A/B测试、上线流程标准
- 上线灰度规范：阶梯放量、指标观察、回滚流程标准
- 效果迭代规范：数据驱动优化、bad case闭环流程标准
