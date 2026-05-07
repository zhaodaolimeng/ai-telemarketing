# 项目文档总览

---

## 文档结构

```
docs/
├── README.md                          # 本文件，文档总览
├── ROADMAP.md                         # 开发路线图与TODO总览
├── 业务背景.md                         # 印尼催收业务背景
├── DEPLOYMENT_GUIDE.md                # 部署与CI/CD指南
│
├── requirements/                      # 业务需求文档
│   ├── README.md                      # 需求总览
│   ├── 00-项目概述.md                  # 项目背景、目标、价值
│   ├── 01-业务流程.md                  # 催收业务流程说明
│   ├── 02-功能需求.md                  # 详细功能需求
│   ├── 03-核心能力需求.md              # 技术能力要求
│   ├── 04-场景特定需求.md              # 各场景详细需求
│   ├── 05-性能指标要求.md              # 性能与SLA要求
│   ├── 06-催收策略需求.md              # 不同阶段催收策略
│   ├── 07-用户画像与标签体系.md         # 用户画像设计
│   ├── 08-话术选择与动态调整需求.md     # 话术策略
│   └── 09-催收效果评估与分析需求.md     # 效果评估要求
│
├── design/                            # 系统设计文档
│   ├── README.md                      # 设计总览
│   ├── 01-技术选型.md                  # 技术选型与对比
│   ├── 02-project-structure.md        # 代码项目结构
│   ├── 03-llm-fallback.md             # LLM兜底混合架构设计
│   ├── 04-robust-training.md          # 红黑对抗训练框架设计
│   ├── 05-user-profile-templating.md  # 用户画像与话术模板设计
│   └── 06-intent-matrix.md            # 意图处理矩阵（19类意图规则）
│
├── evaluation/                        # 评估体系文档
│   ├── EVALUATION_FRAMEWORK.md        # 全链路评估方案总览
│   ├── BASELINE_TEST_20260503.md      # Baseline测试报告
│   ├── BULK_TEST_GUIDE.md             # 批量测试工具使用指南
│   ├── SIMULATOR_GUIDE.md             # 生成式客户模拟器使用指南
│   ├── TOOLS_GUIDE.md                 # 评估工具综合指南
│   └── ROBUSTNESS_TEST_CASES.md       # 鲁棒性测试用例库（120条）
│
├── experiments/                       # 数据分析与实验报告
│   ├── 01-数据说明.md                  # 数据集说明
│   ├── 02-分析方法.md                  # 分析方法介绍
│   ├── 03-状态发现.md                  # 对话状态分析
│   ├── 04-话术分析.md                  # 话术效果分析
│   ├── 05-实验总结.md                  # 实验结论
│   ├── 06-真实对话分析总结.md          # 77条真实对话分析
│   ├── 07-话术开发指南.md              # 话术开发规范
│   ├── 语音转写实验结果.md             # 语音转写实验结果
│   └── 语音转写方案调研.md             # 本地语音转写技术调研
│
├── annotation/                        # 标注指南
│   ├── annotation_guide.md           # 黄金数据集标注指南
│   └── annotation_checklist.md       # 标注快速参考Checklist
│
└── archive/                           # 历史归档
    └── short_term_completion_report.md  # MVP短期任务完成报告(2026-04)
```

---

## 快速导航

### 新用户入门
1. 先看 [业务背景.md](业务背景.md) 了解印尼催收行业背景
2. 再看 [requirements/00-项目概述.md](requirements/00-项目概述.md) 了解项目目标
3. 然后看 [design/03-llm-fallback.md](design/03-llm-fallback.md) 了解核心架构设计

### 开发人员
1. 看 [design/02-project-structure.md](design/02-project-structure.md) 了解代码结构
2. 看 [design/01-技术选型.md](design/01-技术选型.md) 了解技术栈
3. 看 [design/05-user-profile-templating.md](design/05-user-profile-templating.md) 了解话术系统设计
4. 看 [design/06-intent-matrix.md](design/06-intent-matrix.md) 了解意图处理规则

### 测试/评估人员
1. 看 [evaluation/EVALUATION_FRAMEWORK.md](evaluation/EVALUATION_FRAMEWORK.md) 了解评估体系
2. 看 [evaluation/TOOLS_GUIDE.md](evaluation/TOOLS_GUIDE.md) 了解评估工具
3. 看 [design/04-robust-training.md](design/04-robust-training.md) 了解对抗训练方法

### 标注人员
1. 看 [annotation/annotation_guide.md](annotation/annotation_guide.md) 了解标注规范
2. 看 [annotation/annotation_checklist.md](annotation/annotation_checklist.md) 快速参考

### 业务人员
1. 看 [requirements/](requirements/) 了解业务需求
2. 看 [ROADMAP.md](ROADMAP.md) 了解项目进展和计划
