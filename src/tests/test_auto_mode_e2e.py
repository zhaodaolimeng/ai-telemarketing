#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Mode 端到端测试

验证 SSE 流式仿真输出的完整性和正确性:
1. 事件类型序列 (greeting → greeting_audio → turn... → done)
2. 每个事件的字段完整性
3. 客户回复非空、Agent 回复非空
4. 音频文件存在性
5. 会话状态递进
6. 不同 persona / resistance / chat_group 组合
7. 翻译功能
8. 前端期望的数据格式一致性
"""

import asyncio as aio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.voice.customer_simulator import CustomerVoiceSimulator, SimulationTurn
from core.translator import get_translator


# ---------------------------------------------------------------------------
# 测试结果记录
# ---------------------------------------------------------------------------

@dataclass
class EventValidation:
    event_type: str
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CaseResult:
    case_name: str
    persona: str
    resistance: str
    chat_group: str
    passed: bool = True
    greeting_valid: Optional[EventValidation] = None
    greeting_audio_valid: Optional[EventValidation] = None
    turn_validations: List[EventValidation] = field(default_factory=list)
    done_valid: Optional[EventValidation] = None
    sequence_errors: List[str] = field(default_factory=list)
    total_turns: int = 0
    total_duration: float = 0.0


# ---------------------------------------------------------------------------
# 断言工具
# ---------------------------------------------------------------------------

def check(condition: bool, message: str) -> Optional[str]:
    return None if condition else message


# ---------------------------------------------------------------------------
# 核心验证逻辑
# ---------------------------------------------------------------------------

async def run_single_simulation(
    persona: str,
    resistance: str,
    chat_group: str,
    customer_name: str = "Budi",
    max_turns: int = 8,
    asr_model: str = "tiny",
) -> Tuple[CaseResult, List[Dict[str, Any]]]:
    """运行一次仿真，收集所有原始事件和验证结果。"""

    result = CaseResult(
        case_name=f"{persona}/{resistance}/{chat_group}",
        persona=persona,
        resistance=resistance,
        chat_group=chat_group,
    )

    events: List[Dict[str, Any]] = []
    start_time = time.time()

    # ---- 创建组件 ----
    bot = CollectionChatBot(
        chat_group=chat_group,
        customer_name=customer_name,
    )
    bot.session_id = str(uuid.uuid4())

    sim = await CustomerVoiceSimulator.create(
        chatbot=bot,
        persona=persona,
        resistance_level=resistance,
        chat_group=chat_group,
        customer_name=customer_name,
        asr_model_size=asr_model,
        realtime=False,
        save_artifacts=False,
    )

    if not sim._asr.is_available:
        result.passed = False
        result.sequence_errors.append("ASR model not available")
        return result, events

    # ---- 0. greeting ----
    greeting_valid = EventValidation(event_type="greeting")
    first_msg, _ = await bot.process(use_tts=False)

    greeting_valid.errors.append(check(bool(first_msg), "greeting agent_text is empty"))
    greeting_valid.errors.append(check(len(first_msg) > 10, f"greeting agent_text too short: '{first_msg}'"))
    greeting_valid.errors.append(check(
        bot.session_id is not None,
        "bot.session_id is None"
    ))
    greeting_valid.details = {
        "session_id": bot.session_id,
        "agent_text": first_msg[:100],
        "state": sim._state_to_stage(bot.state),
    }
    greeting_valid.errors = [e for e in greeting_valid.errors if e]
    greeting_valid.passed = len(greeting_valid.errors) == 0
    result.greeting_valid = greeting_valid

    # ---- 1. greeting_audio ----
    audio_valid = EventValidation(event_type="greeting_audio")
    greeting_audio_url = None
    audio_file_exists = False
    if first_msg:
        try:
            tts_result = await sim._tts.synthesize(first_msg, voice=sim.agent_voice)
            if tts_result.success and tts_result.audio_file:
                greeting_audio_url = f"/audio/{Path(tts_result.audio_file).name}"
                audio_file_exists = Path(tts_result.audio_file).exists()
            else:
                audio_valid.errors.append(f"greeting TTS failed: {tts_result.error_message}")
        except Exception as e:
            audio_valid.errors.append(f"greeting TTS exception: {e}")
    else:
        audio_valid.errors.append("No first_msg for greeting TTS")

    audio_valid.errors.append(check(audio_file_exists, f"greeting audio file not found: {greeting_audio_url}"))
    audio_valid.details = {"audio_url": greeting_audio_url, "file_exists": audio_file_exists}
    audio_valid.errors = [e for e in audio_valid.errors if e]
    audio_valid.passed = len(audio_valid.errors) == 0
    result.greeting_audio_valid = audio_valid

    # ---- 2. turns ----
    turn_count = 0
    states_seen: List[str] = [sim._state_to_stage(bot.state)]

    async for turn in sim.run_streaming(max_turns=max_turns):
        turn_count += 1
        turn_valid = EventValidation(event_type=f"turn_{turn.turn_id}")

        # --- 字段完整性 ---
        turn_valid.errors.append(check(
            turn.turn_id > 0, f"invalid turn_id: {turn.turn_id}"
        ))
        turn_valid.errors.append(check(
            bool(turn.customer_text and turn.customer_text.strip()),
            f"turn {turn.turn_id}: customer_text is empty"
        ))
        turn_valid.errors.append(check(
            len(turn.customer_text.strip()) > 0,
            f"turn {turn.turn_id}: customer_text whitespace only"
        ))
        turn_valid.errors.append(check(
            bool(turn.agent_text and turn.agent_text.strip()),
            f"turn {turn.turn_id}: agent_text is empty"
        ))

        # --- 客户音频 ---
        customer_audio_ok = True
        if turn.customer_audio_file:
            if not Path(turn.customer_audio_file).exists():
                turn_valid.errors.append(
                    f"turn {turn.turn_id}: customer audio not found: {turn.customer_audio_file}"
                )
                customer_audio_ok = False
        else:
            turn_valid.warnings.append(f"turn {turn.turn_id}: no customer_audio_file")
            customer_audio_ok = False

        # --- Agent 音频 ---
        agent_audio_ok = True
        if turn.agent_audio_file:
            if not Path(turn.agent_audio_file).exists():
                turn_valid.errors.append(
                    f"turn {turn.turn_id}: agent audio not found: {turn.agent_audio_file}"
                )
                agent_audio_ok = False
        else:
            turn_valid.warnings.append(f"turn {turn.turn_id}: no agent_audio_file")
            agent_audio_ok = False

        # --- ASR ---
        if turn.asr_text:
            turn_valid.details["asr_cer"] = round(turn.asr_cer, 4)
            turn_valid.details["asr_exact_match"] = turn.asr_exact_match
            if turn.asr_cer > 1.0:
                turn_valid.warnings.append(
                    f"turn {turn.turn_id}: CER > 100% ({turn.asr_cer:.2%})"
                )

        # --- 状态递进 ---
        current_state = sim._state_to_stage(bot.state)
        states_seen.append(current_state)
        if turn.state_before and turn.state_after:
            turn_valid.details["state"] = f"{turn.state_before} → {turn.state_after}"
        else:
            turn_valid.details["state"] = str(current_state)

        # --- 时序 ---
        turn_valid.details.update({
            "customer_text": turn.customer_text[:80],
            "agent_text": turn.agent_text[:80],
            "tts_time": round(turn.tts_time, 3),
            "asr_time": round(turn.asr_time, 3),
            "total_time": round(turn.total_time, 3),
            "customer_audio_ok": customer_audio_ok,
            "agent_audio_ok": agent_audio_ok,
        })

        turn_valid.errors = [e for e in turn_valid.errors if e]
        turn_valid.passed = len(turn_valid.errors) == 0
        result.turn_validations.append(turn_valid)

        # --- 检查对话是否可结束 ---
        if bot.is_finished():
            break

    result.total_turns = turn_count

    # ---- 3. done ----
    done_valid = EventValidation(event_type="done")
    report = sim.get_report()

    done_valid.errors.append(check(
        report.total_turns == turn_count,
        f"report.total_turns ({report.total_turns}) != actual ({turn_count})"
    ))
    done_valid.errors.append(check(
        report.total_turns > 0,
        f"simulation produced 0 turns for {result.case_name}"
    ))
    done_valid.errors.append(check(
        report.final_state,
        f"final_state is empty"
    ))
    done_valid.details = {
        "total_turns": report.total_turns,
        "final_state": report.final_state,
        "asr_exact_match_rate": round(report.asr_exact_match_rate, 4),
        "avg_cer": round(report.avg_cer, 4),
        "committed_time": report.committed_time,
        "conversation_ended": report.conversation_ended,
    }

    # --- 检查状态递进 ---
    if len(set(states_seen)) < 2 and turn_count > 1:
        done_valid.warnings.append(
            f"State never changed: {states_seen}"
        )

    done_valid.errors = [e for e in done_valid.errors if e]
    done_valid.passed = len(done_valid.errors) == 0
    result.done_valid = done_valid

    # ---- 序列级验证 ----
    if turn_count == 0:
        result.sequence_errors.append("No turns produced")

    # 检查状态是否合理递进（不应该卡在同一个状态太久）
    if len(states_seen) >= 3:
        max_consecutive = 1
        current_consecutive = 1
        for i in range(1, len(states_seen)):
            if states_seen[i] == states_seen[i - 1]:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        if max_consecutive >= 4:
            result.sequence_errors.append(
                f"State stuck for {max_consecutive} consecutive turns: {states_seen}"
            )

    result.total_duration = round(time.time() - start_time, 2)

    # 汇总通过状态
    all_ok = (
        result.greeting_valid.passed
        and result.greeting_audio_valid.passed
        and all(t.passed for t in result.turn_validations)
        and result.done_valid.passed
        and len(result.sequence_errors) == 0
    )
    result.passed = all_ok

    return result, events


# ---------------------------------------------------------------------------
# 翻译测试
# ---------------------------------------------------------------------------

async def test_translation():
    """验证本地翻译功能可用。"""
    print("\n" + "=" * 70)
    print("Translation Test")
    print("=" * 70)

    try:
        translator = get_translator()
    except Exception as e:
        print(f"  FAIL: Translator not available: {e}")
        return False

    test_cases = [
        ("Selamat siang, Pak. Ada yang bisa saya bantu?", "id", "en"),
        ("Saya sedang sibuk, tidak bisa bicara sekarang.", "id", "en"),
        ("Baik, saya akan bayar minggu depan.", "id", "en"),
    ]

    all_ok = True
    for text, src, tgt in test_cases:
        try:
            result = translator.translate(text, source_lang=src, target_lang=tgt)
            translated = result.translated_text if result.success else ""
            ok = bool(translated and len(translated) > 0 and translated != text)
            status = "PASS" if ok else "WARN"
            if not ok:
                all_ok = False
            print(f"  {status} [{src}→{tgt}] '{text[:50]}...' → '{translated[:50] if translated else 'EMPTY'}...'")
        except Exception as e:
            print(f"  FAIL [{src}→{tgt}] '{text[:50]}...': {e}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# 批量运行
# ---------------------------------------------------------------------------

TEST_MATRIX = [
    # (persona, resistance, chat_group, description)
    ("cooperative", "low", "H2", "标准合作客户"),
    ("busy", "medium", "H1", "忙碌客户 + 中等抗拒"),
    ("resistant", "high", "S0", "高抗拒客户"),
    ("negotiating", "low", "H2", "谈判型客户"),
    ("excuse_master", "medium", "H1", "借口大师"),
    ("forgetful", "very_high", "S0", "健忘客户 + 极高抗拒"),
]


async def main():
    print("=" * 70)
    print("Auto Mode End-to-End Test Suite")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ---- 翻译测试 ----
    translation_ok = await test_translation()

    # ---- SSE 仿真测试 ----
    all_results: List[CaseResult] = []

    for persona, resistance, group, desc in TEST_MATRIX:
        case_label = f"{persona}/{resistance}/{group}"
        print(f"\n{'─' * 70}")
        print(f"Testing: {case_label} ({desc})")
        print(f"{'─' * 70}")

        try:
            result, events = await run_single_simulation(
                persona=persona,
                resistance=resistance,
                chat_group=group,
                customer_name="Pak Budi",
                max_turns=8,
                asr_model="tiny",
            )
            all_results.append(result)
        except Exception as e:
            import traceback
            print(f"  EXCEPTION: {e}")
            traceback.print_exc()
            result = CaseResult(
                case_name=case_label,
                persona=persona,
                resistance=resistance,
                chat_group=group,
                passed=False,
            )
            result.sequence_errors.append(f"Unhandled exception: {e}")
            all_results.append(result)
            continue

        # ---- 即时输出 ----
        status = "✓ PASS" if result.passed else "✗ FAIL"
        print(f"\n  Result: {status}")
        print(f"  Duration: {result.total_duration}s")
        print(f"  Turns: {result.total_turns}")

        # greeting
        g = result.greeting_valid
        if g:
            print(f"  greeting: {'✓' if g.passed else '✗'} agent_text='{g.details.get('agent_text', '')[:60]}...'")
            for e in g.errors:
                print(f"    ERROR: {e}")

        # greeting_audio
        ga = result.greeting_audio_valid
        if ga:
            print(f"  greeting_audio: {'✓' if ga.passed else '✗'} file_exists={ga.details.get('file_exists')}")
            for e in ga.errors:
                print(f"    ERROR: {e}")

        # turns
        for tv in result.turn_validations:
            icon = "✓" if tv.passed else "✗"
            d = tv.details
            print(f"  {tv.event_type}: {icon} "
                  f"cust='{d.get('customer_text', '')[:50]}...' "
                  f"agent='{d.get('agent_text', '')[:50]}...' "
                  f"t={d.get('total_time', 0)}s "
                  f"cust_audio={d.get('customer_audio_ok')} "
                  f"agent_audio={d.get('agent_audio_ok')}")
            for e in tv.errors:
                print(f"    ERROR: {e}")
            for w in tv.warnings:
                print(f"    WARN: {w}")

        # done
        d = result.done_valid
        if d:
            print(f"  done: {'✓' if d.passed else '✗'} "
                  f"final_state={d.details.get('final_state')} "
                  f"ended={d.details.get('conversation_ended')}")
            for e in d.errors:
                print(f"    ERROR: {e}")
            for w in d.warnings:
                print(f"    WARN: {w}")

        # sequence
        for e in result.sequence_errors:
            print(f"  SEQUENCE ERROR: {e}")

    # ---- 汇总报告 ----
    print("\n")
    print("=" * 70)
    print("SUMMARY REPORT")
    print("=" * 70)

    total_cases = len(all_results)
    passed_cases = sum(1 for r in all_results if r.passed)
    total_turns = sum(r.total_turns for r in all_results)
    total_errors = 0
    total_warnings = 0

    for r in all_results:
        if r.greeting_valid:
            total_errors += len(r.greeting_valid.errors)
            total_warnings += len(r.greeting_valid.warnings)
        if r.greeting_audio_valid:
            total_errors += len(r.greeting_audio_valid.errors)
            total_warnings += len(r.greeting_audio_valid.warnings)
        for tv in r.turn_validations:
            total_errors += len(tv.errors)
            total_warnings += len(tv.warnings)
        if r.done_valid:
            total_errors += len(r.done_valid.errors)
            total_warnings += len(r.done_valid.warnings)
        total_errors += len(r.sequence_errors)

    print(f"\n  Translation: {'✓ PASS' if translation_ok else '✗ FAIL'}")
    print(f"  Cases: {passed_cases}/{total_cases} passed")
    print(f"  Total turns across all cases: {total_turns}")
    print(f"  Total errors: {total_errors}")
    print(f"  Total warnings: {total_warnings}")

    # ---- 检查关键断言 ----
    print(f"\n  Key Checks:")
    all_have_customer_text = all(
        tv.passed
        for r in all_results
        for tv in r.turn_validations
        if "customer_text is empty" not in str(tv.errors)
    )
    customer_text_empty_count = sum(
        1 for r in all_results
        for tv in r.turn_validations
        if any("customer_text" in e for e in tv.errors)
    )
    print(f"    Customer text non-empty: "
          f"{'✓' if customer_text_empty_count == 0 else f'✗ ({customer_text_empty_count} turns with empty customer_text)'}")

    agent_text_empty_count = sum(
        1 for r in all_results
        for tv in r.turn_validations
        if any("agent_text" in e for e in tv.errors)
    )
    print(f"    Agent text non-empty: "
          f"{'✓' if agent_text_empty_count == 0 else f'✗ ({agent_text_empty_count} turns with empty agent_text)'}")

    zero_turn_cases = sum(1 for r in all_results if r.total_turns == 0)
    print(f"    At least 1 turn per case: "
          f"{'✓' if zero_turn_cases == 0 else f'✗ ({zero_turn_cases} cases with 0 turns)'}")

    # ---- 详细输出到 JSON ----
    report_path = Path("data/test_reports")
    report_path.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = report_path / f"auto_mode_e2e_{timestamp}.json"

    report_data = {
        "timestamp": timestamp,
        "translation_ok": translation_ok,
        "summary": {
            "total_cases": total_cases,
            "passed_cases": passed_cases,
            "total_turns": total_turns,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
        "cases": [],
    }

    for r in all_results:
        case_data = {
            "case_name": r.case_name,
            "passed": r.passed,
            "total_turns": r.total_turns,
            "total_duration": r.total_duration,
            "greeting": None,
            "greeting_audio": None,
            "turns": [],
            "done": None,
            "sequence_errors": r.sequence_errors,
        }

        if r.greeting_valid:
            case_data["greeting"] = {
                "passed": r.greeting_valid.passed,
                "errors": r.greeting_valid.errors,
                "details": {k: str(v) for k, v in r.greeting_valid.details.items()},
            }
        if r.greeting_audio_valid:
            case_data["greeting_audio"] = {
                "passed": r.greeting_audio_valid.passed,
                "errors": r.greeting_audio_valid.errors,
                "details": {k: str(v) for k, v in r.greeting_audio_valid.details.items()},
            }
        for tv in r.turn_validations:
            case_data["turns"].append({
                "event_type": tv.event_type,
                "passed": tv.passed,
                "errors": tv.errors,
                "warnings": tv.warnings,
                "details": {k: str(v) for k, v in tv.details.items()},
            })
        if r.done_valid:
            case_data["done"] = {
                "passed": r.done_valid.passed,
                "errors": r.done_valid.errors,
                "warnings": r.done_valid.warnings,
                "details": {k: str(v) for k, v in r.done_valid.details.items()},
            }

        report_data["cases"].append(case_data)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print(f"\n  Detailed report saved to: {json_path}")

    # ---- 退出码 ----
    if passed_cases == total_cases and translation_ok:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {total_cases - passed_cases} CASE(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = aio.run(main())
    sys.exit(exit_code)
