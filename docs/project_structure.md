# AI智能催收项目 - 完整结构

```
ai-telemarketing/
├── .git/                                      # Git版本控制
├── README.md                                  # 项目说明
│
├── docs/                                      # 文档目录
│   ├── TODO.md                                # 项目任务清单
│   ├── 业务背景.md                            # 业务背景说明
│   ├── 分析总结.md                            # 初步分析总结
│   ├── 智能语音话术开发指南.md               # 智能语音指南
│   ├── 完整话术库与对话模板.md                # 话术库与模板
│   ├── 所有对话完整记录.md                    # 246个对话记录
│   ├── h2_h1_s0_analysis.md                   # 环节分析
│   ├── ctm_analysis.md                        # CTM分析
│   ├── chatbot_test_report.md                 # 机器人测试报告
│   ├── final_effective_talk_script.md         # 最终有效话术
│   ├── project_structure.md                   # 本文档 - 项目结构
│   │
│   ├── requirements/                          # 需求文档
│   │   ├── README.md
│   │   ├── 00-项目概述.md
│   │   ├── 01-业务流程.md
│   │   ├── 02-功能需求.md
│   │   ├── 03-核心能力需求.md
│   │   ├── 04-场景特定需求.md
│   │   ├── 05-性能指标要求.md
│   │   ├── 06-催收策略需求.md
│   │   ├── 07-用户画像与标签体系.md
│   │   ├── 08-话术选择与动态调整需求.md
│   │   └── 09-催收效果评估与分析需求.md
│   │
│   └── design/                                # 设计文档
│       ├── README.md
│       └── 01-技术选型.md
│
└── experiments/                               # 实验目录
    ├── README.md
    ├── requirements.txt                       # Python依赖
    │
    ├── data/                                 # 数据目录
    │   ├── chat-sample/                       # 音频样本
    │   │   └── *.mp3 (287个音频文件)
    │   │
    │   ├── label-chat-sample.xlsx             # 标签文件（包含H2/H1/S0）
    │   ├── cases.csv                          # 案例数据
    │   │
    │   └── processed/                         # 处理后的数据
    │       ├── transcripts/                   # 转写结果
    │       │   └── *.json (287个转写文件)
    │       │
    │       ├── final_analysis.json            # 初步分析结果
    │       ├── all_287_analysis.json          # 完整分析结果
    │       ├── chat_group_analysis.json       # 环节分析结果
    │       ├── chatbot_test_results.json      # 机器人测试结果
    │       ├── comprehensive_analysis.json    # 综合分析
    │       ├── ctm_analysis.json              # CTM分析
    │       ├── test_diarization_result.json   # 测试结果
    │       └── all_dialogues_output.txt      # 对话输出
    │
    ├── scripts/                               # 核心脚本
    │   ├── transcribe.py                      # 语音转写
    │   └── analyze.py                         # 话术分析
    │
    ├── notebooks/                             # Jupyter笔记本
    │   └── 00-语音转写测试.ipynb
    │
    ├── docs/                                  # 实验文档
    │   ├── 01-数据说明.md
    │   ├── 02-分析方法.md
    │   ├── 03-状态发现.md
    │   ├── 04-话术分析.md
    │   ├── 05-实验总结.md
    │   ├── 实验结果总结.md
    │   └── 调研-本地语音转写方案.md
    │
    ├── collection_chatbot_v2.py              # 对话机器人（最新版）
    ├── collection_chatbot.py                # 对话机器人（旧版）
    ├── analyze_all_287.py                  # 287个音频分析
    ├── analyze_by_ctm.py                   # 按CTM分析
    ├── analyze_by_chat_group.py            # 按环节分析
    ├── check_new_labels.py                # 检查新标签
    ├── export_all_246.py                 # 导出246个对话
    ├── comprehensive_dialogue_analysis.py # 综合分析
    ├── check_full_labels.py              # 检查标签
    ├── check_labels.py                    # 检查标签
    ├── transcribe_all_remaining.py         # 批量转写
    ├── transcribe_more.py                # 批量转写（旧版）
    ├── final_analysis.py                  # 最终分析
    ├── test_transcribe.py                # 转写测试
    ├── simple_transcribe.py              # 简单转写
    ├── tiny_transcribe.py               # 轻量转写
    ├── test_diarization.py               # 说话人分离测试
    └── test_analyze.py                   # 分析测试
```

---

## 核心数据统计

### 音频数据
- **总音频数**: 287个
- **音频格式**: .mp3
- **语言**: 印尼语
- **时长**: 10-60秒

### 标签数据
- **标签文件**: `label-chat-sample.xlsx`
- **chat_group**: H2/H1/S0 (三个催收环节)
- **repay_type**: repay/extend/NaN (还款/延期/未还款)
- **reloan_flag**: 0 (复借标记)
- **seats_name**: CTM-040/CTM-077/CTM-039/CTM-014/CTM-070等

### 转写数据
- **转写文件**: 287个JSON
- **有效对话**: 246个（排除语音信箱）
- **成功对话**: 144个
- **失败对话**: 102个

---

## 项目成果

### 1. 数据处理阶段
- ✅ 287个音频全部转写完成
- ✅ 语音信箱自动检测过滤
- ✅ 说话人分离（Agent/Customer）

### 2. 分析阶段
- ✅ 按环节（H2/H1/S0）分析
- ✅ 按CTM坐席分析
- ✅ 成功/失败对话对比
- ✅ 高频话术提取
- ✅ 话术差异分析

### 3. 话术库阶段
- ✅ 建立按环节分类的话术库
- ✅ 整理对话模板
- ✅ 提取关键成功要素

### 4. 机器人阶段
- ✅ 实现状态对话机器人
- ✅ 7个状态完整流程
- ✅ 测试10个场景
- ✅ 70%成功率

---

## 核心发现

### 关键成功要素
1. **适当停顿** (...) - 最重要！
2. **多次确认** (Ya, ya, ya.)
3. **简洁开场** (Halo?)
4. **主动等待** (Saya tunggu ya.)
5. **礼貌结束** (Terima kasih.)

### 环节成功率
- **H2**: 73.0% (早期催收，成功率最高)
- **H1**: 38.9% (中期催收)
- **S0**: 37.9% (晚期催收，成功率最低)

---

## 文件快速索引

### 查找话术
- `docs/final_effective_talk_script.md` - 最终有效话术
- `docs/完整话术库与对话模板.md` - 话术库
- `docs/h2_h1_s0_analysis.md` - 环节话术分析

### 查找对话数据
- `experiments/data/processed/transcripts/` - 287个转写
- `docs/all_246_dialogues.md` - 246个有效对话

### 查看机器人测试
- `docs/chatbot_test_report.md` - 测试报告
- `experiments/collection_chatbot_v2.py` - 机器人代码

### 查看业务背景
- `docs/业务背景.md` - 业务背景
- `docs/requirements/` - 完整需求文档
