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

        # 5-fold CV 评估
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        y_pred_proba = cross_val_predict(self.model, features, labels, cv=cv, method='predict_proba')[:, 1]
        self.cv_auc = roc_auc_score(labels, y_pred_proba)

        # 校准误差 (ECE)
        prob_true, prob_pred = calibration_curve(labels, y_pred_proba, n_bins=10)
        self.cv_ece = float(np.mean(np.abs(prob_true - prob_pred)))

        # Fit on all data after CV (for prediction API)
        self.model.fit(features, labels)
        self.is_fitted = True

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

        # 95% CI: Wald normal interval (approximate, for display only)
        # Uses feature count as heuristic for effective sample size
        n_features = max(10, self.model.n_features_in_)
        z = 1.96
        p = repay_prob
        margin = z * np.sqrt(p * (1 - p) / n_features)
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

        Uses permutation test on model-predicted probabilities.
        NOTE: The p-value reflects whether the model-score difference
        could arise by chance, NOT whether actual repayment rates differ.
        This is a model-relative statistic, not a statement about true outcomes.
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
        """Save model to pickle file. Only load models from trusted sources."""
        with open(path, "wb") as f:
            pickle.dump({
                "model": self.model,
                "cv_auc": self.cv_auc,
                "cv_ece": self.cv_ece,
            }, f)

    def load(self, path: Path):
        """Load model from pickle file. WARNING: Only load from trusted sources.
        Pickle deserialization can execute arbitrary code."""
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
