#!/usr/bin/env python3
"""
P15-B01 策略效果对比评测

对比"分客群策略" vs "默认H2策略"在不同客群×阶段组合下的表现。
数据源: gold_linkage.json (806 matched cases)
"""
import json, sys, asyncio, csv
from pathlib import Path
from collections import Counter, defaultdict
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.chatbot import CollectionChatBot, ChatState


async def replay_case(bot: CollectionChatBot, dialogue: list[dict], max_turns: int = 30) -> dict:
    """重放对话，返回结果"""
    turn_count = 0
    final_state = ChatState.INIT
    got_commit = False
    extension_offered = False
    agent_responses = []

    for i, turn in enumerate(dialogue):
        if turn.get("speaker") != "customer":
            continue
        if i >= max_turns:
            break

        customer_text = turn.get("text", "").strip()
        if not customer_text:
            continue

        response, _ = await bot.process(customer_text)
        turn_count += 1
        final_state = bot.state

        if response:
            agent_responses.append(response)
        if bot.commit_time:
            got_commit = True
            break
        if "exten" in response.lower() or "perpanjangan" in response.lower():
            extension_offered = True
        if final_state in (ChatState.CLOSE, ChatState.FAILED):
            break

    return {
        "turns": turn_count,
        "final_state": final_state.name,
        "got_commit": got_commit,
        "extension_offered": extension_offered,
        "agent_responses": agent_responses,
    }


async def run_comparison(num_per_segment: int = 15):
    """按 9 个客群分段，每个抽 N 条对比"""
    project_root = PROJECT_ROOT
    linkage_path = project_root / "data" / "gold_linkage.json"
    gd_path = project_root / "data" / "gold_dataset"

    with open(linkage_path) as f:
        linkage = json.load(f)

    linked = linkage["linked_cases"]

    # 分组
    groups = defaultdict(list)
    for c in linked:
        key = f"nf={c['new_flag']}_{c['chat_group']}"
        groups[key].append(c)

    segments = [
        ("nf=0_H1", "新客·H1"),
        ("nf=0_H2", "新客·H2"),
        ("nf=0_S0", "新客·S0"),
        ("nf=1_H1", "新转老·H1"),
        ("nf=1_H2", "新转老·H2"),
        ("nf=1_S0", "新转老·S0"),
        ("nf=2_H1", "老客·H1"),
        ("nf=2_H2", "老客·H2"),
        ("nf=2_S0", "老客·S0"),
    ]

    print("=" * 90)
    print("P15-B01 策略效果对比评测")
    print(f"每个客群抽样 {num_per_segment} 条，对比 默认H2策略(no_strategy) vs 分客群策略(with_strategy)")
    print("=" * 90)

    all_results = {}

    for seg_key, seg_name in segments:
        cases = groups.get(seg_key, [])
        if len(cases) < 3:
            print(f"\n{seg_name}: 样本不足({len(cases)}), 跳过")
            continue

        sample = cases[:num_per_segment]
        nf_val = int(seg_key.split("_")[0].split("=")[1])
        cg_val = seg_key.split("_")[1]

        # 统计指标
        no_strat = {"success": 0, "commit": 0, "turns": 0, "extensions": 0, "total": 0}
        with_strat = {"success": 0, "commit": 0, "turns": 0, "extensions": 0, "total": 0}

        for case in sample:
            file_path = gd_path / case["file"]
            if not file_path.exists():
                continue
            dialogue = json.loads(file_path.read_text()).get("dialogue", [])
            if not dialogue:
                continue

            no_strat["total"] += 1
            with_strat["total"] += 1

            # 无策略: 默认 new_flag=0
            bot_no = CollectionChatBot(chat_group=cg_val, new_flag=0)
            r_no = await replay_case(bot_no, dialogue)
            if r_no["final_state"] == "CLOSE" and r_no["got_commit"]:
                no_strat["success"] += 1
            if r_no["got_commit"]:
                no_strat["commit"] += 1
            no_strat["turns"] += r_no["turns"]
            if r_no["extension_offered"]:
                no_strat["extensions"] += 1

            # 有策略: 实际 new_flag
            bot_with = CollectionChatBot(chat_group=cg_val, new_flag=nf_val)
            r_with = await replay_case(bot_with, dialogue)
            if r_with["final_state"] == "CLOSE" and r_with["got_commit"]:
                with_strat["success"] += 1
            if r_with["got_commit"]:
                with_strat["commit"] += 1
            with_strat["turns"] += r_with["turns"]
            if r_with["extension_offered"]:
                with_strat["extensions"] += 1

        # 计算指标
        def calc_metrics(d):
            t = d["total"]
            if t == 0:
                return {}
            return {
                "success_rate": d["success"] / t,
                "commit_rate": d["commit"] / t,
                "avg_turns": d["turns"] / t,
                "extension_rate": d["extensions"] / t,
                "n": t,
            }

        m_no = calc_metrics(no_strat)
        m_with = calc_metrics(with_strat)
        all_results[seg_key] = {"no_strategy": m_no, "with_strategy": m_with, "seg_name": seg_name}

        succ_diff = m_with.get("success_rate", 0) - m_no.get("success_rate", 0)
        turn_diff = m_with.get("avg_turns", 0) - m_no.get("avg_turns", 0)
        ext_diff = m_with.get("extension_rate", 0) - m_no.get("extension_rate", 0)

        arrow_s = "↑" if succ_diff > 0 else ("↓" if succ_diff < 0 else "=")
        arrow_t = "↑" if turn_diff > 0 else ("↓" if turn_diff < 0 else "=")

        print(f"\n{'─' * 80}")
        print(f"  {seg_name} (n={m_no.get('n', 0)})")
        print(f"  {'指标':<18} {'默认H2策略':>12} {'分客群策略':>12} {'差异':>12}")
        print(f"  {'─' * 54}")
        print(f"  {'承诺率(commit)':<18} {m_no.get('commit_rate', 0):>11.1%} {m_with.get('commit_rate', 0):>11.1%} {arrow_s} {abs(succ_diff):.0%}")
        print(f"  {'平均轮次':<18} {m_no.get('avg_turns', 0):>11.1f} {m_with.get('avg_turns', 0):>11.1f} {arrow_t} {abs(turn_diff):.1f}")
        print(f"  {'展期提及率':<18} {m_no.get('extension_rate', 0):>11.1%} {m_with.get('extension_rate', 0):>11.1%} {f'+{ext_diff:.0%}' if ext_diff > 0 else f'{ext_diff:.0%}'}")

    # ─── 汇总 ───
    print(f"\n{'=' * 90}")
    print("整体汇总 (按客群加权平均)")
    print(f"{'=' * 90}")

    def weighted_avg(results, strategy_key):
        total_s = 0
        total_t = 0
        total_n = 0
        total_ext = 0
        total_cases = 0
        for seg_key, data in results.items():
            m = data[strategy_key]
            n = m.get("n", 0)
            if n == 0:
                continue
            total_s += m.get("commit_rate", 0) * n
            total_t += m.get("avg_turns", 0) * n
            total_ext += m.get("extension_rate", 0) * n
            total_cases += n
        if total_cases == 0:
            return {}
        return {
            "commit_rate": total_s / total_cases,
            "avg_turns": total_t / total_cases,
            "extension_rate": total_ext / total_cases,
            "n": total_cases,
        }

    w_no = weighted_avg(all_results, "no_strategy")
    w_with = weighted_avg(all_results, "with_strategy")

    print(f"  {'指标':<18} {'默认H2策略':>12} {'分客群策略':>12} {'差异':>12}")
    print(f"  {'─' * 54}")
    commit_diff = w_with.get("commit_rate", 0) - w_no.get("commit_rate", 0)
    turn_diff = w_with.get("avg_turns", 0) - w_no.get("avg_turns", 0)
    ext_diff = w_with.get("extension_rate", 0) - w_no.get("extension_rate", 0)
    print(f"  {'承诺率(commit)':<18} {w_no.get('commit_rate', 0):>11.1%} {w_with.get('commit_rate', 0):>11.1%} {commit_diff:>+11.1%}")
    print(f"  {'平均轮次':<18} {w_no.get('avg_turns', 0):>11.1f} {w_with.get('avg_turns', 0):>11.1f} {turn_diff:>+11.1f}")
    print(f"  {'展期提及率':<18} {w_no.get('extension_rate', 0):>11.1%} {w_with.get('extension_rate', 0):>11.1%} {ext_diff:>+11.1%}")

    # 阶段×客群汇总
    print(f"\n{'=' * 90}")
    print("按客群类型汇总 (跨阶段平均)")
    print(f"{'=' * 90}")
    for nf_val, nf_name in [(0, "新客"), (1, "新转老"), (2, "老客")]:
        no_s = 0; no_t = 0; no_ext = 0; no_n = 0
        wi_s = 0; wi_t = 0; wi_ext = 0; wi_n = 0
        for cg in ["H1", "H2", "S0"]:
            key = f"nf={nf_val}_{cg}"
            data = all_results.get(key, {})
            for strat_key, acc_s, acc_t, acc_ext, acc_n in [
                ("no_strategy", no_s, no_t, no_ext, no_n),
                ("with_strategy", wi_s, wi_t, wi_ext, wi_n),
            ]:
                m = data.get(strat_key, {})
                n = m.get("n", 0)
                if n:
                    if strat_key == "no_strategy":
                        no_s += m.get("commit_rate", 0) * n
                        no_t += m.get("avg_turns", 0) * n
                        no_ext += m.get("extension_rate", 0) * n
                        no_n += n
                    else:
                        wi_s += m.get("commit_rate", 0) * n
                        wi_t += m.get("avg_turns", 0) * n
                        wi_ext += m.get("extension_rate", 0) * n
                        wi_n += n

        if no_n == 0:
            continue
        no_cr = no_s / no_n; wi_cr = wi_s / wi_n
        no_tr = no_t / no_n; wi_tr = wi_t / wi_n
        no_er = no_ext / no_n; wi_er = wi_ext / wi_n
        print(f"  {nf_name}: commit {no_cr:.0%}→{wi_cr:.0%} ({wi_cr-no_cr:+.0%}) | turns {no_tr:.1f}→{wi_tr:.1f} ({wi_tr-no_tr:+.1f}) | ext {no_er:.0%}→{wi_er:.0%} ({wi_er-no_er:+.0%})")

    # 按阶段汇总
    print(f"\n按催收阶段汇总 (跨客群平均)")
    for cg in ["H1", "H2", "S0"]:
        no_s = 0; no_t = 0; no_ext = 0; no_n = 0
        wi_s = 0; wi_t = 0; wi_ext = 0; wi_n = 0
        for nf_val in [0, 1, 2]:
            key = f"nf={nf_val}_{cg}"
            data = all_results.get(key, {})
            for strat_key in ["no_strategy", "with_strategy"]:
                m = data.get(strat_key, {})
                n = m.get("n", 0)
                if n:
                    if strat_key == "no_strategy":
                        no_s += m.get("commit_rate", 0) * n
                        no_t += m.get("avg_turns", 0) * n
                        no_ext += m.get("extension_rate", 0) * n
                        no_n += n
                    else:
                        wi_s += m.get("commit_rate", 0) * n
                        wi_t += m.get("avg_turns", 0) * n
                        wi_ext += m.get("extension_rate", 0) * n
                        wi_n += n
        if no_n == 0:
            continue
        no_cr = no_s / no_n; wi_cr = wi_s / wi_n
        no_tr = no_t / no_n; wi_tr = wi_t / wi_n
        no_er = no_ext / no_n; wi_er = wi_ext / wi_n
        print(f"  {cg}: commit {no_cr:.0%}→{wi_cr:.0%} ({wi_cr-no_cr:+.0%}) | turns {no_tr:.1f}→{wi_tr:.1f} ({wi_tr-no_tr:+.1f}) | ext {no_er:.0%}→{wi_er:.0%} ({wi_er-no_er:+.0%})")

    print()


if __name__ == "__main__":
    asyncio.run(run_comparison(num_per_segment=15))
