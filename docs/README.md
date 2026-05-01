# 📚 项目文档总览
本文档体系覆盖从业务需求、系统设计、核心模块、评估体系到实验报告的全流程内容。

---

## 📁 文档结构
```
docs/
├── README.md                    # 本文件，文档总览
├── requirements/                # 业务需求文档
│   ├── README.md                # 需求总览
│   ├── 00-项目概述.md           # 项目背景、目标、价值
│   ├── 01-业务流程.md           # 催收业务流程说明
│   ├── 02-功能需求.md           # 详细功能需求
│   ├── 03-核心能力需求.md       # 技术能力要求
│   ├── 04-场景特定需求.md       # 各场景详细需求
│   ├── 05-性能指标要求.md       # 性能与SLA要求
│   ├── 06-催收策略需求.md       # 不同阶段催收策略
│   ├── 07-用户画像与标签体系.md # 用户画像设计
│   ├── 08-话术选择与动态调整需求.md # 话术策略
│   └── 09-催收效果评估与分析需求.md # 效果评估要求
├── design/                      # 系统设计文档
│   ├── README.md                # 设计总览
│   └── 01-技术选型.md           # 技术选型与对比
├── evaluation/                  # 评估体系文档
│   ├── EVALUATION_FRAMEWORK.md  # 全链路评估方案总览
│   └── ...其他评估文档
├── experiments/                 # 数据分析与实验报告
│   ├── 01-数据说明.md           # 数据集说明
│   ├── 02-分析方法.md           # 分析方法介绍
│   ├── 03-状态发现.md           # 对话状态分析
│   ├── 04-话术分析.md           # 话术效果分析
│   ├── 05-实验总结.md           # 实验结论
│   ├── 实验结果总结.md          # 实验结果汇总
│   └── 调研-本地语音转写方案.md # 技术调研报告
├── LLM_FALLBACK_DESIGN.md       # LLM兜底架构详细设计
├── ROBUST_TRAINING.md           # 红黑对抗训练框架设计
├── USER_PROFILE_TEMPLATING.md   # 用户画像与话术模板设计
├── PROJECT_STRUCTURE.md         # 代码项目结构说明
├── ROADMAP.md                   # 发展路线图
├── 业务背景.md                  # 印尼催收业务背景介绍
└── 智能语音话术开发指南.md      # 话术开发规范
```

---

## 🔍 快速导航
### 新用户入门
1. 先看 [业务背景.md](业务背景.md) 了解印尼催收行业背景
2. 再看 [requirements/00-项目概述.md](requirements/00-项目概述.md) 了解项目目标
3. 然后看 [LLM_FALLBACK_DESIGN.md](LLM_FALLBACK_DESIGN.md) 了解核心架构设计

### 开发人员
1. 看 [PROJECT_STRUCTURE.md](project_structure.md) 了解代码结构
2. 看 [design/01-技术选型.md](design/01-技术选型.md) 了解技术栈
3. 看 [USER_PROFILE_TEMPLATING.md](USER_PROFILE_TEMPLATING.md) 了解话术系统设计

### 测试/评估人员
1. 看 [evaluation/EVALUATION_FRAMEWORK.md](evaluation/EVALUATION_FRAMEWORK.md) 了解评估体系
2. 看 [ROBUST_TRAINING.md](ROBUST_TRAINING.md) 了解对抗训练方法

### 业务人员
1. 看 [requirements/](requirements/) 了解业务需求
2. 看 [experiments/](experiments/) 了解数据分析结果
