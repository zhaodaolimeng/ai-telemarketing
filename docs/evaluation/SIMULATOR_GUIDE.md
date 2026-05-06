# 生成式客户模拟器使用指南

## 概述
生成式客户模拟器是基于真实催收对话数据训练的数据驱动模拟器，能够生成更符合真实场景的用户回复，解决了传统规则模拟器回复模式固定、不够真实的问题。

## 特点
- ✅ **数据驱动**：基于829条真实对话转写提取的4500+条用户回复，去重后3800条有效语料，覆盖更多真实场景
- ✅ **参数化配置**：支持7种用户类型、5种抗拒程度、3个催收阶段的组合配置
- ✅ **符合真实场景**：回复包含真实的ASR识别错误、口语化表达、各种抗拒模式
- ✅ **可插拔设计**：实现了统一的SimulatorInterface接口，可直接插入评估框架使用
- ✅ **向后兼容**：评估框架同时支持规则模拟器和生成式模拟器

## 使用方法

### 在评估框架中使用
只需在运行evaluation.py时添加`--use-generative`参数即可使用生成式模拟器：

```bash
# 使用生成式模拟器运行全部测试用例
python src/core/evaluation.py --use-generative

# 使用生成式模拟器仅运行Golden测试用例
python src/core/evaluation.py --use-generative --num-tests 0
```

### 独立使用
你也可以在代码中直接使用生成式模拟器：

```python
from core.simulator import GenerativeCustomerSimulator

# 初始化模拟器
simulator = GenerativeCustomerSimulator()

# 生成用户回复
response = simulator.generate_response(
    stage="ask_time",               # 当前对话阶段
    chat_group="H1",                # 催收阶段：H2(刚逾期)/H1(逾期30天内)/S0(逾期30天以上)
    persona="resistant",            # 用户类型：cooperative/busy/negotiating/silent/forgetful/resistant/excuse_master
    resistance_level="high",        # 抗拒程度：very_low/low/medium/high/very_high
    push_count=2,                   # 被追问次数
    last_agent_text="Kapan bisa bayar?"  # 上一轮机器人回复
)

print(response)
```

## 配置说明

### 用户类型 (persona)
| 用户类型 | 特点 | 主要回复类别 |
|----------|------|--------------|
| cooperative | 合作型，愿意配合还款 | agree, time |
| busy | 忙碌型，常说自己没时间 | excuse, negotiate, time |
| negotiating | 协商型，希望延期或商量还款时间 | negotiate, question, time |
| silent | 沉默型，回复简短或不说话 | silent_short, other |
| forgetful | 健忘型，经常忘记还款或找理由拖延 | excuse, negotiate, other |
| resistant | 抗拒型，不愿意还款，态度较差 | refuse, excuse, emotion_angry, negotiate |
| excuse_master | 借口大师，各种理由拖延，极难说服 | excuse, refuse, negotiate, question, emotion_angry |

### 抗拒程度 (resistance_level)
| 抗拒程度 | 合作类回复概率 | 抗拒类回复概率 | 适用场景 |
|----------|----------------|----------------|----------|
| very_low | 90% | 10% | 非常配合的用户 |
| low | 70% | 30% | 比较配合的用户 |
| medium | 50% | 50% | 普通用户 |
| high | 30% | 70% | 比较抗拒的用户 |
| very_high | 10% | 90% | 非常抗拒的用户 |

### 对话阶段 (stage)
| 阶段 | 描述 |
|------|------|
| greeting | 问候阶段 |
| identity | 身份确认阶段 |
| purpose | 说明来意阶段 |
| ask_time | 询问还款时间阶段 |
| push | 施压催促阶段 |
| confirm | 确认承诺阶段 |
| close | 结束阶段 |

### 催收阶段 (chat_group)
| 阶段 | 描述 |
|------|------|
| H2 | 刚逾期（M0） |
| H1 | 逾期30天内（M1） |
| S0 | 逾期30天以上（M2+） |

## 语料库说明
生成式模拟器使用的语料库位于`data/behavior_analysis/customer_response_corpus.json`，包含：
- `stage_corpus`：按对话阶段分类的用户回复
- `category_corpus`：按回复类别分类的用户回复（agree/refuse/excuse等）
- `chat_group_corpus`：按催收阶段分类的用户回复
- `metadata`：语料库元数据

语料库是通过`src/experiments/scripts/extract_customer_behavior.py`脚本从真实对话转写中自动提取的。如果需要更新语料库，可以运行该脚本：

```bash
python src/experiments/scripts/extract_customer_behavior.py
```

## 实现逻辑
生成式模拟器采用基于语料库的智能检索匹配算法，不需要大语言模型：
1. **多维度匹配**：根据当前对话阶段、催收阶段、用户画像、抗拒程度、施压次数等参数，从语料库中筛选匹配的回复候选集
2. **加权随机**：对候选回复按照匹配度加权，随机选择最终回复，保证回复多样性
3. **动态调整**：根据施压次数动态调整回复的对抗性，施压次数越多，用户回复越容易出现愤怒、拒绝等对抗性内容

## 下一步计划
- [ ] 优化语料库，过滤低质量的ASR识别结果
- [ ] 增加更多用户行为模式的支持
- [ ] 支持自定义回复风格和语言特点
