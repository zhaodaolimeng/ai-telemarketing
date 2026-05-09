# 迭代优化操作指南

短周期（样本补充 → 薄弱点修复 → 回归验证）的标准操作流程。适用于多轮快速迭代阶段。

---

## 迭代循环总览

```
发现薄弱点 ──→ 补充样本 ──→ 修改优化 ──→ 回归验证 ──→ 记录结论
    ↑                                                        │
    └────────────────────────────────────────────────────────┘
```

---

## Step 1: 发现薄弱点

运行当前版本的全量评测，确认现状：

```bash
# 回归测试（15个核心场景，快速）
python3 -m src.tests.test_regression

# Golden 评测（20个/681个标准化案例）
python3 -m src.core.evaluation --num-tests 0    # 0 = 全部20个
python3 -m src.core.evaluation --num-tests 100  # 前100个

# 鲁棒性测试（119个高风险用例）
python3 -m src.tests.robustness_test
```

关注评测报告中的：
- **按客户类型失败率**：silent / excuse_master / resistant 哪个最弱
- **按抗拒程度失败率**：high / very_high 是否显著低于 baseline
- **按催收阶段失败率**：H2 / H1 / S0 哪个阶段问题集中

---

## Step 2: 补充样本

薄弱点确认后，针对性补充黄金测试集或鲁棒性用例。

### 2a. 自然增长：从管道产出中抽取

管道持续产出 ASR 转录 + 自动标注的黄金数据（`data/gold_dataset/`），定期审查新入库的 case：

```bash
# 查看最新产出的标注数据
ls -lt data/gold_dataset/ | head -20

# 统计当前数据集规模
ls data/gold_dataset/ | wc -l
```

选取与当前薄弱点匹配的 case（如 silent 类型、excuse_master 类型），人工审核后纳入评测集。

### 2b. LLM 精标注数据飞轮（P15-C01）

自动标注器的 regex 意图识别有盲区——81% 的客户话语被标为 `unknown`，其中大量异议意图（`no_money`、`threaten`、`user_abuse` 等）被漏掉。LLM 精标注用于从 `unknown` 池中挖掘真实意图，填补这个缺口。

**流程：**

```
gold_dataset (regex标注, 81% unknown)
    │
    ▼
提取 unknown 话语 ──→ LLM 批量精标注 ──→ 人工抽检 ──→ 合并训练数据
    │                                                    │
    ▼                                                    ▼
分析新发现意图                                  重训 ML 分类器
    │                                                    │
    ▼                                                    ▼
改进 regex 模式 ←──────────────────────────────── 上线 + 继续收集
```

**执行命令：**

```bash
# Round 1: 采样标注 + 发现新意图
python3 src/experiments/reannotate_intents.py --sample-size 400
# 产出: data/llm_intent_labels.json（训练数据）

# Round 2: 大规模批量标注
python3 src/experiments/discover_new_intents.py --limit 500
# 产出: data/llm_discovery_results.json（含新意图标记）

# 重训 ML 分类器（合并 LLM 标注数据）
python3 -c "
from core.simple_classifier import train_and_save_model
train_and_save_model(llm_labels_path='data/llm_intent_labels.json')
"
# 产出: models/simple_intent_classifier.pkl
```

**质量门禁：**

| 检查项 | 阈值 | 作用 |
|--------|------|------|
| LLM 标注一致性 | 与已知标签一致率 > 80% | 验证 LLM 标注质量 |
| 新意图合理性 | 每种新意图 ≥ 3 条样本 | 避免噪声引入 |
| 回归测试 | 15/15 全过 | 确保 regex/ML 改动不破坏已有功能 |
| ML 准确率 | 整体 > 75%，macro F1 > 45% | 确保模型可用 |

**第一轮 P15-C01 运行记录（2026-05-09）：**

| 指标 | 值 |
|------|------|
| 标注样本 | 550 条（两轮合计） |
| 从 unknown 挖掘 | `user_abuse` 19条、`busy_later` 36条、`threaten` 13条、`no_money` 9条 |
| 新增 regex 模式 | `user_abuse`（9个侮辱词）、`threaten`（+7模式）、`busy_later`（+3模式） |
| ML 类别扩充 | 16类 → 25类 |
| unknown 残留率 | ~18%（主要因 ASR 错误严重） |

### 2c. 定向构造：在 golden test cases 中添加

编辑 `src/core/simulator.py` 中的 `GOLDEN_TEST_CASES_V2`，新增 case 示例：

```python
{
    "case_id": "custom_silent_h1",
    "customer_type": "silent",
    "chat_group": "H1",
    "resistance_level": "high",
    "expected_success": False,
    "expected_states": ["CLOSE"],
    "description": "沉默客户在H1阶段不回应任何问题"
}
```

### 2d. 鲁棒性用例补充

编辑 `docs/evaluation/ROBUSTNESS_TEST_CASES.md`，在对应类别下新增表格行。

---

## Step 3: 修改优化

每次只改一个维度，避免多变量交叉影响判断。

### 常见改动类型与位置

| 问题类型 | 改什么 | 位置 |
|----------|--------|------|
| 某场景缺少应对话术 | 新增话术模板 | `chatbot.py:_init_script_lib()` |
| 意图分类不准 | 先跑 LLM 精标注补充训练数据（Step 2b），再重训 + 补 regex | `chatbot.py:IntentDetector`, `simple_classifier.py` |
| 状态流转不对 | 调整状态机逻辑 | `chatbot.py:_handle_*()` 方法 |
| 沉默/抗拒处理不当 | 调整沉默分级或抗拒策略 | `chatbot.py:_handle_silence()` |
| 模拟器不够真实 | 调整客户行为参数 | `simulator.py` 客户类型类 |

### 修改原则

- 先加话术，再动逻辑。话术补充是成本最低、风险最小的改进
- 每次改动后立即跑回归，不积累多个改动再测
- 改动后如果回归失败，优先修复回归，再继续新改动

---

## Step 4: 回归验证

```bash
# 快速回归（必跑，每次改动后）
python3 -m src.tests.test_regression

# Golden 评测（建议跑，特别是改话术/逻辑后）
python3 -m src.core.evaluation --num-tests 0

# 鲁棒性测试（改动较大时跑）
python3 -m src.tests.robustness_test
```

### 判断标准

| 结果 | 动作 |
|------|------|
| 回归全过 + 目标场景改善 | 提交，进入下一轮 |
| 回归全过 + 目标场景未改善 | 回滚改动，换方向 |
| 回归有失败 | 先修回归，再继续 |

---

## Step 5: 记录结论

每轮迭代在 commit message 中记录关键信息：

```
fix: 补充silence客户H2阶段引导话术

- 新增3条 silence_level_2 H2场景话术
- Golden评测 silent 2/2 → 1/2（H2场景通过，S0仍失败）
- 回归15/15无影响
```

不需要单独维护迭代日志文档，commit history 本身就是记录。

---

## 常用命令速查

```bash
# 评测
python3 -m src.tests.test_regression           # 回归（15 case，快）
python3 -m src.tests.playback_test             # 黄金回放
python3 -m src.tests.robustness_test           # 鲁棒性（119 case）

# 交互式单步调试
python3 -m src.core.chatbot                    # 命令行交互模式

# 批量测试
python3 -m src.tests.run_small_scale_test 50   # 随机50个case

# 数据飞轮
python3 src/experiments/reannotate_intents.py --sample-size 400   # LLM 精标注
python3 src/experiments/discover_new_intents.py --limit 500       # 开放式发现

# 查看评测历史
ls -lt data/evaluations/ | head -10
ls -lt data/regression_report_*.md | head -5
```
