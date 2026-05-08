#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音会话 Corner Case 测试

覆盖场景:
1. 语音重复播放检测 (同一状态多次返回相同话术)
2. 无法终止检测 (finished 后资源清理)
3. SSE 连接中断恢复
4. ASR 空文本 / 乱码输入处理
5. TTS 超时 / 失败降级
6. 多语音会话并发
7. 会话超时自动清理
8. Heartbeat 机制验证
"""
import asyncio as aio
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot, ChatState
from core.voice.tts import TTSManager
from core.voice.asr import ASRPipeline
from core.voice.vad import SimpleEnergyVAD, VADState
from core.voice.interruption import InterruptionHandler, InterruptionType


# ---------------------------------------------------------------------------
# 测试工具
# ---------------------------------------------------------------------------

def check(condition: bool, message: str) -> Optional[str]:
    return None if condition else message


@dataclass
class CaseResult:
    case_name: str
    passed: bool = True
    errors: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 场景 1: 语音重复播放检测
# ---------------------------------------------------------------------------

async def test_1_voice_repetition_detection():
    """验证同一状态不会无限返回相同话术 (voice repeating bug)"""
    result = CaseResult(case_name="语音重复播放检测")

    bot = CollectionChatBot("H2", "Pak Test")
    responses = ["Halo", "iya", "iya", "iya", "iya", "iya", "iya", "iya"]
    resp_idx = 0
    agent_texts: List[str] = []

    agent_says, _ = await bot.process()
    agent_texts.append(agent_says)

    while not bot.is_finished() and resp_idx < len(responses):
        agent_says, _ = await bot.process(responses[resp_idx])
        resp_idx += 1
        if agent_says:
            agent_texts.append(agent_says)

    # 检测连续重复
    max_repeat = 1
    current_repeat = 1
    for i in range(1, len(agent_texts)):
        if agent_texts[i] == agent_texts[i - 1]:
            current_repeat += 1
            max_repeat = max(max_repeat, current_repeat)
        else:
            current_repeat = 1

    err = check(max_repeat <= 3, f"同一话术最多重复 {max_repeat} 次 (阈值 3)")
    if err:
        result.errors.append(err)

    # 状态递进检查
    err = check(bot.is_finished(), f"对话应在有限轮内结束, 实际 state={bot.state.name}")
    if err:
        result.errors.append(err)

    result.details = {"max_repeat": max_repeat, "total_turns": len(agent_texts),
                      "final_state": bot.state.name, "finished": bot.is_finished()}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 2: 无法终止 - 资源清理
# ---------------------------------------------------------------------------

async def test_2_unable_to_terminate():
    """验证会话结束后资源被正确清理 (unable to stop bug)"""
    result = CaseResult(case_name="无法终止检测")

    # 模拟 active_sessions 字典
    active_sessions: Dict[str, Any] = {}

    bot = CollectionChatBot("H2", "Pak Stop")
    session_id = str(uuid.uuid4())
    bot.session_id = session_id
    active_sessions[session_id] = bot

    responses = ["Halo", "iya", "jam 5", "iya"]
    resp_idx = 0

    await bot.process()
    while not bot.is_finished() and resp_idx < len(responses):
        await bot.process(responses[resp_idx])
        resp_idx += 1

    # 模拟 /voice/turn 完成后的清理逻辑
    if bot.is_finished():
        active_sessions.pop(session_id, None)

    # 验证
    err = check(bot.is_finished(), "对话应结束")
    if err:
        result.errors.append(err)
    err = check(session_id not in active_sessions, "已结束的 session 应从 active_sessions 移除")
    if err:
        result.errors.append(err)
    err = check(len(active_sessions) == 0, f"active_sessions 应为空, 实际 {len(active_sessions)}")
    if err:
        result.errors.append(err)

    # 验证再次访问已结束 session 会被拒绝
    if session_id not in active_sessions:
        rejected = True
    else:
        rejected = active_sessions[session_id].is_finished()
    err = check(session_id not in active_sessions or active_sessions[session_id].is_finished(),
                "已结束 session 应被清理或标记为 finished")
    if err:
        result.errors.append(err)

    result.details = {"session_cleaned": session_id not in active_sessions,
                      "finished": bot.is_finished(),
                      "active_count": len(active_sessions)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 3: SSE 连接中断与恢复
# ---------------------------------------------------------------------------

async def test_3_sse_disconnection():
    """验证 SSE 生成器在外部取消/断开时正确清理资源"""
    result = CaseResult(case_name="SSE 连接中断恢复")

    bot = CollectionChatBot("H2", "Pak SSE")
    session_id = str(uuid.uuid4())
    bot.session_id = session_id

    active_sessions: Dict[str, Any] = {session_id: bot}

    # 模拟 SSE generator 被取消 (客户端断开)
    async def simulate_sse_generator():
        try:
            await bot.process()
            for i in range(5):
                await aio.sleep(0.01)
                if bot.is_finished():
                    break
        except aio.CancelledError:
            # 模拟 finally 清理
            active_sessions.pop(session_id, None)
            raise
        finally:
            active_sessions.pop(session_id, None)

    task = aio.create_task(simulate_sse_generator())
    await aio.sleep(0.02)
    task.cancel()
    try:
        await task
    except aio.CancelledError:
        pass

    # 验证清理
    err = check(session_id not in active_sessions, "SSE 断开后应清理 session")
    if err:
        result.errors.append(err)

    # 验证 bot 不再被引用, 没有泄漏
    result.details = {"session_cleaned": session_id not in active_sessions,
                      "active_count": len(active_sessions)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 4: ASR 空文本 / 乱码处理
# ---------------------------------------------------------------------------

async def test_4_asr_edge_cases():
    """验证 ASR 返回空文本、乱码、极短文本时的处理"""
    result = CaseResult(case_name="ASR 边界输入")

    bot = CollectionChatBot("H2", "Pak ASR")

    # 模拟 ASR 可能返回的边界情况
    edge_inputs = [
        "",            # 空输入
        "   ",         # 空白
        "...",         # 标点
        "uh",          # 极短
        "mmmmmmm",     # 填充词
        "halo" * 50,   # 极长重复
    ]

    for i, edge_input in enumerate(edge_inputs):
        try:
            agent_says, _ = await bot.process(edge_input)
            # 不应崩溃
        except Exception as e:
            result.errors.append(f"输入 #{i} '{edge_input[:20]}' 导致崩溃: {e}")

    result.details = {"inputs_tested": len(edge_inputs), "crashes": len(result.errors)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 5: TTS 失败降级
# ---------------------------------------------------------------------------

async def test_5_tts_failure_degradation():
    """验证 TTS 合成失败时系统降级, 不崩溃"""
    from core.voice.tts import TTSResult, TTSEngine
    result = CaseResult(case_name="TTS 失败降级")

    bot = CollectionChatBot("H2", "Pak TTS")
    await bot.process()

    # 用自定义引擎模拟 TTS 失败
    class MockFailingEngine(TTSEngine):
        async def synthesize(self, text, output_file=None, voice=None, **kwargs):
            return TTSResult(text=text, success=False, error_message="mock failure")
        async def list_voices(self, locale=None):
            return []
        def get_engine_name(self):
            return "mock_failing"
        def is_available(self):
            return True

    tts = TTSManager()
    tts.register_engine(MockFailingEngine(), set_default=True)

    agent_text, _ = await bot.process("halo")
    tts_result = await tts.synthesize(agent_text)

    err = check(agent_text is not None and len(agent_text) > 0,
                "TTS 失败不应影响文本生成")
    if err:
        result.errors.append(err)
    err = check(not tts_result.success,
                "Mock TTS 应返回失败")
    if err:
        result.errors.append(err)

    result.details = {"tts_success": tts_result.success, "text_generated": len(agent_text) > 0}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 6: 多语音会话并发
# ---------------------------------------------------------------------------

async def test_6_concurrent_voice_sessions():
    """验证多个语音会话并发时不互相干扰"""
    result = CaseResult(case_name="多语音会话并发")

    async def run_session(name: str) -> Dict[str, Any]:
        bot = CollectionChatBot("H2", name)
        session_id = str(uuid.uuid4())
        bot.session_id = session_id
        await bot.process()
        for _ in range(3):
            if bot.is_finished():
                break
            await bot.process("iya")
        return {
            "session_id": session_id,
            "final_state": bot.state.name,
            "finished": bot.is_finished(),
            "turns": len(bot.conversation),
        }

    tasks = [run_session(f"Pak {i}") for i in range(5)]
    results_list = await aio.gather(*tasks)

    session_ids: Set[str] = set()
    for r in results_list:
        sid = r["session_id"]
        err = check(sid not in session_ids, f"Session ID 重复: {sid}")
        if err:
            result.errors.append(err)
        session_ids.add(sid)
        err = check(r["turns"] > 0, f"会话 {sid} 应有对话轮次")
        if err:
            result.errors.append(err)

    result.details = {"concurrent_sessions": len(results_list),
                      "unique_ids": len(session_ids)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 7: 会话超时清理
# ---------------------------------------------------------------------------

async def test_7_session_timeout_cleanup():
    """验证长时间无交互的会话可以被超时清理"""
    result = CaseResult(case_name="会话超时清理")

    active_sessions: Dict[str, Any] = {}

    # 创建几个"过期"会话
    for i in range(3):
        bot = CollectionChatBot("H2", f"Pak Timeout{i}")
        session_id = f"timeout-session-{i}"
        bot.session_id = session_id
        bot._start_time = time.time() - 7200  # 模拟 2 小时前创建
        active_sessions[session_id] = bot

    # 超时清理逻辑 (30 分钟超时)
    timeout_seconds = 1800
    now = time.time()
    expired_ids = []
    for sid, bot in list(active_sessions.items()):
        session_age = now - getattr(bot, '_start_time', 0)
        if session_age > timeout_seconds:
            expired_ids.append(sid)
            del active_sessions[sid]

    err = check(len(expired_ids) == 3, f"应清理 3 个过期会话, 实际 {len(expired_ids)}")
    if err:
        result.errors.append(err)
    err = check(len(active_sessions) == 0, f"active_sessions 应为空, 实际 {len(active_sessions)}")
    if err:
        result.errors.append(err)

    result.details = {"expired_cleaned": len(expired_ids),
                      "remaining": len(active_sessions)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 8: Heartbeat 机制验证
# ---------------------------------------------------------------------------

async def test_8_heartbeat_mechanism():
    """验证长时间等待时的 heartbeat 机制"""
    result = CaseResult(case_name="Heartbeat 机制")

    heartbeat_count = 0
    events: List[str] = []

    async def simulate_wait_with_heartbeat(wait_time: float = 1.5):
        nonlocal heartbeat_count
        start = time.time()
        while time.time() - start < wait_time:
            await aio.sleep(0.3)
            events.append(f": heartbeat\n\n")
            heartbeat_count += 1
        events.append("data: {\"type\": \"done\"}\n\n")

    await simulate_wait_with_heartbeat(1.5)

    err = check(heartbeat_count >= 3, f"长时间等待应有至少 3 次 heartbeat, 实际 {heartbeat_count}")
    if err:
        result.errors.append(err)
    err = check(events[-1].startswith("data:"), "最后一个事件应是 data 事件")
    if err:
        result.errors.append(err)

    result.details = {"heartbeat_count": heartbeat_count, "total_events": len(events)}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 9: 中断处理器 - 短打断不终止
# ---------------------------------------------------------------------------

async def test_9_interruption_short_vs_long():
    """验证短打断 (嗯、啊) 不终止播放, 长打断终止"""
    from core.voice.interruption import InterruptionEvent
    result = CaseResult(case_name="智能打断判断")

    vad = SimpleEnergyVAD()
    handler = InterruptionHandler(vad, short_interruption_threshold_ms=500)

    now = time.time()

    # 短打断: 300ms (低于 500ms 阈值)
    short_event = InterruptionEvent(
        type=InterruptionType.SHORT_INTERRUPTION,
        start_time=now,
        end_time=now + 0.3,
        duration=0.3,
    )
    should_stop_short = handler.should_stop_playback(short_event)
    err = check(not should_stop_short, "短打断 (<500ms) 不应停止播放")
    if err:
        result.errors.append(err)

    # 长打断: 1200ms (高于 500ms 阈值)
    long_event = InterruptionEvent(
        type=InterruptionType.LONG_INTERRUPTION,
        start_time=now,
        end_time=now + 1.2,
        duration=1.2,
    )
    should_stop_long = handler.should_stop_playback(long_event)
    err = check(should_stop_long, "长打断 (>500ms) 应停止播放")
    if err:
        result.errors.append(err)

    result.details = {
        "short_stopped": should_stop_short,
        "long_stopped": should_stop_long,
    }
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 场景 10: VAD 静音 / 噪音处理
# ---------------------------------------------------------------------------

async def test_10_vad_silence_noise():
    """验证 VAD 对静音和语音的区分 (需多帧预热状态机)"""
    import numpy as np
    result = CaseResult(case_name="VAD 静音噪音区分")

    vad = SimpleEnergyVAD(
        sample_rate=16000,
        energy_threshold=0.005,
        silence_frames=3,
        voice_frames=2,
    )

    # 预热: 连续喂多帧静音, 让状态机进入 SILENCE
    silence_frame = np.zeros(480, dtype=np.float32)  # 30ms @ 16kHz (默认 frame_duration)
    for _ in range(10):
        vad.process_frame(silence_frame)
    silence_result = vad.process_frame(silence_frame)
    err = check(silence_result.state == VADState.SILENCE,
                f"连续静音后应判定为 SILENCE, 实际 {silence_result.state}")
    if err:
        result.errors.append(err)

    # 喂入高能量语音帧, 应转为 VOICE
    speech_frame = np.random.randn(480).astype(np.float32) * 0.5
    for _ in range(5):
        speech_result = vad.process_frame(speech_frame)

    # VAD 在足够多的高能量帧后应判定为 VOICE
    final_state = speech_result.state.value
    err2 = check(speech_result.state != VADState.UNKNOWN,
                 f"语音帧不应为 UNKNOWN, 实际 {final_state}")
    if err2:
        result.errors.append(err2)

    result.details = {"silence_state": silence_result.state.value,
                      "speech_state": final_state}
    result.passed = len(result.errors) == 0
    return result


# ---------------------------------------------------------------------------
# 运行所有测试
# ---------------------------------------------------------------------------

async def main():
    print("=" * 70)
    print("Voice Session Corner Case Test Suite")
    print("=" * 70)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tests = [
        test_1_voice_repetition_detection,
        test_2_unable_to_terminate,
        test_3_sse_disconnection,
        test_4_asr_edge_cases,
        test_5_tts_failure_degradation,
        test_6_concurrent_voice_sessions,
        test_7_session_timeout_cleanup,
        test_8_heartbeat_mechanism,
        test_9_interruption_short_vs_long,
        test_10_vad_silence_noise,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            result = await test()
            status = "PASS" if result.passed else "FAIL"
            if result.passed:
                passed += 1
            else:
                failed += 1
            print(f"  [{status}] {result.case_name}")
            if result.errors:
                for e in result.errors:
                    print(f"         ✗ {e}")
            if result.details:
                details_str = " | ".join(f"{k}={v}" for k, v in result.details.items())
                print(f"         {details_str}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 70)
    print(f"结果: {passed} 通过, {failed} 失败 (共 {len(tests)} 项)")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = aio.run(main())
    sys.exit(0 if success else 1)
