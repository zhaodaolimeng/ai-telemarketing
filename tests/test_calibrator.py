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
    assert result["ece"] <= 0.20
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
