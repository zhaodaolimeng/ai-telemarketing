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
        records = reporter.get_history()
        assert len(records) == 1
        assert records[0]["change"] == "test_change"
        assert not records[0]["conflict"]


def test_detect_conflict_sim_only():
    with tempfile.TemporaryDirectory() as tmp:
        hist = Path(tmp) / "history.jsonl"
        reporter = EvalReporter(history_path=hist)

        sim = {"commit_rate_a": 0.58, "commit_rate_b": 0.66, "delta": 0.08}
        model = {"delta_mean": 0.005, "p_value": 0.8, "significant": False}
        quality = {"auc": 0.78, "ece": 0.08}

        report = reporter.generate_report("suspicious_change", sim, model, quality)

        assert ("reward hacking" in report.lower() or
                "模拟器升" in report)
        records = reporter.get_history()
        assert records[0]["conflict"] is True


def test_empty_history():
    with tempfile.TemporaryDirectory() as tmp:
        hist = Path(tmp) / "nonexistent.jsonl"
        reporter = EvalReporter(history_path=hist)
        records = reporter.get_history()
        assert records == []
