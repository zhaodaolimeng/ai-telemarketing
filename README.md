# AI-Telemarketing - 智能语音客服系统

## 项目简介
智能语音客服系统是一个面向信贷催收场景的自动化语音外呼与智能对话系统。

## 阶段规划

### Phase 0: 数据分析实验（当前）
在正式设计系统前，先通过真实数据分析回答：
- 真实催收对话有哪些核心状态？
- 哪些话术能有效促进回款？
- 成功的对话模式是什么？

详见: [experiments/README.md](experiments/README.md)

### Phase 1: 需求定义 ✅
梳理完整的需求文档，明确功能和性能指标。

详见: [docs/requirements/README.md](docs/requirements/README.md)

### Phase 2: 系统设计
基于实验发现和需求，进行系统设计。

### Phase 3: 核心实现
实现TTS/ASR/对话引擎等核心模块。

## 文档导航
- [需求文档](docs/requirements/README.md) - 项目需求
- [设计文档](docs/design/README.md) - 系统设计
- [API文档](docs/api/README.md) - API接口
- [实验项目](experiments/README.md) - 数据分析实验

## 当前状态
- ✅ 需求文档完成
- 🔄 数据分析实验框架搭建中
- ⏳ 系统设计待开始

## 目录结构
```
ai-telemarketing/
├── README.md
├── docs/
│   ├── requirements/   # 需求文档
│   ├── design/         # 设计文档
│   └── api/            # API文档
└── experiments/        # 数据分析实验
    ├── data/           # 数据目录
    ├── docs/           # 实验文档
    ├── notebooks/      # Jupyter notebooks
    ├── scripts/        # 分析脚本
    └── results/        # 分析结果
```

## 快速开始

### 数据分析实验
当有真实语音数据后：
```bash
cd experiments

# 1. 将数据放入 data/raw/
#    - 音频文件: data/raw/*.wav
#    - 案件数据: data/raw/cases.csv

# 2. 运行转写
python scripts/transcribe.py --input data/raw --output data/processed/transcripts

# 3. 运行分析
python scripts/analyze.py --data data/processed --output results

# 4. 查看 notebooks 进行交互式分析
jupyter notebook notebooks/
```
