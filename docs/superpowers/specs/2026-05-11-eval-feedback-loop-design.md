# 评测反馈循环重构 — 双轨校准评测体系

**日期**: 2026-05-11
**状态**: 设计完成，待实现
**关联任务**: P15-G03（校准模型）, P15-G04（模拟器升级）

## 问题陈述

当前评测体系的核心缺陷：**无法从评测分数推断真实回款率变化**。

1. **代理指标不可靠**：以"bot 拿到承诺时间"为成功，但 P15-G01 显示人工坐席标注成功的案例中仅 50.8% 真正还款（35.3% 假阳性率）
2. **黄金数据集对话偏短**（平均 4 轮）：无法测量策略参数（push 持久度、展期优先、异议耐心）的差异效果
3. **优化靠猜测**：策略改动后无法确认其是否真正提升了还款率，只能依赖直觉和零散对比

## 目标

构建双轨评测体系，使每次策略改动都有可量化的 Δrepay 预估：

- **轨道 1（校准模型）**：对话特征 → P(repay) 概率，提供科学锚点
- **轨道 2（拟真模拟器）**：注入真实行为档案的客户模拟，提供秒级迭代反馈
- 两轨信号相互校验，冲突时触发人工研判

## 组件设计

### 组件 1: 特征提取器 (DialogueFeatureExtractor)

**位置**: `src/evaluation/feature_extractor.py`

**输入**: `DialogueLog`（来自 chatbot 或 gold dataset）+ `UserProfile`（来自 CSV）

**输出**: 26 维特征向量（np.ndarray 或可读 dict）

**三类特征**：

- A. 对话行为特征（10维）：total_turns, push_count, silence_count, unknown_count, extension_offered, got_commitment, commitment_turn, objection_types, final_state, cooperation_signals
- B. 用户画像特征（10维）：new_flag, chat_group, dpd, repay_history, income_ratio, product_name（编码）, marital_status, loan_seq, call_hour, seats_group
- C. 策略参数特征（6维）：approach（编码）, tone（编码）, push_intensity, extension_priority, max_push_rounds, extension_fee_ratio。注意：策略参数仅用于离线分析，不参与线上预测

**缺失处理**: 缺失字段填中位值，记录缺失率，不抛异常中断评测

### 组件 2: 校准模型 (RepaymentCalibrator)

**位置**: `src/evaluation/calibrator.py`

**模型**: Logistic Regression（首选），后续可升级 XGBoost

**训练数据**: 806 gold linkage cases → 对话回放 → 提取 26 维特征 → Y = `repay_type` 是否为 repay/extend

**目标变量**: 有效还款 = 1（repay 或 extend），未还款 = 0（empty）
已知偏差：仅追踪 12h 内还款，超时还款被误标为空，报告中标出

**API**:
```python
# 单次预测
calibrator.predict(features) -> {
    "repay_prob": 0.73,
    "ci_lower": 0.61,
    "ci_upper": 0.83,
    "top_factors": [("dpd", +0.18), ("push_count", +0.12)]
}

# 批量策略比较
calibrator.compare(logs_a, logs_b) -> {
    "delta_mean": +0.04,
    "p_value": 0.03,
    "significant": True
}
```

**质量门槛**:
| 指标 | 阈值 | 说明 |
|------|------|------|
| AUC | ≥ 0.75 | 区分还款/未还款能力 |
| ECE (校准误差) | ≤ 0.10 | 预测概率与真实频率一致 |
| PSI (特征稳定性) | ≤ 0.15 | 训练/验证分布一致性 |

### 组件 3: 拟真模拟器 (RealisticSimulator)

**位置**: 扩展 `src/core/simulator.py`，新增 `BehaviorProfile` dataclass

**核心变更**: 在 `generate_response()` 的 stage→response 逻辑前插入 profile 判断层，不改动核心逻辑。现有 `compare_strategies_gen.py` 零改动复用。

**BehaviorProfile 三大决策点**:

1. 回不回应？— silent_type / reluctant / responsive
2. 给什么回应？— honest / excuse_prone / false_promiser
3. 最终还了吗？— payer / non_payer / conditional

**5 种预定义档案**（基于 P15-G01 校准数据）:

| 档案 | 特征 | will_repay | 对标数据 |
|------|------|------------|----------|
| 沉默还款型 | reluctant + honest | True | 老客 H2 90.4% |
| 借口大师型 | responsive + excuse_prone | conditional | 新客 S0 28.2% |
| 虚假承诺型 | responsive + false_promiser | False | 35% FPR |
| 明知故拖型 | responsive + excuse_prone | conditional (需高强度 push) | 老客 S0 53.4% |
| 无力回天型 | responsive + honest | False | DPD>7 0.7% |

**conditional 档案**: will_repay 取决于 bot 的策略强度参数（push_intensity, max_push_rounds, extension_priority），这是测量策略差异增量效果的核心机制。

### 组件 4: 评估报告器 (EvalReporter)

**位置**: `src/evaluation/reporter.py`

**每份报告五段**:

- **A. 一页纸结论**: 双轨信号 + 冲突状态 + 最大贡献特征 + 需关注项
- **B. 模拟器分群明细**: 9 客群的承诺率变化（2,500 对话/方案）
- **C. 校准模型分群预测**: 按 DPD/客群等维度的 Δrepay
- **D. 冲突检测与研判建议**: 四种信号模式的自动化分析（见下表）
- **E. 历史趋势**: 每次评测一条 JSONL 写入 `data/evaluations/history.jsonl`

**冲突研判规则**:

| 信号模式 | 研判建议 | 用户决策 |
|----------|----------|----------|
| 双升 | 置信度高，建议采纳。检查负向交叉（如新客升但老客降），如有则微调 | 采纳/微调 |
| 模拟器升·模型平 | 可能 reward hacking 或模型训练数据偏短。建议 PSI 检查对话分布 | 采信模型/重做 |
| 模型升·模拟器平 | 模拟器可能缺对应行为档案。建议确认档案覆盖，如无则新增后重测 | 补充档案/采信 |
| 双降 | 清晰负面信号，建议回滚。有强业务理由可保留但标记降幅 | 回滚/保留 |

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/evaluation/__init__.py` | 新增/更新 | 模块入口 |
| `src/evaluation/feature_extractor.py` | 新增 | 组件1: 26维特征提取 |
| `src/evaluation/calibrator.py` | 新增 | 组件2: Logistic Regression 校准模型 |
| `src/evaluation/reporter.py` | 新增 | 组件4: 双轨评测报告生成 |
| `src/core/simulator.py` | 修改 | 组件3: 新增 BehaviorProfile + _apply_profile() |
| `src/experiments/run_eval.py` | 新增 | 一键评测入口：回放→特征→模型→报告 |
| `data/evaluations/history.jsonl` | 新增 | 历史趋势追踪文件 |

## 扩展点

以下不在当前范围内，但设计预留了接口：

- **校准模型升级 XGBoost**：calibrator.py 支持 model_type 参数切换
- **新增行为档案**：BehaviorProfile 是 dataclass，实例化即用，无需改代码
- **多语言模型**：特征提取器 language-agnostic，切换训练数据即可适配新语言
- **实时线上校准**：特征提取器接口与 chatbot.py 兼容，后续可接入生产 pipeline
- **A/B 测试集成**：compare() 方法输出 p_value + CI，直接对接 P22 A/B 框架

## 验证方式

```bash
# 1. 单元测试
python3 -m pytest src/evaluation/ -v

# 2. 校准模型训练 + 交叉验证
python3 -m src.evaluation.calibrator --train --cv 5

# 3. 端到端评测
python3 -m src.experiments.run_eval --strategy-a default --strategy-b segmented --episodes 100

# 4. 回归测试确保现有功能不受影响
python3 -m src.tests.test_regression
```
