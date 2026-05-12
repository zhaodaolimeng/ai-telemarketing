#!/usr/bin/env python3
"""P15-H05: T3 跨通话轨迹分析离线回测

从 gold_linkage.json 加载多通话用户，构建 CallSnapshot 序列，
运行 TrajectoryAnalyzer，输出统计信息。
"""
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.trajectory_analyzer import TrajectoryAnalyzer, CallSnapshot

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "gold_dataset"


# 意图分类
COOPERATION_INTENTS = frozenset({
    "agree_to_pay", "confirm_time", "acknowledge_debt",
    "ask_extension", "ask_amount", "confirm_identity",
    "greeting", "respond_to_greeting",
})

OBJECTION_INTENTS = frozenset({
    "refuse_to_pay", "threaten", "no_money", "cannot_repay_now",
    "dont_know", "deny_identity", "question_identity", "third_party",
})

SILENCE_INTENTS = frozenset({"unknown", "unknown_intent", ""})


def extract_phone(case_id: str) -> str:
    """从 case_id 提取手机号"""
    return case_id.split("-")[0] if "-" in case_id else case_id


def build_snapshot(link: dict, transcript: dict) -> CallSnapshot | None:
    """从 linkage 条目和 transcript 构建 CallSnapshot"""
    dialogue = transcript.get("dialogue", [])
    if not dialogue:
        return None

    # 统计对话特征
    turns = len(dialogue)
    cooperation = 0
    objection = 0
    silence = 0
    push_count = 0

    for turn in dialogue:
        intent = turn.get("user_intent", "").strip().lower() or ""
        # 归一化: "" → "silence"
        if not intent:
            intent = ""

        if intent in COOPERATION_INTENTS:
            cooperation += 1
        elif intent in OBJECTION_INTENTS:
            objection += 1
        elif intent in SILENCE_INTENTS:
            silence += 1

        # agent 的推催话术
        if turn.get("speaker") == "agent" and turn.get("stage") in (
            "push_for_time", "push", "push_hard", "push_final"
        ):
            push_count += 1

    # 是否获得承诺
    got_commitment = any(
        t.get("user_intent") == "confirm_time"
        for t in dialogue
        if t.get("speaker") == "customer"
    )

    # 是否展期
    got_extension = link.get("repay_type") == "extend"

    call_result = transcript.get("basic_info", {}).get("call_result", "abandoned")
    # 归一化 call_result
    if call_result in ("failure", "not_connected", "voice_mail"):
        call_result = "failed"
    elif call_result in ("success", "connected"):
        call_result = "success"
    else:
        call_result = "abandoned"

    return CallSnapshot(
        call_index=0,  # 排序后重设
        call_date=link.get("case_id", ""),
        new_flag=link.get("new_flag", 0),
        chat_group=link.get("chat_group", "H2"),
        dpd=link.get("dpd", 0),
        call_result=call_result,
        objection_count=objection,
        cooperation_signals=cooperation,
        got_commitment=got_commitment,
        got_extension=got_extension,
        turns=turns,
        silence_count=silence,
        push_count=push_count,
        loan_no=link.get("loan_no", ""),
    )


def main():
    linkage_path = DATA_DIR / "processed" / "gold_linkage.json"
    if not linkage_path.exists():
        print(f"ERROR: gold_linkage.json not found at {linkage_path}")
        return 1

    with open(linkage_path) as f:
        linkage_data = json.load(f)

    linked = linkage_data.get("linked_cases", [])
    print(f"Total linked cases: {len(linked)}")

    # 按手机号分组
    phone_groups: dict[str, list[dict]] = defaultdict(list)
    for case in linked:
        phone = extract_phone(case["case_id"])
        phone_groups[phone].append(case)

    multi_call_phones = {
        p: cases for p, cases in phone_groups.items()
        if len(cases) >= 2
    }
    print(f"Users with 2+ calls: {len(multi_call_phones)}")

    # 构建轨迹
    analyzer = TrajectoryAnalyzer()
    direction_counts: Counter[str] = Counter()
    pattern_counts: Counter[str] = Counter()
    all_deltas: dict[str, list[int | float]] = defaultdict(list)
    total_adjustments = 0
    users_with_adjustments = 0
    processed = 0

    for phone, cases in sorted(multi_call_phones.items()):
        # 按 case_id 排序（含时间戳）
        cases_sorted = sorted(cases, key=lambda c: c["case_id"])
        snapshots = []

        for case in cases_sorted:
            case_file = case.get("file", "")
            if not case_file:
                continue
            transcript_path = RAW_DIR / case_file
            if not transcript_path.exists():
                continue

            try:
                with open(transcript_path) as f:
                    transcript = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            snap = build_snapshot(case, transcript)
            if snap:
                snapshots.append(snap)

        if len(snapshots) < 2:
            continue

        # 重设 call_index
        for i, s in enumerate(snapshots):
            s.call_index = i

        profile = analyzer.analyze(snapshots)
        processed += 1

        direction_counts[profile.direction] += 1
        for pat in profile.active_patterns:
            pattern_counts[pat] += 1

        adj = profile.adjustments
        if adj:
            total_adjustments += 1
            if any(v != 0 and v != 0.0 for v in adj.to_dict().values() if isinstance(v, (int, float))):
                users_with_adjustments += 1

            d = adj.to_dict()
            for key, val in d.items():
                if isinstance(val, (int, float)) and val != 0:
                    all_deltas[key].append(val)

    # ── 输出 ──────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"T3 Trajectory Backtest Results")
    print(f"{'='*60}")
    print(f"Multi-call users processed: {processed}")
    print(f"Users with adjustments: {users_with_adjustments}/{processed}")

    print(f"\n── Direction Distribution ──")
    total_d = sum(direction_counts.values())
    for direction in ["improving", "deteriorating", "stable", "volatile", "insufficient_data"]:
        count = direction_counts.get(direction, 0)
        pct = count / max(total_d, 1) * 100
        bar = "█" * int(pct / 2)
        print(f"  {direction:20s}: {count:4d} ({pct:5.1f}%) {bar}")

    print(f"\n── Pattern Frequency ──")
    for pattern, count in pattern_counts.most_common():
        print(f"  {pattern:30s}: {count:4d}")

    print(f"\n── Adjustment Delta Statistics ──")
    for key, vals in sorted(all_deltas.items()):
        if vals:
            avg = sum(vals) / len(vals)
            print(f"  {key:30s}: n={len(vals):3d}, mean={avg:+.3f}, "
                  f"min={min(vals):+.1f}, max={max(vals):+.1f}")

    print(f"\n── Rule Hit Summary ──")
    rule_hits = {
        "R1 soften_deteriorating": "deteriorating" if direction_counts.get("deteriorating", 0) > 0 else None,
        "R2 reward_improving": "improving" if direction_counts.get("improving", 0) > 0 else None,
        "R3 always_extends": pattern_counts.get("ALWAYS_EXTENDS", 0),
        "R4 post_extension_repeat": pattern_counts.get("POST_EXTENSION_REPEAT", 0),
        "R5 silence_growing": pattern_counts.get("SILENCE_GROWING", 0),
        "R6 consecutive_failure": pattern_counts.get("CONSECUTIVE_FAILURE", 0),
        "R7 cycle_breaker": pattern_counts.get("CYCLE_BREAKER", 0),
        "R8 always_pays_after_push": pattern_counts.get("ALWAYS_PAYS_AFTER_PUSH_3", 0),
    }
    for rule, hits in rule_hits.items():
        print(f"  {rule:35s}: {hits}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
