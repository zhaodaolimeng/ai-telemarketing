#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端多模态语音仿真测试工具
支持口音、噪音场景模拟，统计ASR准确率、响应延迟、打断准确率等语音链路指标
"""
import asyncio
import json
import random
import time
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.chatbot import CollectionChatBot
from core.compliance_checker import get_compliance_checker

# 模拟ASR服务接口，实际使用时替换成真实的ASR客户端
class MockASRClient:
    """模拟ASR服务"""
    def __init__(self):
        # 不同口音的识别准确率
        self.accent_accuracy = {
            "standard": 0.95,  # 标准印尼语
            "javanese": 0.85,  # 爪哇口音
            "sundanese": 0.82,  # 巽他口音
            "balinese": 0.78,  # 巴厘口音
            "papuan": 0.75,  # 巴布亚口音
            "chinese": 0.70,  # 华裔口音
        }
        # 不同噪音类型的影响因子
        self.noise_impact = {
            "quiet": 1.0,  # 安静环境
            "traffic": 0.8,  # 交通噪音
            "crowd": 0.7,  # 人群噪音
            "wind": 0.75,  # 风噪
            "music": 0.85,  # 背景音乐
            "echo": 0.65,  # 回声
        }

    async def transcribe(self, audio_path: str, accent: str = "standard", noise_type: str = "quiet") -> Tuple[str, float, float]:
        """
        模拟语音转文本
        返回: (转写文本, 识别准确率, 处理延迟秒数)
        """
        # 模拟处理延迟
        latency = random.uniform(0.5, 2.0)
        await asyncio.sleep(latency)

        # 计算基础准确率
        base_accuracy = self.accent_accuracy.get(accent, 0.9)
        noise_factor = self.noise_impact.get(noise_type, 1.0)
        final_accuracy = base_accuracy * noise_factor

        # 模拟识别错误
        # 这里简化处理，实际应该根据准确率生成有错误的文本
        # 加载真实的音频文件后会替换成真实的ASR调用
        mock_texts = {
            "greeting": "Halo selamat pagi",
            "identity_confirm": "Ya saya adalah John Doe",
            "ask_payment": "Saya mau menanyakan tagihan saya",
            "negotiate": "Saya tidak punya uang, bisa perpanjang tidak?",
            "promise": "Oke saya akan bayar besok",
            "reject": "Saya tidak mau bayar, jangan telepon lagi",
            "busy": "Saya sedang rapat, nanti telepon kembali"
        }

        # 根据音频文件名判断内容，实际应该从音频元数据获取
        for key in mock_texts:
            if key in audio_path.lower():
                text = mock_texts[key]
                break
        else:
            text = "Iya ada apa?"

        return text, round(final_accuracy, 4), latency

# 模拟TTS服务接口
class MockTTSClient:
    """模拟TTS服务"""
    def __init__(self):
        self.voice_options = {
            "female": {"latency": 0.3, "naturalness": 0.92},
            "male": {"latency": 0.35, "naturalness": 0.9},
        }

    async def synthesize(self, text: str, voice: str = "female") -> Tuple[str, float, float]:
        """
        模拟文本转语音
        返回: (音频文件路径, 处理延迟秒数, 自然度评分)
        """
        latency = random.uniform(0.2, 1.0) + len(text) * 0.005
        await asyncio.sleep(latency)

        voice_config = self.voice_options.get(voice, self.voice_options["female"])
        naturalness = voice_config["naturalness"]
        audio_path = f"/tmp/tts_{hash(text)}.wav"

        return audio_path, latency, naturalness

@dataclass
class VoiceTestCase:
    """语音测试用例"""
    case_id: str
    audio_path: str
    expected_text: str
    user_accent: str
    background_noise: str
    expected_intent: str
    expected_stage: str
    interrupt_scenario: bool  # 是否是用户打断场景
    expected_response_requirements: str

@dataclass
class TurnResult:
    """单轮对话结果"""
    turn_number: int
    asr_input: str
    asr_expected: str
    asr_accuracy: float
    asr_latency: float
    bot_response: str
    bot_latency: float
    tts_output_path: str
    tts_latency: float
    tts_naturalness: float
    total_turn_latency: float
    is_correct: bool
    compliance_violations: List[Dict]
    interrupted: bool  # 是否发生了用户打断
    interrupt_handled_correctly: bool  # 打断处理是否正确

@dataclass
class SimulationResult:
    """仿真测试结果"""
    case_id: str
    success: bool
    total_turns: int
    completed_turns: int
    avg_asr_accuracy: float
    avg_turn_latency: float
    total_latency: float
    interrupt_count: int
    interrupt_success_rate: float
    compliance_violations: List[Dict]
    turn_results: List[TurnResult]
    scenario_type: str
    accent: str
    noise_type: str

@dataclass
class VoiceEvaluationResult:
    """语音测试评估结果"""
    total_cases: int
    success_rate: float
    avg_asr_accuracy: float
    avg_response_latency: float
    avg_turn_latency: float
    interrupt_success_rate: float
    compliance_violation_rate: float
    tts_naturalness_avg: float
    scenario_performance: Dict[str, Dict]
    accent_performance: Dict[str, Dict]
    noise_performance: Dict[str, Dict]
    error_analysis: Dict[str, int]

class VoiceSimulationTester:
    """多模态语音仿真测试器"""

    def __init__(self, test_cases_dir: str = "data/runs/voice_test_cases/"):
        self.test_cases_dir = Path(test_cases_dir)
        self.test_cases: List[VoiceTestCase] = []
        self.asr_client = MockASRClient()
        self.tts_client = MockTTSClient()
        self.compliance_checker = get_compliance_checker()

        self._load_test_cases()

    def _load_test_cases(self) -> None:
        """加载语音测试用例"""
        if not self.test_cases_dir.exists():
            print(f"警告：语音测试用例目录 {self.test_cases_dir} 不存在，请先准备测试用例")
            return

        for file_path in self.test_cases_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    case = VoiceTestCase(
                        case_id=data.get("case_id", file_path.stem),
                        audio_path=data.get("audio_path", ""),
                        expected_text=data.get("expected_text", ""),
                        user_accent=data.get("user_accent", "standard"),
                        background_noise=data.get("background_noise", "quiet"),
                        expected_intent=data.get("expected_intent", ""),
                        expected_stage=data.get("expected_stage", "greeting"),
                        interrupt_scenario=data.get("interrupt_scenario", False),
                        expected_response_requirements=data.get("expected_response_requirements", "")
                    )
                    self.test_cases.append(case)
            except Exception as e:
                print(f"加载语音测试用例 {file_path} 失败: {e}")

        print(f"成功加载 {len(self.test_cases)} 个语音测试用例")

    async def run_single_test(self, test_case: VoiceTestCase) -> SimulationResult:
        """运行单个语音测试用例"""
        print(f"运行语音测试用例: {test_case.case_id} (口音: {test_case.user_accent}, 噪音: {test_case.background_noise})")

        bot = CollectionChatBot(chat_group="H2")
        bot_state = None
        turn_results: List[TurnResult] = []
        total_turns = 0
        interrupt_count = 0
        interrupt_successes = 0
        all_violations = []
        success = True

        # 模拟完整对话流程
        conversation_flow = self._generate_conversation_flow(test_case)

        for turn_idx, turn_data in enumerate(conversation_flow, 1):
            total_turns += 1
            turn_start_time = time.time()

            # 1. ASR识别用户语音
            asr_start = time.time()
            asr_text, asr_accuracy, asr_latency = await self.asr_client.transcribe(
                turn_data["audio_path"],
                test_case.user_accent,
                test_case.background_noise
            )
            asr_end = time.time()

            # 模拟用户打断场景
            interrupted = test_case.interrupt_scenario and turn_idx == 2  # 假设第二轮打断
            interrupt_handled = False

            if interrupted:
                interrupt_count += 1
                # 检查机器人是否支持打断
                # 简化处理，实际应该检测机器人是否在用户说话时停止播放
                interrupt_handled = random.random() > 0.2  # 80%概率处理正确
                if interrupt_handled:
                    interrupt_successes += 1
                else:
                    success = False

            # 2. 机器人处理
            bot_start = time.time()
            try:
                bot_response, bot_state = await bot.process(asr_text, bot_state)
                bot_latency = time.time() - bot_start
            except Exception as e:
                print(f"机器人处理失败: {e}")
                bot_response = ""
                bot_latency = time.time() - bot_start
                success = False

            # 3. 合规检查
            is_compliant, violations = self.compliance_checker.check(bot_response)
            all_violations.extend(violations)
            if any(v["severity"] == "high" for v in violations):
                success = False

            # 4. TTS合成
            tts_start = time.time()
            tts_path, tts_latency, tts_naturalness = await self.tts_client.synthesize(bot_response)
            tts_end = time.time()

            # 计算总延迟
            total_turn_latency = time.time() - turn_start_time

            # 判断回复是否正确
            is_correct = self._evaluate_response_correctness(
                bot_response, turn_data["expected_response"], test_case.expected_stage
            )
            if not is_correct:
                success = False

            turn_result = TurnResult(
                turn_number=turn_idx,
                asr_input=asr_text,
                asr_expected=turn_data["expected_text"],
                asr_accuracy=asr_accuracy,
                asr_latency=asr_latency,
                bot_response=bot_response,
                bot_latency=bot_latency,
                tts_output_path=tts_path,
                tts_latency=tts_latency,
                tts_naturalness=tts_naturalness,
                total_turn_latency=total_turn_latency,
                is_correct=is_correct,
                compliance_violations=violations,
                interrupted=interrupted,
                interrupt_handled_correctly=interrupt_handled
            )
            turn_results.append(turn_result)

            # 对话结束判断
            if self._is_conversation_end(bot_response):
                break

        # 计算统计指标
        completed_turns = len(turn_results)
        avg_asr_accuracy = sum(t.asr_accuracy for t in turn_results) / completed_turns if completed_turns > 0 else 0.0
        avg_turn_latency = sum(t.total_turn_latency for t in turn_results) / completed_turns if completed_turns > 0 else 0.0
        total_latency = sum(t.total_turn_latency for t in turn_results)
        interrupt_success_rate = interrupt_successes / interrupt_count if interrupt_count > 0 else 1.0

        return SimulationResult(
            case_id=test_case.case_id,
            success=success,
            total_turns=total_turns,
            completed_turns=completed_turns,
            avg_asr_accuracy=avg_asr_accuracy,
            avg_turn_latency=avg_turn_latency,
            total_latency=total_latency,
            interrupt_count=interrupt_count,
            interrupt_success_rate=interrupt_success_rate,
            compliance_violations=all_violations,
            turn_results=turn_results,
            scenario_type=test_case.expected_stage,
            accent=test_case.user_accent,
            noise_type=test_case.background_noise
        )

    def _generate_conversation_flow(self, test_case: VoiceTestCase) -> List[Dict]:
        """生成完整的对话流程"""
        # 基础对话流程
        flow = [
            {
                "audio_path": "audio/greeting.wav",
                "expected_text": "Halo selamat pagi",
                "expected_response": "Halo selamat pagi, apakah saya bicara dengan Bapak?"
            },
            {
                "audio_path": test_case.audio_path,
                "expected_text": test_case.expected_text,
                "expected_response": test_case.expected_response_requirements
            }
        ]

        # 根据场景扩展对话
        if test_case.expected_stage == "negotiate":
            flow.extend([
                {
                    "audio_path": "audio/negotiate_1.wav",
                    "expected_text": "Saya tidak punya uang, bisa perpanjang tidak?",
                    "expected_response": "Tentu bisa Pak, berapa lama Bapak butuhkan?"
                },
                {
                    "audio_path": "audio/negotiate_2.wav",
                    "expected_text": "Saya butuh 2 minggu lagi",
                    "expected_response": "Baik Pak, kami berikan perpanjangan 2 minggu ya, tapi Bapak harus bayar denda 10% ya."
                }
            ])
        elif test_case.expected_stage == "push":
            flow.extend([
                {
                    "audio_path": "audio/push_1.wav",
                    "expected_text": "Saya belum bisa bayar sekarang",
                    "expected_response": "Pak, tagihan sudah jatuh tempo lebih dari 3 hari, jika tidak dibayar hari ini akan ada denda tambahan ya."
                }
            ])

        return flow

    def _evaluate_response_correctness(self, actual_response: str, expected_requirements: str, stage: str) -> bool:
        """评估机器人回复是否正确"""
        if not actual_response:
            return False

        actual_lower = actual_response.lower()

        # 按阶段检查关键内容
        stage_requirements = {
            "greeting": ["halo", "selamat", "pagi", "siang", "sore", "bapak", "ibu"],
            "identity": ["nama saya", "dari", "extra", "apakah benar", "konfirmasi"],
            "purpose": ["tagihan", "pinjaman", "hutang", "jatuh tempo", "pembayaran"],
            "ask_time": ["kapan", "tanggal", "jam", "bisa bayar", "waktu"],
            "push": ["segera", "hari ini", "batas waktu", "denda", "konsekuensi"],
            "negotiate": ["bisa", "coba", "bagaimana", "mengerti", "perpanjang", "cicil"],
            "commit": ["oke", "ya", "baik", "terima kasih", "kami tunggu", "janji"],
            "close": ["terima kasih", "selamat tinggal", "sampai jumpa"]
        }

        required_keywords = stage_requirements.get(stage, [])
        if required_keywords:
            has_required = any(kw in actual_lower for kw in required_keywords)
            if not has_required:
                return False

        # 检查是否包含禁止内容
        forbidden_keywords = ["kamu bodoh", "ancam akan datang kerumah", "hubungi keluarga", "polisi"]
        if any(kw in actual_lower for kw in forbidden_keywords):
            return False

        return True

    def _is_conversation_end(self, response: str) -> bool:
        """判断对话是否结束"""
        end_keywords = ["terima kasih", "selamat tinggal", "saya tutup", "sampai jumpa", "bye"]
        response_lower = response.lower().strip()
        return any(kw in response_lower for kw in end_keywords)

    async def run_all_tests(self, sample_size: Optional[int] = None) -> Tuple[List[SimulationResult], VoiceEvaluationResult]:
        """运行所有语音测试用例"""
        if not self.test_cases:
            print("没有可用的语音测试用例，请先准备测试数据")
            return [], None

        cases = self.test_cases[:sample_size] if sample_size else self.test_cases
        print(f"开始运行 {len(cases)} 个语音仿真测试用例...")

        results = []
        for i, case in enumerate(cases, 1):
            if i % 10 == 0:
                print(f"已处理 {i}/{len(cases)} 个用例")
            result = await self.run_single_test(case)
            results.append(result)

        # 计算评估指标
        eval_result = self._calculate_evaluation_metrics(results)

        return results, eval_result

    def _calculate_evaluation_metrics(self, results: List[SimulationResult]) -> VoiceEvaluationResult:
        """计算语音测试的评估指标"""
        total_cases = len(results)
        if total_cases == 0:
            return None

        # 基础指标
        successful_cases = sum(1 for r in results if r.success)
        success_rate = successful_cases / total_cases

        total_asr_accuracy = sum(r.avg_asr_accuracy for r in results)
        avg_asr_accuracy = total_asr_accuracy / total_cases

        total_response_latency = sum(sum(t.bot_latency for t in r.turn_results) for r in results)
        total_turns = sum(r.completed_turns for r in results)
        avg_response_latency = total_response_latency / total_turns if total_turns > 0 else 0

        total_turn_latency = sum(r.avg_turn_latency for r in results)
        avg_turn_latency = total_turn_latency / total_cases

        total_interrupt_success = sum(r.interrupt_success_rate for r in results if r.interrupt_count > 0)
        interrupt_cases = sum(1 for r in results if r.interrupt_count > 0)
        interrupt_success_rate = total_interrupt_success / interrupt_cases if interrupt_cases > 0 else 1.0

        total_violation_cases = sum(1 for r in results if r.compliance_violations)
        compliance_violation_rate = total_violation_cases / total_cases

        total_tts_naturalness = sum(sum(t.tts_naturalness for t in r.turn_results) for r in results)
        tts_naturalness_avg = total_tts_naturalness / total_turns if total_turns > 0 else 0

        # 场景性能统计
        scenario_stats = {}
        accent_stats = {}
        noise_stats = {}
        error_stats = defaultdict(int)

        for result in results:
            # 按场景
            scenario = result.scenario_type
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {"total": 0, "success": 0, "avg_asr": 0.0, "avg_latency": 0.0}
            scenario_stats[scenario]["total"] += 1
            if result.success:
                scenario_stats[scenario]["success"] += 1
            scenario_stats[scenario]["avg_asr"] += result.avg_asr_accuracy
            scenario_stats[scenario]["avg_latency"] += result.avg_turn_latency

            # 按口音
            accent = result.accent
            if accent not in accent_stats:
                accent_stats[accent] = {"total": 0, "success": 0, "avg_asr": 0.0, "avg_latency": 0.0}
            accent_stats[accent]["total"] += 1
            if result.success:
                accent_stats[accent]["success"] += 1
            accent_stats[accent]["avg_asr"] += result.avg_asr_accuracy
            accent_stats[accent]["avg_latency"] += result.avg_turn_latency

            # 按噪音
            noise = result.noise_type
            if noise not in noise_stats:
                noise_stats[noise] = {"total": 0, "success": 0, "avg_asr": 0.0, "avg_latency": 0.0}
            noise_stats[noise]["total"] += 1
            if result.success:
                noise_stats[noise]["success"] += 1
            noise_stats[noise]["avg_asr"] += result.avg_asr_accuracy
            noise_stats[noise]["avg_latency"] += result.avg_turn_latency

            # 错误分析
            if not result.success:
                # 识别错误
                if result.avg_asr_accuracy < 0.7:
                    error_stats["asr_recognition_error"] += 1
                # 响应延迟过高
                if result.avg_turn_latency > 3.0:
                    error_stats["high_latency"] += 1
                # 打断处理失败
                if result.interrupt_count > 0 and result.interrupt_success_rate < 0.5:
                    error_stats["interrupt_handling_failure"] += 1
                # 合规违规
                if result.compliance_violations:
                    error_stats["compliance_violation"] += 1
                # 回复内容错误
                if any(not t.is_correct for t in result.turn_results):
                    error_stats["response_content_error"] += 1

        # 计算平均值
        for scenario in scenario_stats:
            data = scenario_stats[scenario]
            data["success_rate"] = data["success"] / data["total"] if data["total"] > 0 else 0
            data["avg_asr"] = data["avg_asr"] / data["total"] if data["total"] > 0 else 0
            data["avg_latency"] = data["avg_latency"] / data["total"] if data["total"] > 0 else 0

        for accent in accent_stats:
            data = accent_stats[accent]
            data["success_rate"] = data["success"] / data["total"] if data["total"] > 0 else 0
            data["avg_asr"] = data["avg_asr"] / data["total"] if data["total"] > 0 else 0
            data["avg_latency"] = data["avg_latency"] / data["total"] if data["total"] > 0 else 0

        for noise in noise_stats:
            data = noise_stats[noise]
            data["success_rate"] = data["success"] / data["total"] if data["total"] > 0 else 0
            data["avg_asr"] = data["avg_asr"] / data["total"] if data["total"] > 0 else 0
            data["avg_latency"] = data["avg_latency"] / data["total"] if data["total"] > 0 else 0

        return VoiceEvaluationResult(
            total_cases=total_cases,
            success_rate=round(success_rate, 4),
            avg_asr_accuracy=round(avg_asr_accuracy, 4),
            avg_response_latency=round(avg_response_latency, 2),
            avg_turn_latency=round(avg_turn_latency, 2),
            interrupt_success_rate=round(interrupt_success_rate, 4),
            compliance_violation_rate=round(compliance_violation_rate, 4),
            tts_naturalness_avg=round(tts_naturalness_avg, 4),
            scenario_performance=scenario_stats,
            accent_performance=accent_stats,
            noise_performance=noise_stats,
            error_analysis=dict(error_stats)
        )

    def generate_report(self, results: List[SimulationResult], eval_result: VoiceEvaluationResult, output_dir: str = "data/outputs/voice_simulation_reports/") -> str:
        """生成语音仿真测试报告"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 生成JSON报告
        json_file = output_path / f"voice_simulation_{timestamp}.json"
        report_data = {
            "summary": {
                "total_cases": eval_result.total_cases,
                "success_rate": eval_result.success_rate,
                "avg_asr_accuracy": eval_result.avg_asr_accuracy,
                "avg_response_latency": eval_result.avg_response_latency,
                "avg_turn_latency": eval_result.avg_turn_latency,
                "interrupt_success_rate": eval_result.interrupt_success_rate,
                "compliance_violation_rate": eval_result.compliance_violation_rate,
                "tts_naturalness_avg": eval_result.tts_naturalness_avg
            },
            "scenario_performance": eval_result.scenario_performance,
            "accent_performance": eval_result.accent_performance,
            "noise_performance": eval_result.noise_performance,
            "error_analysis": eval_result.error_analysis
        }

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        # 生成Markdown报告
        md_file = output_path / f"voice_simulation_{timestamp}.md"

        md_content = f"""# 多模态语音仿真测试报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试用例数: {eval_result.total_cases}

## 📊 核心指标
| 指标 | 数值 | 合格标准 | 结果 |
|------|------|----------|------|
| 整体成功率 | {eval_result.success_rate*100:.1f}% | ≥90% | {'✅ 合格' if eval_result.success_rate >= 0.9 else '❌ 不合格'} |
| 平均ASR识别准确率 | {eval_result.avg_asr_accuracy*100:.1f}% | ≥85% | {'✅ 合格' if eval_result.avg_asr_accuracy >= 0.85 else '❌ 不合格'} |
| 平均机器人响应延迟 | {eval_result.avg_response_latency:.2f}s | ≤1.5s | {'✅ 合格' if eval_result.avg_response_latency <= 1.5 else '❌ 不合格'} |
| 平均单轮对话延迟 | {eval_result.avg_turn_latency:.2f}s | ≤3.0s | {'✅ 合格' if eval_result.avg_turn_latency <= 3.0 else '❌ 不合格'} |
| 用户打断处理成功率 | {eval_result.interrupt_success_rate*100:.1f}% | ≥90% | {'✅ 合格' if eval_result.interrupt_success_rate >= 0.9 else '❌ 不合格'} |
| 合规违规率 | {eval_result.compliance_violation_rate*100:.1f}% | ≤5% | {'✅ 合格' if eval_result.compliance_violation_rate <= 0.05 else '❌ 不合格'} |
| TTS语音自然度 | {eval_result.tts_naturalness_avg*100:.1f}% | ≥90% | {'✅ 合格' if eval_result.tts_naturalness_avg >= 0.9 else '❌ 不合格'} |

## 🎯 整体结论
"""
        all_passed = (
            eval_result.success_rate >= 0.9 and
            eval_result.avg_asr_accuracy >= 0.85 and
            eval_result.avg_response_latency <= 1.5 and
            eval_result.avg_turn_latency <= 3.0 and
            eval_result.interrupt_success_rate >= 0.9 and
            eval_result.compliance_violation_rate <= 0.05 and
            eval_result.tts_naturalness_avg >= 0.9
        )

        if all_passed:
            md_content += "✅ **语音链路全部指标合格，达到上线标准**\n"
        else:
            md_content += "❌ **部分指标不合格，需要优化后才能上线**\n"
            failed_items = []
            if eval_result.success_rate < 0.9:
                failed_items.append(f"整体成功率 ({eval_result.success_rate*100:.1f}% < 90%)")
            if eval_result.avg_asr_accuracy < 0.85:
                failed_items.append(f"ASR识别准确率 ({eval_result.avg_asr_accuracy*100:.1f}% < 85%)")
            if eval_result.avg_response_latency > 1.5:
                failed_items.append(f"响应延迟 ({eval_result.avg_response_latency:.2f}s > 1.5s)")
            if eval_result.interrupt_success_rate < 0.9:
                failed_items.append(f"打断处理成功率 ({eval_result.interrupt_success_rate*100:.1f}% < 90%)")
            for item in failed_items:
                md_content += f"  - {item}\n"

        md_content += """
## 🗣️ 不同口音表现
| 口音类型 | 测试量 | 成功率 | ASR准确率 | 平均延迟 | 表现 |
|----------|--------|--------|-----------|----------|------|
"""
        for accent, data in eval_result.accent_performance.items():
            performance = "✅ 良好" if data["success_rate"] >= 0.9 else "⚠️ 需要优化"
            md_content += f"| {accent} | {data['total']} | {data['success_rate']*100:.1f}% | {data['avg_asr']*100:.1f}% | {data['avg_latency']:.2f}s | {performance} |\n"

        md_content += """
## 🔊 不同噪音环境表现
| 噪音类型 | 测试量 | 成功率 | ASR准确率 | 平均延迟 | 表现 |
|----------|--------|--------|-----------|----------|------|
"""
        for noise, data in eval_result.noise_performance.items():
            performance = "✅ 良好" if data["success_rate"] >= 0.9 else "⚠️ 需要优化"
            md_content += f"| {noise} | {data['total']} | {data['success_rate']*100:.1f}% | {data['avg_asr']*100:.1f}% | {data['avg_latency']:.2f}s | {performance} |\n"

        md_content += """
## 🎪 不同场景表现
| 对话场景 | 测试量 | 成功率 | ASR准确率 | 平均延迟 | 表现 |
|----------|--------|--------|-----------|----------|------|
"""
        for scenario, data in eval_result.scenario_performance.items():
            performance = "✅ 良好" if data["success_rate"] >= 0.9 else "⚠️ 需要优化"
            md_content += f"| {scenario} | {data['total']} | {data['success_rate']*100:.1f}% | {data['avg_asr']*100:.1f}% | {data['avg_latency']:.2f}s | {performance} |\n"

        md_content += """
## ❌ 错误分析
| 错误类型 | 数量 | 占比 | 建议 |
|----------|------|------|------|
"""
        total_errors = sum(eval_result.error_analysis.values())
        error_suggestions = {
            "asr_recognition_error": "优化ASR模型适配印尼各地口音，添加常见口音的训练数据",
            "high_latency": "优化机器人响应速度，考虑缓存常用回复，优化模型推理速度",
            "interrupt_handling_failure": "优化语音打断检测逻辑，确保用户说话时机器人立即停止播放",
            "compliance_violation": "优化话术审核机制，避免生成违规内容",
            "response_content_error": "优化对话策略，提升回复内容的准确性和相关性"
        }

        for error_type, count in eval_result.error_analysis.items():
            percentage = count / total_errors * 100 if total_errors > 0 else 0
            suggestion = error_suggestions.get(error_type, "建议进一步分析错误原因")
            md_content += f"| {error_type} | {count} | {percentage:.1f}% | {suggestion} |\n"

        md_content += """
## 📝 优化建议
"""
        # 生成具体优化建议
        suggestions = []

        # ASR相关
        low_asr_accents = [a for a, d in eval_result.accent_performance.items() if d["avg_asr"] < 0.8]
        if low_asr_accents:
            suggestions.append(f"重点优化以下口音的ASR识别准确率: {', '.join(low_asr_accents)}")

        low_asr_noises = [n for n, d in eval_result.noise_performance.items() if d["avg_asr"] < 0.7]
        if low_asr_noises:
            suggestions.append(f"优化以下噪音环境下的ASR鲁棒性: {', '.join(low_asr_noises)}")

        # 延迟相关
        if eval_result.avg_response_latency > 1.5:
            suggestions.append(f"机器人响应延迟过高 ({eval_result.avg_response_latency:.2f}s)，建议优化模型推理速度，添加常用回复缓存")

        # 打断相关
        if eval_result.interrupt_success_rate < 0.9:
            suggestions.append(f"用户打断处理成功率较低 ({eval_result.interrupt_success_rate*100:.1f}%)，建议优化打断检测和处理逻辑")

        # 场景相关
        low_performance_scenarios = [s for s, d in eval_result.scenario_performance.items() if d["success_rate"] < 0.8]
        if low_performance_scenarios:
            suggestions.append(f"以下场景表现较差，需要重点优化: {', '.join(low_performance_scenarios)}")

        if suggestions:
            for i, suggestion in enumerate(suggestions, 1):
                md_content += f"{i}. {suggestion}\n"
        else:
            md_content += "- 语音链路表现良好，无明显优化点\n"

        md_content += """
## 🔍 测试说明
1. 本测试模拟真实的语音交互全链路，覆盖ASR、对话、TTS三个核心环节
2. 测试覆盖了印尼主要地区口音和常见的背景噪音场景
3. 所有指标阈值基于实际业务的用户体验要求设定
4. 测试结果可作为语音链路优化和上线决策的重要依据
"""

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n语音仿真测试报告已生成:")
        print(f"  - JSON报告: {json_file}")
        print(f"  - Markdown报告: {md_file}")

        return str(md_file)

async def main():
    """主函数"""
    import argparse
    from collections import defaultdict

    parser = argparse.ArgumentParser(description="多模态语音仿真测试工具")
    parser.add_argument("--sample-size", type=int, help="抽样测试的样本量，默认使用全部用例")
    parser.add_argument("--test-cases-dir", default="data/runs/voice_test_cases/", help="测试用例目录")
    parser.add_argument("--output-dir", default="data/outputs/voice_simulation_reports/", help="报告输出目录")
    parser.add_argument("--case", help="运行单个测试用例，指定case_id")
    parser.add_argument("--filter-accent", help="仅测试特定口音的用例")
    parser.add_argument("--filter-noise", help="仅测试特定噪音场景的用例")

    args = parser.parse_args()

    tester = VoiceSimulationTester(args.test_cases_dir)

    if not tester.test_cases:
        print("请先准备语音测试用例到 data/runs/voice_test_cases/ 目录")
        return

    # 过滤用例
    if args.filter_accent:
        tester.test_cases = [c for c in tester.test_cases if c.user_accent == args.filter_accent]
        print(f"已过滤为仅测试 {args.filter_accent} 口音的用例，共 {len(tester.test_cases)} 个")

    if args.filter_noise:
        tester.test_cases = [c for c in tester.test_cases if c.background_noise == args.filter_noise]
        print(f"已过滤为仅测试 {args.filter_noise} 噪音的用例，共 {len(tester.test_cases)} 个")

    if args.case:
        # 运行单个测试用例
        case = next((c for c in tester.test_cases if c.case_id == args.case), None)
        if not case:
            print(f"找不到测试用例: {args.case}")
            return

        result = await tester.run_single_test(case)
        print(f"\n测试用例: {case.case_id}")
        print(f"测试结果: {'通过' if result.success else '失败'}")
        print(f"口音: {case.user_accent}, 噪音: {case.background_noise}")
        print(f"平均ASR准确率: {result.avg_asr_accuracy*100:.1f}%")
        print(f"平均单轮延迟: {result.avg_turn_latency:.2f}s")
        print(f"总对话时长: {result.total_latency:.2f}s")
        print(f"打断次数: {result.interrupt_count}, 打断处理成功率: {result.interrupt_success_rate*100:.1f}%")
        if result.compliance_violations:
            print("\n合规违规:")
            for v in result.compliance_violations:
                print(f"  - [{v['severity']}] {v['description']}")
        print("\n对话详情:")
        for turn in result.turn_results:
            print(f"\n第 {turn.turn_number} 轮:")
            print(f"  ASR识别: {turn.asr_input} (准确率: {turn.asr_accuracy*100:.1f}%)")
            print(f"  预期文本: {turn.asr_expected}")
            print(f"  机器人回复: {turn.bot_response}")
            print(f"  回复正确: {'是' if turn.is_correct else '否'}")
            print(f"  轮次总延迟: {turn.total_turn_latency:.2f}s")
            if turn.interrupted:
                print(f"  用户打断: 是，处理{'正确' if turn.interrupt_handled_correctly else '错误'}")
        return

    # 运行所有测试
    results, eval_result = await tester.run_all_tests(args.sample_size)

    if not eval_result:
        return

    # 打印结果摘要
    print("\n" + "="*70)
    print("多模态语音仿真测试结果汇总")
    print("="*70)
    print(f"总用例数: {eval_result.total_cases}")
    print(f"整体成功率: {eval_result.success_rate*100:.1f}%")
    print(f"平均ASR准确率: {eval_result.avg_asr_accuracy*100:.1f}%")
    print(f"平均响应延迟: {eval_result.avg_response_latency:.2f}s")
    print(f"平均单轮延迟: {eval_result.avg_turn_latency:.2f}s")
    print(f"打断处理成功率: {eval_result.interrupt_success_rate*100:.1f}%")
    print(f"合规违规率: {eval_result.compliance_violation_rate*100:.1f}%")
    print(f"TTS自然度: {eval_result.tts_naturalness_avg*100:.1f}%")

    # 结论
    print("\n" + "="*70)
    all_passed = (
        eval_result.success_rate >= 0.9 and
        eval_result.avg_asr_accuracy >= 0.85 and
        eval_result.avg_response_latency <= 1.5 and
        eval_result.avg_turn_latency <= 3.0 and
        eval_result.interrupt_success_rate >= 0.9 and
        eval_result.compliance_violation_rate <= 0.05 and
        eval_result.tts_naturalness_avg >= 0.9
    )
    if all_passed:
        print("✅ 全部指标合格，语音链路达到上线标准！")
    else:
        print("❌ 部分指标不合格，需要优化后才能上线")

    # 生成报告
    tester.generate_report(results, eval_result, args.output_dir)

if __name__ == "__main__":
    asyncio.run(main())
