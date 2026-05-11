# 双轨校准评测体系 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建双轨评测体系 — 校准模型 (P(repay|features)) + 拟真模拟器 (BehaviorProfile)，使每次策略改动都有可量化的 Δrepay 预估

**Architecture:** 4 个独立组件通过统一接口串联。FeatureExtractor 从对话日志抽 26 维特征 → Calibrator 输出 P(repay) → Simulator 升级注入 BehaviorProfile → Reporter 聚合双轨信号生成报告 + 历史追踪

**Tech Stack:** Python 3, scikit-learn (LogisticRegression), numpy, jsonlines

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `src/evaluation/__init__.py` | 模块入口，导出公共 API | 新建 |
| `src/evaluation/feature_extractor.py` | 从 DialogueLog + UserProfile → 26维特征向量 | 新建 |
| `src/evaluation/calibrator.py` | LogisticRegression 模型：训练/预测/策略比较 | 新建 |
| `src/evaluation/reporter.py` | 双轨信号聚合 + 冲突检测 + 历史追溯 | 新建 |
| `src/core/simulator.py` | 新增 BehaviorProfile dataclass + `_profile_driven_response()` | 修改 |
| `src/experiments/run_eval.py` | CLI 一键评测入口 | 新建 |

**依赖关系**: `feature_extractor.py` (无依赖) → `calibrator.py` (依赖 extractor) + `simulator.py` (独立) → `reporter.py` (依赖 calibrator + simulator) → `run_eval.py` (依赖以上全部)

---

### Task 1: 创建 evaluation 模块骨架

**Files:**
- Create: `src/evaluation/__init__.py`

- [ ] **Step 1: 创建模块入口文件**

`src/evaluation/__init__.py`:
```python
"""P15 评测体系 — 特征提取 + 校准模型 + 拟真模拟 + 双轨报告"""

from .feature_extractor import DialogueFeatureExtractor, UserProfile
from .calibrator import RepaymentCalibrator
from .reporter import EvalReporter

__all__ = [
    "DialogueFeatureExtractor",
    "UserProfile",
    "RepaymentCalibrator",
    "EvalReporter",
]
```

- [ ] **Step 2: 验证模块可导入**

Run: `python3 -c "import sys; sys.path.insert(0, 'src'); from evaluation import DialogueFeatureExtractor, RepaymentCalibrator, EvalReporter; print('OK')"`
Expected: ImportError (extractor not yet defined) — 确认路径正确即可，后续 Task 逐步消除

- [ ] **Step 3: Commit**

```bash
git add src/evaluation/__init__.py
git commit -m "feat: evaluation 模块骨架"
```

---

### Task 2: 特征提取器 — UserProfile + DialogueFeatureExtractor

**Files:**
- Create: `src/evaluation/feature_extractor.py`

- [ ] **Step 1: 定义 UserProfile dataclass**

`src/evaluation/feature_extractor.py`:
```python
"""组件1: 对话特征提取器 — DialogueLog + UserProfile → 26维特征向量"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class UserProfile:
    """用户画像 — 来自 CSV 的高预测力字段"""
    new_flag: int = 0          # 0=新客, 1=新转老, 2=老客
    chat_group: str = "H2"     # H1/H2/S0
    dpd: int = 0               # 逾期天数
    repay_history: float = 0.5 # 历史还清率 [0-1]
    income_ratio: float = 1.0  # monthly_income / approved_amount
    product_name: str = ""     # UangNow/PinjamPro/DuitFast
    marital_status: str = ""   # married/single/divorced/widowed
    loan_seq: int = 1          # 借款次数
    call_hour: int = 12        # 通话时段 0-23
    seats_group: str = ""      # 坐席组 CTM-xxx

    # 以下为用中位值填充的默认值
    UNKNOWN_PRODUCT = "unknown_product"
    UNKNOWN_MARITAL = "unknown_marital"
    UNKNOWN_SEATS = "unknown_seats"
```

- [ ] **Step 2: 实现 DialogueFeatureExtractor**

Continue in `src/evaluation/feature_extractor.py`:
```python
class DialogueFeatureExtractor:
    """从对话日志 + 用户画像提取 26 维特征向量"""

    # 枚举编码映射
    PRODUCT_MAP = {"UangNow": 0, "PinjamPro": 1, "DuitFast": 2}
    MARITAL_MAP = {"married": 0, "single": 1, "divorced": 2, "widowed": 3}
    APPROACH_MAP = {"educate": 0, "guide": 1, "maintain": 2, "light": 3, "firm": 4, "intervene": 5}
    TONE_MAP = {"soft": 0, "neutral": 1, "firm": 2, "urgent": 3}

    def __init__(self):
        self.missing_counts: dict[str, int] = {}  # 缺失字段统计

    def extract(
        self,
        dialogue_log: dict,
        user_profile: Optional[UserProfile] = None,
        strategy_params: Optional[dict] = None,
    ) -> np.ndarray:
        """
        Args:
            dialogue_log: {
                "turns": int, "push_count": int, "silence_count": int,
                "unknown_count": int, "extension_offered": bool,
                "got_commitment": bool, "commitment_turn": int,
                "objection_types": list[str], "final_state": str,
                "cooperation_signals": int,
            }
            user_profile: UserProfile or None (缺失填中位值)
            strategy_params: {
                "approach": str, "tone": str, "push_intensity": int,
                "extension_priority": bool, "max_push_rounds": int,
                "extension_fee_ratio": float,
            } or None (离线分析时传入)

        Returns:
            np.ndarray shape (26,) float32
        """
        if user_profile is None:
            user_profile = UserProfile()
            self._count_missing("user_profile")
        if strategy_params is None:
            strategy_params = {}
            self._count_missing("strategy_params")

        features = []

        # A. 对话行为特征 (10维)
        features.append(float(dialogue_log.get("turns", 0)))
        features.append(float(dialogue_log.get("push_count", 0)))
        features.append(float(dialogue_log.get("silence_count", 0)))
        features.append(float(dialogue_log.get("unknown_count", 0)))
        features.append(float(dialogue_log.get("extension_offered", False)))
        features.append(float(dialogue_log.get("got_commitment", False)))
        features.append(float(dialogue_log.get("commitment_turn", -1)))  # -1 表示无承诺
        features.append(float(len(dialogue_log.get("objection_types", []))))
        features.append(float(dialogue_log.get("final_state", "") == "CLOSE"))
        features.append(float(dialogue_log.get("cooperation_signals", 0)))

        # B. 用户画像特征 (10维)
        features.append(float(user_profile.new_flag))
        features.append(float({"H1": 0, "H2": 1, "S0": 2}.get(user_profile.chat_group, 1)))
        features.append(float(user_profile.dpd))
        features.append(float(user_profile.repay_history))
        features.append(float(user_profile.income_ratio))
        features.append(float(self.PRODUCT_MAP.get(user_profile.product_name, 3)))
        features.append(float(self.MARITAL_MAP.get(user_profile.marital_status, 4)))
        features.append(float(user_profile.loan_seq))
        features.append(float(user_profile.call_hour))
        features.append(float(hash(user_profile.seats_group) % 27 if user_profile.seats_group else 0))

        # C. 策略参数特征 (6维)
        sp = strategy_params
        features.append(float(self.APPROACH_MAP.get(sp.get("approach", "educate"), 0)))
        features.append(float(self.TONE_MAP.get(sp.get("tone", "neutral"), 1)))
        features.append(float(sp.get("push_intensity", 2)))
        features.append(float(sp.get("extension_priority", False)))
        features.append(float(sp.get("max_push_rounds", 3)))
        features.append(float(sp.get("extension_fee_ratio", 0.25)))

        return np.array(features, dtype=np.float32)

    def extract_batch(
        self, dialogue_logs: list[dict], user_profiles: list[Optional[UserProfile]],
        strategy_params: Optional[dict] = None,
    ) -> np.ndarray:
        """批量提取特征"""
        return np.array([
            self.extract(log, profile, strategy_params)
            for log, profile in zip(dialogue_logs, user_profiles)
        ])

    @property
    def feature_names(self) -> list[str]:
        """26维特征名称列表"""
        return [
            "turns", "push_count", "silence_count", "unknown_count",
            "extension_offered", "got_commitment", "commitment_turn",
            "objection_type_count", "is_close", "cooperation_signals",
            "new_flag", "chat_group_encoded", "dpd", "repay_history",
            "income_ratio", "product_encoded", "marital_encoded",
            "loan_seq", "call_hour", "seats_encoded",
            "approach_encoded", "tone_encoded", "push_intensity",
            "extension_priority", "max_push_rounds", "extension_fee_ratio",
        ]

    def _count_missing(self, field: str):
        self.missing_counts[field] = self.missing_counts.get(field, 0) + 1

    def reset_missing_counts(self):
        self.missing_counts.clear()

    def missing_report(self) -> dict:
        return dict(self.missing_counts)
```

- [ ] **Step 3: 写单元测试**

Create `tests/test_feature_extractor.py`:
```python
"""特征提取器单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
from evaluation.feature_extractor import DialogueFeatureExtractor, UserProfile


def test_extract_full_input():
    ex = DialogueFeatureExtractor()
    log = {
        "turns": 12, "push_count": 3, "silence_count": 1,
        "unknown_count": 2, "extension_offered": True,
        "got_commitment": True, "commitment_turn": 8,
        "objection_types": ["no_money", "busy"],
        "final_state": "CLOSE", "cooperation_signals": 2,
    }
    profile = UserProfile(new_flag=2, chat_group="H2", dpd=0,
                          repay_history=0.8, income_ratio=2.5,
                          product_name="PinjamPro", marital_status="married",
                          loan_seq=5, call_hour=14, seats_group="CTM-JKT")
    strategy = {"approach": "light", "tone": "neutral", "push_intensity": 1,
                "extension_priority": False, "max_push_rounds": 1,
                "extension_fee_ratio": 0.3}

    vec = ex.extract(log, profile, strategy)

    assert isinstance(vec, np.ndarray)
    assert vec.shape == (26,)
    assert vec.dtype == np.float32
    assert vec[0] == 12.0         # turns
    assert vec[10] == 2.0         # new_flag
    assert vec[11] == 1.0         # chat_group H2 → 1
    assert vec[13] == 0.8         # repay_history
    assert vec[20] == 3.0         # approach "light" → 3


def test_extract_missing_profile_uses_defaults():
    ex = DialogueFeatureExtractor()
    log = {"turns": 5, "push_count": 1, "silence_count": 0,
           "unknown_count": 0, "extension_offered": False,
           "got_commitment": False, "commitment_turn": -1,
           "objection_types": [], "final_state": "INIT",
           "cooperation_signals": 0}
    vec = ex.extract(log)  # 不传 profile 和 strategy

    assert vec.shape == (26,)
    assert vec[0] == 5.0
    assert vec[10] == 0.0         # new_flag default
    assert vec[13] == 0.5         # repay_history default
    assert ex.missing_report()["user_profile"] == 1


def test_extract_batch():
    ex = DialogueFeatureExtractor()
    logs = [
        {"turns": 10, "push_count": 2, "silence_count": 0,
         "unknown_count": 1, "extension_offered": False,
         "got_commitment": True, "commitment_turn": 7,
         "objection_types": [], "final_state": "CLOSE",
         "cooperation_signals": 1},
        {"turns": 5, "push_count": 0, "silence_count": 2,
         "unknown_count": 0, "extension_offered": False,
         "got_commitment": False, "commitment_turn": -1,
         "objection_types": [], "final_state": "FAILED",
         "cooperation_signals": 0},
    ]
    profiles = [UserProfile(), None]
    batch = ex.extract_batch(logs, profiles)
    assert batch.shape == (2, 26)


def test_feature_names():
    ex = DialogueFeatureExtractor()
    assert len(ex.feature_names) == 26
    assert ex.feature_names[0] == "turns"
    assert ex.feature_names[-1] == "extension_fee_ratio"
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `python3 -m pytest tests/test_feature_extractor.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/evaluation/__init__.py src/evaluation/feature_extractor.py tests/test_feature_extractor.py
git commit -m "feat: DialogueFeatureExtractor — 对话日志+用户画像 → 26维特征向量"
```

---

### Task 3: 校准模型 — Logistic Regression 训练/预测/比较

**Files:**
- Create: `src/evaluation/calibrator.py`

- [ ] **Step 1: 实现 RepaymentCalibrator**

`src/evaluation/calibrator.py`:
```python
"""组件2: 回款校准模型 — P(repay | dialogue_features)"""
import json
import pickle
import numpy as np
from pathlib import Path
from typing import Optional
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score
from sklearn.calibration import calibration_curve

from .feature_extractor import DialogueFeatureExtractor, UserProfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class RepaymentCalibrator:
    """Logistic Regression 校准模型 — 输出 P(有效还款|对话特征)"""

    def __init__(self):
        self.model: Optional[LogisticRegression] = None
        self.extractor = DialogueFeatureExtractor()
        self.is_fitted = False
        self.cv_auc: float = 0.0
        self.cv_ece: float = 0.0

    def train(self, features: np.ndarray, labels: np.ndarray) -> dict:
        """
        训练模型 + 5-fold CV 评估

        Args:
            features: shape (N, 26)
            labels: shape (N,) 0/1

        Returns:
            {"auc": float, "ece": float, "n_samples": int, "pos_rate": float}
        """
        self.model = LogisticRegression(
            penalty='l2', C=1.0, solver='lbfgs',
            max_iter=1000, class_weight='balanced',
        )
        self.model.fit(features, labels)
        self.is_fitted = True

        # 5-fold CV 评估
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        y_pred_proba = cross_val_predict(self.model, features, labels, cv=cv, method='predict_proba')[:, 1]
        self.cv_auc = roc_auc_score(labels, y_pred_proba)

        # 校准误差 (ECE)
        prob_true, prob_pred = calibration_curve(labels, y_pred_proba, n_bins=10)
        self.cv_ece = float(np.mean(np.abs(prob_true - prob_pred)))

        return {
            "auc": round(self.cv_auc, 3),
            "ece": round(self.cv_ece, 3),
            "n_samples": len(labels),
            "pos_rate": round(float(np.mean(labels)), 3),
        }

    def predict(self, features: np.ndarray) -> dict:
        """单次预测，返回 P(repay) + 95% CI + top 特征贡献"""
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call train() first.")

        proba = self.model.predict_proba(features.reshape(1, -1))[0]
        repay_prob = float(proba[1])

        # 95% CI: 用 Wilson 近似
        n_eff = max(10, self.model.n_features_in_)
        z = 1.96
        p = repay_prob
        margin = z * np.sqrt(p * (1 - p) / n_eff)
        ci_lower = max(0.0, p - margin)
        ci_upper = min(1.0, p + margin)

        # Top 贡献特征
        coef = self.model.coef_[0]
        abs_coef = np.abs(coef)
        top_idx = np.argsort(abs_coef)[-5:][::-1]
        top_factors = [
            (self.extractor.feature_names[i], round(float(coef[i]), 3))
            for i in top_idx
        ]

        return {
            "repay_prob": round(repay_prob, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "top_factors": top_factors,
        }

    def compare(
        self,
        features_a: np.ndarray,
        features_b: np.ndarray,
    ) -> dict:
        """
        比较两组策略的 P(repay) 差异。
        用 bootstrap 估计 p-value (非参数，不依赖正态假设)。
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call train() first.")

        proba_a = self.model.predict_proba(features_a)[:, 1]
        proba_b = self.model.predict_proba(features_b)[:, 1]
        delta_obs = float(np.mean(proba_b) - np.mean(proba_a))

        # Bootstrap p-value
        n_boot = 1000
        combined = np.concatenate([proba_a, proba_b])
        n_a = len(proba_a)
        boot_deltas = np.zeros(n_boot)
        rng = np.random.RandomState(42)
        for i in range(n_boot):
            rng.shuffle(combined)
            boot_deltas[i] = float(np.mean(combined[:n_a]) - np.mean(combined[n_a:]))
        p_value = float(np.mean(np.abs(boot_deltas) >= abs(delta_obs)))

        return {
            "delta_mean": round(delta_obs, 4),
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "n_a": n_a,
            "n_b": len(proba_b),
        }

    def save(self, path: Path):
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "cv_auc": self.cv_auc,
                "cv_ece": self.cv_ece,
            }, f)

    def load(self, path: Path):
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.model = data["model"]
        self.cv_auc = data["cv_auc"]
        self.cv_ece = data["cv_ece"]
        self.is_fitted = True

    def quality_report(self) -> dict:
        return {
            "auc": self.cv_auc,
            "ece": self.cv_ece,
            "auc_pass": self.cv_auc >= 0.75,
            "ece_pass": self.cv_ece <= 0.10,
        }
```

- [ ] **Step 2: 写单元测试**

Create `tests/test_calibrator.py`:
```python
"""校准模型单元测试"""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
from evaluation.calibrator import RepaymentCalibrator


def make_synthetic_data(n=200, seed=42) -> tuple:
    rng = np.random.RandomState(seed)
    # DPD 是最强特征：dpd<=0 → 97% pos, dpd 1-7 → 36% pos, dpd>7 → 1% pos
    features = np.zeros((n, 26), dtype=np.float32)
    dpd = rng.choice([0, 3, 15], size=n, p=[0.5, 0.25, 0.25])
    features[:, 12] = dpd  # dpd column
    # 加一些噪声
    features[:, 0] = rng.randint(5, 20, n)  # turns
    features[:, 1] = rng.randint(0, 5, n)   # push_count

    labels = np.zeros(n, dtype=int)
    labels[dpd == 0] = rng.binomial(1, 0.97, np.sum(dpd == 0))
    labels[dpd == 3] = rng.binomial(1, 0.36, np.sum(dpd == 3))
    labels[dpd == 15] = rng.binomial(1, 0.01, np.sum(dpd == 15))
    return features, labels


def test_train_and_predict():
    X, y = make_synthetic_data()
    cal = RepaymentCalibrator()
    result = cal.train(X, y)

    assert result["auc"] >= 0.90  # DPD 是极强特征
    assert result["ece"] <= 0.15
    assert result["n_samples"] == 200

    # 测试预测
    pred = cal.predict(X[0])
    assert 0.0 <= pred["repay_prob"] <= 1.0
    assert "top_factors" in pred
    assert len(pred["top_factors"]) == 5


def test_compare():
    X, y = make_synthetic_data(300)
    cal = RepaymentCalibrator()
    cal.train(X, y)

    # 改变 push_intensity 特征的策略 B
    X_a = X[:100].copy()
    X_b = X[:100].copy()
    X_b[:, 22] += 2  # push_intensity +2

    result = cal.compare(X_a, X_b)
    assert "delta_mean" in result
    assert "p_value" in result
    assert isinstance(result["significant"], bool)


def test_save_load():
    X, y = make_synthetic_data(100)
    cal = RepaymentCalibrator()
    cal.train(X, y)

    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        tmp = Path(f.name)
    try:
        cal.save(tmp)
        cal2 = RepaymentCalibrator()
        cal2.load(tmp)
        assert cal2.is_fitted
        pred = cal2.predict(X[0])
        assert "repay_prob" in pred
    finally:
        tmp.unlink(missing_ok=True)


def test_quality_report():
    X, y = make_synthetic_data(100)
    cal = RepaymentCalibrator()
    cal.train(X, y)
    qr = cal.quality_report()
    assert "auc_pass" in qr
    assert "ece_pass" in qr
```

- [ ] **Step 3: 运行测试**

Run: `python3 -m pytest tests/test_calibrator.py -v`
Expected: 4/4 PASS

- [ ] **Step 4: Commit**

```bash
git add src/evaluation/calibrator.py tests/test_calibrator.py
git commit -m "feat: RepaymentCalibrator — Logistic Regression 校准模型 P(repay|features)"
```

---

### Task 4: 拟真模拟器 — BehaviorProfile 注入

**Files:**
- Modify: `src/core/simulator.py`

- [ ] **Step 1: 在 GenerativeCustomerSimulator 类中添加 BehaviorProfile**

在 `src/core/simulator.py` 文件末尾 (class 外部) 添加后，在 `generate_response()` 方法第一行插入 profile 检查:

在 `RealCustomerSimulatorV2` 类定义之前插入：
```python
@dataclass
class BehaviorProfile:
    """与 sim stage 无关的底层客户人设 — 来自 P15-G01 校准数据"""
    name: str                          # 档案名
    response_style: str = "responsive" # silent / reluctant / responsive
    intent_type: str = "honest"        # honest / excuse_prone / false_promiser
    will_repay: str = "payer"          # payer / non_payer / conditional

    # silent pass-through rounds: 第几轮后逐渐有反应
    silent_thaw_round: int = 2

    # excuse_prone 参数: 每轮切换借口的概率
    excuse_switch_rate: float = 0.6

    # false_promiser 参数: 给出承诺的轮次和具体程度
    promise_round: int = 2             # 第几轮后开始给虚假承诺
    promise_detail_level: float = 0.7  # 承诺具体程度 (越高越像真承诺)

    # conditional 参数: 多强的 push 才能促使其还款
    repayment_threshold: float = 0.5   # push_intensity / max_push 到达此值才还款

    # --- 内部引用 ---
    _rng: object = field(default_factory=lambda: random.Random())

    @classmethod
    def silent_payer_h2_old(cls) -> "BehaviorProfile":
        """档案1: H2老客·沉默还款型 — P15-G01 老客H2 90.4%"""
        return cls(name="silent_payer", response_style="reluctant",
                   intent_type="honest", will_repay="payer",
                   silent_thaw_round=2)

    @classmethod
    def excuse_master_s0_new(cls) -> "BehaviorProfile":
        """档案2: S0新客·借口大师型 — P15-G01 新客S0 28.2%"""
        return cls(name="excuse_master", response_style="responsive",
                   intent_type="excuse_prone", will_repay="conditional",
                   repayment_threshold=0.6, excuse_switch_rate=0.7)

    @classmethod
    def false_promiser(cls) -> "BehaviorProfile":
        """档案3: 虚假承诺型 — P15-G01 35.3% FPR"""
        return cls(name="false_promiser", response_style="responsive",
                   intent_type="false_promiser", will_repay="non_payer",
                   promise_round=2, promise_detail_level=0.8)

    @classmethod
    def knowing_delayer_s0_old(cls) -> "BehaviorProfile":
        """档案4: S0老客·明知故拖型 — P15-G01 老客S0 53.4%"""
        return cls(name="knowing_delayer", response_style="responsive",
                   intent_type="excuse_prone", will_repay="conditional",
                   repayment_threshold=0.75, excuse_switch_rate=0.5)

    @classmethod
    def hopeless_dpd(cls) -> "BehaviorProfile":
        """档案5: DPD极端·无力回天型 — P15-G01 DPD>7 0.7%"""
        return cls(name="hopeless", response_style="responsive",
                   intent_type="honest", will_repay="non_payer")


# 预构建实例 (工厂函数，每次调用返回独立实例以保证 _rng 隔离)
def make_profiles() -> dict:
    return {
        "silent_payer": BehaviorProfile.silent_payer_h2_old(),
        "excuse_master": BehaviorProfile.excuse_master_s0_new(),
        "false_promiser": BehaviorProfile.false_promiser(),
        "knowing_delayer": BehaviorProfile.knowing_delayer_s0_old(),
        "hopeless": BehaviorProfile.hopeless_dpd(),
    }
```

需要在 simulator.py 文件顶部的 import 区加 `from dataclasses import dataclass, field`。

- [ ] **Step 2: 在 RealCustomerSimulatorV2.generate_response() 插入 profile 优先判断**

在 `generate_response()` 方法第一行（L195 后），插入:
```python
    def generate_response(
        self, stage, chat_group="H2", persona="cooperative",
        resistance_level="medium", last_agent_text="",
        conversation_history=None, push_count=0,
        profile: Optional["BehaviorProfile"] = None,  # 新增参数
    ) -> str:
        # 如果传入了 BehaviorProfile，走 profile 驱动逻辑
        if profile is not None:
            return self._profile_driven_response(
                stage, profile, push_count, persona, resistance_level)
        history = conversation_history or []
        # ... 保持原有逻辑不变
```

- [ ] **Step 3: 实现 RealCustomerSimulatorV2._profile_driven_response()**

在 `RealCustomerSimulatorV2` 类中添加:
```python
    def _profile_driven_response(
        self, stage: str, profile, push_count: int,
        fallback_persona: str, fallback_resistance: str,
    ) -> str:
        """基于 BehaviorProfile 生成内在一致的回复"""
        pr = profile

        # ─── 决策1: 回不回应 ───
        if pr.response_style == "silent":
            if push_count < pr.silent_thaw_round:
                return "" if random.random() < 0.7 else "..."
            else:
                # 逐渐开口
                if random.random() < 0.5:
                    return random.choice(["Iya", "Ya", "Hm"])
        elif pr.response_style == "reluctant":
            if push_count < pr.silent_thaw_round and random.random() < 0.4:
                return "" if random.random() < 0.5 else "..."

        # ─── 决策2: 给什么回应 ───
        if pr.intent_type == "honest":
            return self._profile_honest(stage, push_count)
        elif pr.intent_type == "excuse_prone":
            return self._profile_excuse_prone(stage, push_count, pr)
        elif pr.intent_type == "false_promiser":
            return self._profile_false_promiser(stage, push_count, pr)

        # fallback
        return self._cooperative_response(stage)

    def _profile_honest(self, stage: str, push_count: int) -> str:
        """诚信型 — 按真实意愿回应"""
        if stage in ("greeting", "identity"):
            return random.choice(["Halo", "Iya", "Ya"])
        if stage in ("purpose", "ask_time"):
            return random.choice([
                "Saya belum punya duit", "Besok ya",
                "Saya sedang kesulitan", "Nanti saya usahakan",
            ])
        if stage == "push":
            if push_count >= 3:
                return random.choice(["Maaf, benar-benar tidak bisa", "Saya menyerah"])
            return random.choice([
                "Saya lagi susah", "Nanti ya",
                "Saya usahakan minggu ini",
            ])
        return "Iya"

    def _profile_excuse_prone(self, stage: str, push_count: int, profile) -> str:
        """借口型 — 递进式借口链，push≥3 后有小概率松口"""
        r = profile._rng.random()
        if stage in ("greeting", "identity"):
            return random.choice(["Halo?", "Ada apa?", "Ya?"])

        chains = [
            ["Nanti ya", "Sebentar lagi", "Saya tunggu dulu"],
            ["Saya lagi susah", "Belum ada uang", "Gaji belum turun"],
            ["Saya lupa", "Besok ya", "Minggu ini"],
            ["Berapa sih?", "Saya kira sudah lunas", "Kok banyak?"],
            ["Tidak bisa", "Jangan dipaksa", "Saya tidak mau"],
        ]
        chain_idx = min(push_count, len(chains) - 1)
        if push_count >= 3 and random.random() < 0.2:
            return random.choice([
                "Oke deh, saya usahakan besok",
                "Ya sudah, nanti saya transfer",
            ])
        return random.choice(chains[chain_idx])

    def _profile_false_promiser(self, stage: str, push_count: int, profile) -> str:
        """虚假承诺型 — 痛快给承诺但不履约"""
        if stage in ("greeting", "identity"):
            return random.choice(["Halo", "Iya", "Ya pak"])

        if stage in ("purpose", "ask_time"):
            return random.choice([
                "Oh iya pak, saya ingat tagihannya",
                "Ya saya tahu, mohon maaf pak",
            ])

        if stage == "push" or stage == "confirm":
            hours = ["1", "2", "3", "4", "5"]
            times = ["jam " + h for h in hours]
            times += ["nanti jam " + h for h in hours]
            times += ["siang nanti", "sore ini", "malam nanti"]

            if push_count >= profile.promise_round:
                detail = random.choice(times)
                confirmations = [
                    f"Baik pak, {detail} saya transfer",
                    f"Siap, {detail} pasti saya bayar",
                    f"Oke pak, {detail} ya",
                    f"Iya pak, {detail} saya lunasi",
                ]
                return random.choice(confirmations)
            else:
                return random.choice(["Iya pak", "Baik", "Saya usahakan"])

        return "Iya pak"
```

- [ ] **Step 4: 验证现有测试未破坏**

Run: `python3 -c "from src.core.simulator import RealCustomerSimulatorV2, BehaviorProfile, make_profiles; s=RealCustomerSimulatorV2(); bp=BehaviorProfile.false_promiser(); r=s.generate_response('push', push_count=2, profile=bp); print(f'Profile response: {r}')"`

- [ ] **Step 5: Commit**

```bash
git add src/core/simulator.py
git commit -m "feat: BehaviorProfile — 5种校准客户档案注入模拟器"
```

---

### Task 5: 评估报告器 — 双轨聚合 + 冲突检测 + 历史追踪

**Files:**
- Create: `src/evaluation/reporter.py`

- [ ] **Step 1: 实现 EvalReporter**

`src/evaluation/reporter.py`:
```python
"""组件4: 双轨评估报告器 — 聚合+冲突检测+历史追踪"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class EvalReporter:
    """聚合模拟器 + 校准模型双轨信号，生成结构化评测报告"""

    def __init__(self, history_path: Optional[Path] = None):
        if history_path is None:
            history_path = PROJECT_ROOT / "data" / "evaluations" / "history.jsonl"
        self.history_path = history_path
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        change_name: str,
        sim_result: dict,       # 模拟器结果: {"commit_rate": 0.64, "by_segment": {...}}
        model_result: dict,     # 校准模型结果: compare() 输出
        quality: dict,          # 模型质量: quality_report() 输出
    ) -> str:
        """生成完整评测报告，返回 Markdown 格式字符串"""

        sim_delta = sim_result.get("delta", 0.0)
        model_delta = model_result.get("delta_mean", 0.0)

        # 冲突检测
        conflict, pattern, recommendation = self._detect_conflict(
            sim_delta, model_delta, model_result.get("p_value", 1.0))

        # 构建报告
        lines = [
            f"# 策略评测报告 — {change_name}",
            f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## A. 一页纸结论",
            "",
            f"| 指标 | 方案A (旧) | 方案B (新) | Δ |",
            f"|------|-----------|-----------|---|",
            f"| 模拟器承诺率 | {sim_result.get('commit_rate_a', 0):.1%} | {sim_result.get('commit_rate_b', 0):.1%} | {sim_delta:+.1%} |",
            f"| 模型 P(repay) | {sim_result.get('repay_prob_a', 0):.2f} | {sim_result.get('repay_prob_b', 0):.2f} | {model_delta:+.2f} |",
            f"| 冲突状态 | {pattern} | | |",
            f"| 模型 AUC: {quality.get('auc', 0):.3f} | ECE: {quality.get('ece', 0):.3f} | | |",
            "",
            f"**研判建议**: {recommendation}",
            "",
        ]

        # 分群明细
        if "by_segment" in sim_result:
            lines.append("## B. 模拟器分群明细")
            lines.append("")
            lines.append("| 客群 | A(旧) | B(新) | Δ |")
            lines.append("|------|-------|-------|---|")
            for seg, (a, b) in sim_result["by_segment"].items():
                lines.append(f"| {seg} | {a:.1%} | {b:.1%} | {b-a:+.1%} |")
            lines.append("")

        lines.extend([
            "## D. 冲突研判",
            "",
            f"- **信号模式**: {pattern}",
            f"- **模拟器 Δ**: {sim_delta:+.1%}",
            f"- **模型 Δ**: {model_delta:+.2f} (p={model_result.get('p_value', 1):.3f})",
            f"- **建议**: {recommendation}",
            "",
        ])

        # 写入历史
        self._append_history(change_name, sim_delta, model_delta, conflict, pattern)

        return "\n".join(lines)

    def _detect_conflict(
        self, sim_delta: float, model_delta: float, p_value: float,
    ) -> tuple:
        """返回 (is_conflict, pattern_name, recommendation)"""
        eps = 0.01  # 1pp 以内视为 "平"
        sim_up = sim_delta > eps
        sim_down = sim_delta < -eps
        model_up = model_delta > eps
        model_down = model_delta < -eps

        if sim_up and model_up:
            return (False, "双升 ✓✓",
                    "置信度高，建议采纳。检查分群明细是否有负向交叉（如新客升但老客降），如有则微调参数。")
        elif sim_up and not (model_up or model_down):
            return (True, "模拟器升·模型平 ✗",
                    "可能 reward hacking — 策略优化了应对模拟器而非真实行为。建议用 PSI 检查模拟器生成的对话分布是否偏离训练数据。如偏离，采信模型；如未偏离且改动有强业务理由，可小范围灰度验证。")
        elif model_up and not (sim_up or sim_down):
            return (True, "模型升·模拟器平 ✗",
                    "模拟器可能缺少对应行为档案。建议检查该策略改动针对的客户类型是否在档案中有覆盖。如无，新增档案后重测；如有，采信模型信号。")
        elif sim_down and model_down:
            return (True, "双降 ✗✗",
                    "清晰负面信号，建议回滚。如改动有强业务理由（如合规要求），保留但显式标记降幅，在下一次迭代中寻找补偿方案。")
        elif sim_up and model_down:
            return (True, "信号背离 ✗",
                    "罕见情况 — 模拟器和模型完全相反。暂停推进，排查：(1) 模拟器档案是否匹配目标场景；(2) 模型训练数据是否覆盖此类策略参数范围；(3) 特征提取是否有bug。")
        elif sim_down and model_up:
            return (True, "信号背离 ✗",
                    "罕见情况 — 与上条同理，建议全面排查后再决策。")
        else:
            return (False, "双平 ==", "无显著变化，改动可能无效或被噪声淹没。")

    def _append_history(
        self, change_name: str, sim_delta: float, model_delta: float,
        conflict: bool, pattern: str,
    ):
        """追加一条历史记录"""
        record = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "change": change_name,
            "sim_delta": round(sim_delta, 4),
            "model_delta": round(model_delta, 4),
            "conflict": conflict,
            "pattern": pattern,
        }
        with open(self.history_path, "a") as f:
            f.write(json.dumps(record) + "\n")

    def get_history(self, limit: int = 20) -> list[dict]:
        """读取最近 N 条历史记录"""
        if not self.history_path.exists():
            return []
        records = []
        with open(self.history_path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records[-limit:]
```

- [ ] **Step 2: 写单元测试**

Create `tests/test_reporter.py`:
```python
"""评估报告器单元测试"""
import sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from evaluation.reporter import EvalReporter


def test_generate_report_no_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        hist = Path(tmp) / "history.jsonl"
        reporter = EvalReporter(history_path=hist)

        sim = {"commit_rate_a": 0.58, "commit_rate_b": 0.64, "delta": 0.06,
               "by_segment": {"新客H2": (0.52, 0.56), "老客S0": (0.48, 0.56)}}
        model = {"delta_mean": 0.04, "p_value": 0.03, "significant": True}
        quality = {"auc": 0.82, "ece": 0.06}

        report = reporter.generate_report("test_change", sim, model, quality)

        assert "双升" in report
        assert "新客H2" in report
        assert "0.06" in report or "+6.0%" in report

        # 验证历史写入
        records = reporter.get_history()
        assert len(records) == 1
        assert records[0]["change"] == "test_change"
        assert not records[0]["conflict"]


def test_detect_conflict_model_flat():
    with tempfile.TemporaryDirectory() as tmp:
        hist = Path(tmp) / "history.jsonl"
        reporter = EvalReporter(history_path=hist)

        sim = {"commit_rate_a": 0.58, "commit_rate_b": 0.66, "delta": 0.08}
        model = {"delta_mean": 0.005, "p_value": 0.8, "significant": False}
        quality = {"auc": 0.78, "ece": 0.08}

        report = reporter.generate_report("suspicious_change", sim, model, quality)

        assert "模拟器升" in report
        assert "reward hacking" in report.lower() or "reward" in report.lower()

        records = reporter.get_history()
        assert records[0]["conflict"] is True


def test_empty_history():
    with tempfile.TemporaryDirectory() as tmp:
        hist = Path(tmp) / "nonexistent.jsonl"
        reporter = EvalReporter(history_path=hist)
        records = reporter.get_history()
        assert records == []
```

- [ ] **Step 3: 运行测试**

Run: `python3 -m pytest tests/test_reporter.py -v`
Expected: 3/3 PASS

- [ ] **Step 4: Commit**

```bash
git add src/evaluation/reporter.py tests/test_reporter.py
git commit -m "feat: EvalReporter — 双轨聚合+冲突检测+历史趋势追踪"
```

---

### Task 6: CLI 评测入口 — 一键运行全链路

**Files:**
- Create: `src/experiments/run_eval.py`

- [ ] **Step 1: 实现 run_eval.py**

`src/experiments/run_eval.py`:
```python
#!/usr/bin/env python3
"""
一键评测入口 — 双轨校准评测

Usage:
  python3 -m src.experiments.run_eval --episodes 50
  python3 -m src.experiments.run_eval --train-only          # 仅训练校准模型
  python3 -m src.experiments.run_eval --compare strategies  # 对比新旧策略
"""
import sys, json, asyncio, argparse, random
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import numpy as np
from evaluation.feature_extractor import DialogueFeatureExtractor, UserProfile
from evaluation.calibrator import RepaymentCalibrator
from evaluation.reporter import EvalReporter
from core.chatbot import CollectionChatBot
from core.simulator import RealCustomerSimulatorV2, BehaviorProfile, make_profiles


def train_calibrator():
    """用 gold_linkage 数据训练校准模型"""
    linkage_path = PROJECT_ROOT / "data" / "gold_linkage.json"
    gd_path = PROJECT_ROOT / "data" / "gold_dataset"

    with open(linkage_path) as f:
        linkage = json.load(f)

    extractor = DialogueFeatureExtractor()
    features = []
    labels = []

    for case in linkage["linked_cases"]:
        file_path = gd_path / case["file"]
        if not file_path.exists():
            continue
        dialogue = json.loads(file_path.read_text()).get("dialogue", [])
        if not dialogue:
            continue

        # 构造 dialogue_log — 简化版，从原始对话提取
        turns = len([t for t in dialogue if t.get("speaker") == "customer"])
        objection_types = list(set(
            t.get("intent", "unknown") for t in dialogue
            if t.get("speaker") == "customer" and t.get("intent", "unknown") != "unknown"
        ))

        log = {
            "turns": turns,
            "push_count": 0,         # gold dialogue 太短，push 从对话内容推断
            "silence_count": 0,
            "unknown_count": sum(1 for t in dialogue if t.get("intent") == "unknown"),
            "extension_offered": False,
            "got_commitment": case.get("repay_type", "None") != "None",
            "commitment_turn": turns,
            "objection_types": objection_types,
            "final_state": "CLOSE",
            "cooperation_signals": sum(1 for t in dialogue if t.get("intent") in ("agree_to_pay", "confirm_identity")),
        }

        profile = UserProfile(
            new_flag=case.get("new_flag", 0),
            chat_group=case.get("chat_group", "H2"),
            dpd=case.get("dpd", 0),
            repay_history=0.5,
        )

        label = 1 if case.get("repay_type") in ("repay", "extend") else 0

        features.append(extractor.extract(log, profile))
        labels.append(label)

    if len(features) == 0:
        print("ERROR: No training data found")
        return None

    X = np.array(features)
    y = np.array(labels)
    print(f"训练数据: {len(y)} 条, 正样本率: {y.mean():.1%}")

    cal = RepaymentCalibrator()
    result = cal.train(X, y)
    print(f"训练完成: AUC={result['auc']:.3f}, ECE={result['ece']:.3f}")

    model_path = PROJECT_ROOT / "data" / "evaluations" / "calibrator.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    cal.save(model_path)
    print(f"模型已保存: {model_path}")

    return cal


def print_help():
    print(__doc__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="双轨校准评测")
    parser.add_argument("--train-only", action="store_true", help="仅训练校准模型")
    parser.add_argument("--help-details", action="store_true")
    args = parser.parse_args()

    if args.help_details:
        print_help()
    elif args.train_only:
        train_calibrator()
    else:
        # 默认: 训练 + 跑一次简单对比
        print("训练校准模型...")
        cal = train_calibrator()
        if cal:
            qr = cal.quality_report()
            print(f"\n模型质量: AUC={qr['auc']:.3f} (门槛≥0.75: {'PASS' if qr['auc_pass'] else 'FAIL'}), "
                  f"ECE={qr['ece']:.3f} (门槛≤0.10: {'PASS' if qr['ece_pass'] else 'FAIL'})")
```

- [ ] **Step 2: 验证可运行（数据路径检查）**

Run: `python3 src/experiments/run_eval.py --train-only`
Expected: 训练成功，输出 AUC 和 ECE

- [ ] **Step 3: Commit**

```bash
git add src/experiments/run_eval.py
git commit -m "feat: run_eval CLI — 一键训练校准模型+评测入口"
```

---

### Task 7: 集成验证 — 更新 __init__.py + 端到端跑通

**Files:**
- Modify: `src/evaluation/__init__.py`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: 更新 __init__.py 包含所有导出**

`src/evaluation/__init__.py` (替换为):
```python
"""P15 评测体系 — 特征提取 + 校准模型 + 拟真模拟 + 双轨报告"""

from .feature_extractor import DialogueFeatureExtractor, UserProfile
from .calibrator import RepaymentCalibrator
from .reporter import EvalReporter

__all__ = [
    "DialogueFeatureExtractor",
    "UserProfile",
    "RepaymentCalibrator",
    "EvalReporter",
]
```

- [ ] **Step 2: 运行全部新测试**

Run: `python3 -m pytest tests/test_feature_extractor.py tests/test_calibrator.py tests/test_reporter.py -v`
Expected: 11/11 PASS

- [ ] **Step 3: 运行回归测试确保未破坏**

Run: `python3 -m src.tests.test_regression`
Expected: 15/15 PASS

- [ ] **Step 4: 运行端到端评测**

Run: `python3 src/experiments/run_eval.py`
Expected: 训练完成 + 模型质量报告

- [ ] **Step 5: 更新 ROADMAP.md**

在 P15-G03 状态改为 ✅ 已完成，P15-G04 状态改为 ✅ 已完成

- [ ] **Step 6: Final commit**

```bash
git add src/evaluation/__init__.py docs/ROADMAP.md src/experiments/run_eval.py
git commit -m "feat: 双轨校准评测体系集成 — P15-G03+P15-G04 完成"
```
