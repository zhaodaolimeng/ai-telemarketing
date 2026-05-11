"""特征提取器单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pytest
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
    assert vec[13] == pytest.approx(0.8, rel=1e-6)  # repay_history
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
