#!/usr/bin/env python3
"""
P15-B01 策略效果评测 — 同输入公平对比版
"""
import sys, asyncio, random
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.chatbot import CollectionChatBot, ChatState
from core.simulator import GenerativeCustomerSimulator

STAGE_MAP = {
    "INIT": "greeting", "IDENTITY_VERIFY": "identity", "PURPOSE": "purpose",
    "ASK_TIME": "ask_time", "PUSH_FOR_TIME": "push", "CONFIRM_EXTENSION": "confirm",
    "HANDLE_OBJECTION": "negotiate", "CLOSE": "close", "FAILED": "close",
}


async def generate_inputs(sim, chat_group, persona, resistance, max_turns=18):
    """用中立bot预生成客户输入序列"""
    bot = CollectionChatBot(chat_group=chat_group, new_flag=0, customer_name="Test")
    inputs = []
    push_count = 0
    _resp, _ = await bot.process()

    for _turn in range(max_turns):
        sim_stage = STAGE_MAP.get(bot.state.name, "push")
        txt = sim.generate_response(
            stage=sim_stage, chat_group=chat_group,
            persona=persona, resistance_level=resistance,
            push_count=push_count,
        )
        if not txt or not txt.strip():
            txt = "..."
        inputs.append(txt)

        prev_state = bot.state.name
        _resp, _ = await bot.process(txt)
        if bot.commit_time or bot.state in (ChatState.CLOSE, ChatState.FAILED):
            break
        if prev_state == "PUSH_FOR_TIME":
            push_count += 1

    return inputs


async def run_bot(bot, inputs: list[str]) -> dict:
    """用固定输入序列驱动bot"""
    _resp, _ = await bot.process()
    turns = 1
    got_commit = False
    extension_offered = False
    final_state = ChatState.INIT
    consumed = 0

    for txt in inputs:
        if not txt or not txt.strip():
            txt = "..."
        consumed += 1
        resp, _ = await bot.process(txt)
        turns += 1
        final_state = bot.state
        if resp and ("exten" in resp.lower() or "perpanjangan" in resp.lower()):
            extension_offered = True
        if bot.commit_time:
            got_commit = True; break
        if final_state in (ChatState.CLOSE, ChatState.FAILED):
            break

    return {
        "turns": turns, "got_commit": got_commit,
        "final_state": final_state.name, "extension_offered": extension_offered,
        "consumed": consumed,
    }


async def main():
    configs = [
        (2, "S0", "老客·S0", "excuse_master", "high"),
        (2, "H2", "老客·H2", "cooperative", "low"),
        (1, "H2", "新转老·H2", "cooperative", "low"),
        (1, "S0", "新转老·S0", "excuse_master", "high"),
        (0, "H2", "新客·H2", "excuse_master", "medium"),
        (0, "S0", "新客·S0", "excuse_master", "high"),
    ]
    EPISODES = 50

    print("P15-B01 策略对比评测 (同输入 ×50ep)")
    print("=" * 90)

    for nf, cg, label, persona, resistance in configs:
        d = {"commit": 0, "turns": 0, "ext": 0, "fail": 0}
        s = {"commit": 0, "turns": 0, "ext": 0, "fail": 0}
        same_count = 0  # 两个bot结果一致的episode数

        for ep in range(EPISODES):
            random.seed(ep * 137 + 42)
            sim = GenerativeCustomerSimulator()
            inputs = await generate_inputs(sim, cg, persona, resistance)
            if not inputs:
                continue

            bot_d = CollectionChatBot(chat_group=cg, new_flag=0, customer_name="Test")
            bot_s = CollectionChatBot(chat_group=cg, new_flag=nf, customer_name="Test")

            r_d = await run_bot(bot_d, inputs)
            r_s = await run_bot(bot_s, inputs)

            d["commit"] += r_d["got_commit"]
            d["turns"] += r_d["turns"]
            d["ext"] += r_d["extension_offered"]
            d["fail"] += (r_d["final_state"] != "CLOSE")

            s["commit"] += r_s["got_commit"]
            s["turns"] += r_s["turns"]
            s["ext"] += r_s["extension_offered"]
            s["fail"] += (r_s["final_state"] != "CLOSE")

            if r_d["got_commit"] == r_s["got_commit"] and r_d["final_state"] == r_s["final_state"]:
                same_count += 1

        n = EPISODES
        cd = d["commit"] / n; cs = s["commit"] / n
        arrow = "↑" if cs > cd else ("↓" if cs < cd else "=")

        print(f"\n{label} ({persona}/{resistance}):")
        print(f"  承诺率:  {cd:.0%} → {cs:.0%}  {arrow} {cs-cd:+.0%}")
        print(f"  平均轮次: {d['turns']/n:.1f} → {s['turns']/n:.1f}  {s['turns']/n - d['turns']/n:+.1f}")
        print(f"  展期率:   {d['ext']/n:.0%} → {s['ext']/n:.0%}  {s['ext']/n - d['ext']/n:+.0%}")
        print(f"  失败率:   {d['fail']/n:.0%} → {s['fail']/n:.0%}  {s['fail']/n - d['fail']/n:+.0%}")
        print(f"  一致率:   {same_count/n:.0%} (两bot结果相同的比例)")

    # 新客对比作为sanity check: nf=0 vs nf=0 应该一致率≈100%
    print(f"\n{'=' * 90}")
    print("(新客 nf=0 对比为代码正确性验证：一致率应接近 100%)")


if __name__ == "__main__":
    asyncio.run(main())
