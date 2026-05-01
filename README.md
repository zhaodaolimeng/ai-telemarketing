# AI-Telemarketing - 智能语音客服系统

## 项目简介
面向信贷催收场景的自动化语音外呼与智能对话系统。通过状态机驱动的规则引擎整合 TTS/VAD，实现自动化债务提醒与还款协商。

## 当前状态
- ✅ 需求文档完成
- ✅ 数据分析实验（77个转写，71个有效对话）
- ✅ 11状态对话机器人（TTS 集成，85.7% 成功率）
- ✅ FastAPI 服务封装 + 数据库设计
- ✅ 7种客户类型模拟器（5级抗拒，40+借口）
- ✅ VAD、打断处理、TTS 引擎抽象
- 🔄 LLM Fallback 架构
- ⏳ 真实 ASR 集成、生产电话接入

## 目录结构
```
ai-telemarketing/
├── src/                    # 源代码
│   ├── api/                # FastAPI 后端服务
│   │   ├── main.py         # 端点定义
│   │   ├── database.py     # ORM 模型
│   │   └── schemas.py      # Pydantic 模型
│   ├── core/               # 生产引擎
│   │   ├── chatbot.py      # 对话状态机
│   │   ├── simulator.py    # 客户模拟器
│   │   ├── evaluation.py   # 评测框架
│   │   ├── translator.py   # 翻译引擎
│   │   ├── metrics.py      # 指标收集
│   │   ├── llm_fallback.py # LLM 兜底
│   │   └── voice/          # 语音子模块
│   │       ├── vad.py      # 语音活动检测
│   │       ├── interruption.py # 打断处理
│   │       └── tts.py      # TTS 引擎
│   ├── experiments/        # 数据分析实验
│   │   ├── scripts/        # 数据处理脚本
│   │   ├── analysis/       # 分析脚本归档
│   │   ├── training/       # 对抗训练脚本
│   │   ├── archive/        # 历史版本归档
│   │   └── notebooks/      # Jupyter notebooks
│   ├── tests/              # 测试
│   │   ├── test_api.py
│   │   └── run_small_scale_test.py
│   └── static/             # 前端 Demo
├── data/                   # 数据（不进 git）
├── docs/                   # 项目文档
│   ├── requirements/       # 需求文档
│   └── design/             # 设计文档
├── start_demo.py           # Demo 启动
├── init_db.py              # 数据库初始化
└── requirements.txt        # Python 依赖
```

## 快速开始

### 安装与启动
```bash
pip install -r requirements.txt
python init_db.py
python start_demo.py
```
访问 http://localhost:8000/docs 查看 API 文档。

### 运行评测
```bash
# 14 场景基础评测
python src/core/evaluation.py --num-tests 0

# 批量生产测试
python src/tests/run_small_scale_test.py 50
```

## 文档导航
- [需求文档](docs/requirements/README.md)
- [设计文档](docs/design/README.md)
- [API 文档](http://localhost:8000/docs)（启动后访问）
- [实验项目](src/experiments/README.md)
