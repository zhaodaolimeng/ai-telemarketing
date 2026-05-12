#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版智能催收对话系统测评框架
使用增强版客户模拟器，包含更多拒绝借口和抗拒程度分级
"""
import sys
import json
import random
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

_PROJECT_ROOT = Path(__file__).parent.parent.parent

sys.path.append(str(Path(__file__).parent.parent))

from core.simulator import RealCustomerSimulatorV2, GOLDEN_TEST_CASES_V2, GenerativeCustomerSimulator
from core.chatbot import CollectionChatBot, ChatState

# ==================== 可插拔抽象接口 ====================
class SimulatorInterface(ABC):
    """模拟器通用接口，所有类型的模拟器都必须实现此接口"""
    @abstractmethod
    def generate_response(
        self,
        stage: str,
        chat_group: str,
        persona: str,
        resistance_level: str,
        last_agent_text: str,
        push_count: int,
        **kwargs
    ) -> str:
        """
        生成用户回复
        :param stage: 当前对话阶段
        :param chat_group: 催收阶段（H2/H1/S0）
        :param persona: 用户类型
        :param resistance_level: 抗拒程度
        :param last_agent_text: 上一轮机器人回复
        :param push_count: 追问次数
        :param kwargs: 扩展参数
        :return: 用户回复文本
        """
        pass

@dataclass
class TestCase:
    """通用测试用例结构"""
    chat_group: str
    persona: str
    description: str
    expected_success: bool
    resistance_level: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)

class TestCaseProviderInterface(ABC):
    """测试用例提供接口，支持从不同来源获取测试用例"""
    @abstractmethod
    def get_test_cases(self) -> List[TestCase]:
        """获取所有测试用例"""
        pass


@dataclass
class PlaybackTestCase:
    """回放测试用例，包含完整的真实对话序列"""
    case_id: str
    chat_group: str
    description: str
    expected_success: bool
    expected_commit_time: Optional[str] = None
    customer_utterances: List[str] = field(default_factory=list)
    key_nodes: Dict[str, Any] = field(default_factory=dict)
    compliance_check: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class PlaybackTestCaseProvider(TestCaseProviderInterface):
    """回放测试用例提供器，从真实对话转写中加载黄金测试用例"""

    def __init__(self, transcripts_dir: Optional[Path] = None, labels_file: Optional[Path] = None):
        """
        初始化回放测试用例提供器
        :param transcripts_dir: 转写文件目录，默认data/processed/transcripts
        :param labels_file: 标签文件路径，默认data/raw/leads/label-chat-sample.xlsx
        """
        if transcripts_dir is None:
            transcripts_dir = Path(__file__).parent.parent.parent / "data" / "processed" / "transcripts"
        if labels_file is None:
            labels_file = Path(__file__).parent.parent.parent / "data/raw/leads" / "label-chat-sample.xlsx"

        self.transcripts_dir = transcripts_dir
        self.labels_file = labels_file
        self.labels = self._load_labels()

    def _load_labels(self) -> Dict[str, Any]:
        """加载标签数据"""
        try:
            import pandas as pd
            df = pd.read_excel(self.labels_file)
            # 标准化列名
            df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
            # 创建match_key，如果没有的话用文件名
            if "match_key" not in df.columns:
                df["match_key"] = df["file_name"].str.replace(".mp3", "", regex=False)
            return dict(zip(df["match_key"], df.to_dict("records")))
        except Exception as e:
            print(f"加载标签失败：{e}，将使用默认标签")
            return {}

    def _load_transcript(self, file_path: Path) -> Optional[PlaybackTestCase]:
        """加载单个转写文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            case_id = data["case_id"]
            # 兼容两种字段名
            if "transcript_with_speakers" in data:
                transcript = data["transcript_with_speakers"]
            elif "transcript" in data:
                transcript = data["transcript"]
            else:
                print(f"文件 {file_path} 格式错误，无transcript字段")
                return None

            # 获取标签信息
            label_info = self.labels.get(case_id, {})
            chat_group = label_info.get("chat_group", "unknown")
            expected_success = label_info.get("repay_result", False)
            expected_commit_time = label_info.get("commit_time")
            description = label_info.get("description", f"真实对话-{case_id}")

            # 提取用户回复序列
            customer_utterances = []
            for turn in transcript:
                speaker = turn.get("speaker", turn.get("role", "")).upper()
                text = turn.get("text", "").strip()
                if speaker in ["CUSTOMER", "CLIENT", "PELANGGAN", "USER", "客户"] and text:
                    customer_utterances.append(text)

            if not customer_utterances:
                print(f"文件 {file_path} 无客户回复，跳过")
                return None

            return PlaybackTestCase(
                case_id=case_id,
                chat_group=chat_group,
                description=description,
                expected_success=expected_success,
                expected_commit_time=expected_commit_time,
                customer_utterances=customer_utterances,
                metadata=label_info
            )

        except Exception as e:
            print(f"加载转写文件 {file_path} 失败：{e}")
            return None

    def get_test_cases(self) -> List[PlaybackTestCase]:
        """获取所有回放测试用例"""
        test_cases = []
        all_files = list(self.transcripts_dir.glob("*.json"))

        print(f"正在加载 {len(all_files)} 个转写文件...")
        for file_path in all_files:
            test_case = self._load_transcript(file_path)
            if test_case:
                test_cases.append(test_case)

        print(f"成功加载 {len(test_cases)} 个回放测试用例")
        return test_cases

    def get_test_case_by_id(self, case_id: str) -> Optional[PlaybackTestCase]:
        """根据ID获取单个测试用例"""
        for test_case in self.get_test_cases():
            if test_case.case_id == case_id:
                return test_case
        return None


# ==================== 默认实现（保持向后兼容）====================
class DefaultRuleSimulator(SimulatorInterface):
    """默认规则模拟器适配器，兼容原有RealCustomerSimulatorV2"""
    def __init__(self):
        self._impl = RealCustomerSimulatorV2()

    def generate_response(self, **kwargs) -> str:
        return self._impl.generate_response(**kwargs)

class DefaultGoldenTestCaseProvider(TestCaseProviderInterface):
    """默认Golden测试用例提供器，兼容原有GOLDEN_TEST_CASES_V2"""
    def get_test_cases(self) -> List[TestCase]:
        return [TestCase(*case) for case in GOLDEN_TEST_CASES_V2]


class GoldenDatasetTestCaseProvider(TestCaseProviderInterface):
    """
    标准化黄金数据集测试用例提供器
    从data/raw/gold_dataset目录加载所有标准化后的测试用例
    """

    def __init__(self, dataset_dir: Optional[Path] = None, annotation_list_file: Optional[Path] = None):
        """
        初始化黄金数据集提供器
        :param dataset_dir: 黄金数据集目录，默认data/raw/gold_dataset
        :param annotation_list_file: 标注列表文件，默认data/raw/gold_dataset_annotation_list.json
        """
        if dataset_dir is None:
            dataset_dir = Path(__file__).parent.parent.parent / "data" / "gold_dataset"
        if annotation_list_file is None:
            annotation_list_file = Path(__file__).parent.parent.parent / "data" / "gold_dataset_annotation_list.json"

        self.dataset_dir = dataset_dir
        self.annotation_list_file = annotation_list_file
        self.annotations = self._load_annotations()

    def _load_annotations(self) -> Dict[str, Any]:
        """加载标注列表文件"""
        try:
            with open(self.annotation_list_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 构建case_id到annotation的映射
                annotation_map = {}
                for item in data.get("items", []):
                    case_id = item.get("file", "").replace(".json", "")
                    if case_id:
                        annotation_map[case_id] = item
                return annotation_map
        except Exception as e:
            print(f"加载标注列表失败：{e}")
            return {}

    def _load_single_case(self, file_path: Path) -> Optional[PlaybackTestCase]:
        """加载单个黄金数据集案例"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            case_id = data.get("case_id", file_path.stem)
            basic_info = data.get("basic_info", {})
            user_profile = data.get("user_profile", {})
            compliance = data.get("compliance", {})
            annotation_info = data.get("annotation_info", {})

            # 获取标注信息
            annotation = self.annotations.get(case_id, {})

            # 提取用户回复序列
            customer_utterances = []
            for turn in data.get("dialogue", []):
                speaker = turn.get("speaker", "").lower()
                text = turn.get("text", "").strip()
                if speaker in ["customer", "user", "pelanggan"] and text:
                    customer_utterances.append(text)

            if not customer_utterances:
                print(f"案例 {case_id} 没有用户回复，跳过")
                return None

            # 确定预期结果
            call_result = basic_info.get("call_result", "").lower()
            expected_success = call_result in ["success", "extension", "berhasil"]

            # 构建预期关键节点
            key_nodes = {
                "identity_confirm": any(turn.get("stage") in ["identity", "identity_verification"] and turn.get("is_correct") for turn in data.get("dialogue", [])),
                "purpose_clear": any(turn.get("stage") in ["purpose", "purpose_statement"] and turn.get("is_correct") for turn in data.get("dialogue", [])),
                "commitment_confirm": any(turn.get("stage") in ["commit", "commitment", "confirm"] and turn.get("is_correct") for turn in data.get("dialogue", [])),
                "pressure_applied": any("denda" in turn.get("text", "").lower() or "bunga" in turn.get("text", "").lower() for turn in data.get("dialogue", []) if turn.get("speaker") == "agent")
            }

            # 生成描述
            description = annotation.get("notes", annotation_info.get("notes", f"黄金数据集案例-{case_id}"))
            if len(description) > 100:
                description = description[:100] + "..."

            return PlaybackTestCase(
                case_id=case_id,
                chat_group=basic_info.get("collection_stage", "H2"),
                description=description,
                expected_success=expected_success,
                expected_commit_time=None,  # 可从对话中提取，暂时留空
                customer_utterances=customer_utterances,
                key_nodes=key_nodes,
                compliance_check=not compliance.get("has_violation", False),
                metadata={
                    "persona": user_profile.get("persona", "unknown"),
                    "resistance_level": user_profile.get("resistance_level", "medium"),
                    "call_duration": basic_info.get("call_duration", 0),
                    "resistance_level": user_profile.get("resistance_level", "medium"),
                    "categories": annotation.get("categories", []),
                    "priority": annotation.get("priority", 0),
                    "annotation_notes": annotation_info.get("notes", "")
                }
            )

        except Exception as e:
            print(f"加载案例 {file_path.name} 失败：{e}")
            import traceback
            traceback.print_exc()
            return None

    def get_test_cases(self) -> List[PlaybackTestCase]:
        """获取所有黄金数据集测试用例"""
        test_cases = []
        all_files = list(self.dataset_dir.glob("*.json"))
        # 排除标注模板和示例文件
        filtered_files = [f for f in all_files if f.name not in ["annotation_template.json", "example_annotation.json"]]

        print(f"正在加载 {len(filtered_files)} 个黄金数据集案例...")
        for file_path in filtered_files:
            test_case = self._load_single_case(file_path)
            if test_case:
                test_cases.append(test_case)

        print(f"成功加载 {len(test_cases)} 个有效测试用例")
        return test_cases

    def get_test_case_by_id(self, case_id: str) -> Optional[PlaybackTestCase]:
        """根据ID获取单个测试用例"""
        for test_case in self.get_test_cases():
            if test_case.case_id == case_id:
                return test_case
        return None


@dataclass
class EvaluationResult:
    """测评结果"""
    session_id: str
    chat_group: str
    persona: str
    description: str
    success: bool
    commit_time: Optional[str]
    conversation_length: int
    conversation_log: List[Dict]
    expected_success: bool
    resistance_level: Optional[str] = None
    push_count: int = 0
    stage_completion: Dict[str, bool] = None
    timestamp: str = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvaluationFrameworkV2:
    """增强版智能催收对话系统测评框架
    支持可插拔的模拟器和测试用例提供器
    """

    def __init__(
        self,
        simulator: Optional[SimulatorInterface] = None,
        test_case_provider: Optional[TestCaseProviderInterface] = None,
        use_tts: bool = False
    ):
        """
        构造函数
        :param simulator: 模拟器实例，不传则使用默认规则模拟器
        :param test_case_provider: 测试用例提供器，不传则使用默认Golden用例
        :param use_tts: 是否启用TTS
        """
        # 依赖注入，默认使用原有实现，保持向后兼容
        self.simulator = simulator or DefaultRuleSimulator()
        self.test_case_provider = test_case_provider or DefaultGoldenTestCaseProvider()
        self.use_tts = use_tts
        self.results: List[EvaluationResult] = []

        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "true_positive": 0,
            "true_negative": 0,
            "false_positive": 0,
            "false_negative": 0,
            "by_group": {"H2": {"total": 0, "success": 0},
                         "H1": {"total": 0, "success": 0},
                         "S0": {"total": 0, "success": 0}},
            "by_persona": {},
            "by_resistance_level": {
                "very_low": {"total": 0, "success": 0},
                "low": {"total": 0, "success": 0},
                "medium": {"total": 0, "success": 0},
                "high": {"total": 0, "success": 0},
                "very_high": {"total": 0, "success": 0}
            }
        }

    async def run_single_test(
        self,
        chat_group: str,
        persona: str,
        description: str,
        expected_success: bool,
        resistance_level: str = "medium",
        max_turns: int = 20
    ) -> EvaluationResult:
        """运行单个测试"""

        bot = CollectionChatBot(chat_group)
        session_id = bot.session_id

        print(f"\n  {'=' * 70}")
        print(f"  场景: {description}")
        print(f"  抗拒程度: {resistance_level}")
        print(f"  {'=' * 70}")

        conversation_log = []
        stage_completion = {
            "greeting": False,
            "identity": False,
            "purpose": False,
            "ask_time": False
        }

        current_persona = persona
        push_count = 0
        silence_round = 0  # 跟踪实际沉默轮次（用于silent persona的渐进式模拟）

        # 开始对话
        agent_text, audio_file = await bot.process(use_tts=self.use_tts)
        print(f"  Agent: {agent_text}")
        conversation_log.append({
            "role": "agent",
            "text": agent_text,
            "timestamp": datetime.now().isoformat()
        })

        current_stage = "greeting"
        stage_completion["greeting"] = True

        # 对话循环
        for turn in range(max_turns):
            if bot.is_finished():
                break

            # 计算被追问次数和沉默轮次
            if "jam berapa" in agent_text.lower() or "kapan" in agent_text.lower():
                push_count += 1
            effective_push = silence_round if current_persona == "silent" else push_count

            # 客户回应
            customer_text = self.simulator.generate_response(
                stage=current_stage,
                chat_group=chat_group,
                persona=persona,
                resistance_level=resistance_level,
                last_agent_text=agent_text,
                push_count=effective_push
            )

            # 跟踪实际沉默轮次（用于silent persona的渐进式模拟）
            if current_persona == "silent" and (not customer_text or not customer_text.strip() or customer_text.strip() in ["...", "。。。"]) :
                silence_round += 1

            print(f"  Customer: {customer_text}")
            conversation_log.append({
                "role": "customer",
                "text": customer_text,
                "timestamp": datetime.now().isoformat()
            })

            # 机器人回应
            agent_text, audio_file = await bot.process(customer_text, use_tts=self.use_tts)

            if agent_text:
                print(f"  Agent: {agent_text}")
                conversation_log.append({
                    "role": "agent",
                    "text": agent_text,
                    "timestamp": datetime.now().isoformat()
                })

            # 更新当前阶段
            current_stage = self._get_stage_from_state(bot.state)
            if current_stage in stage_completion:
                stage_completion[current_stage] = True

        # 对话结束
        success = bot.is_successful()
        commit_time = bot.commit_time

        print(f"\n  结果: {'✅ 成功' if success else '❌ 失败'}")
        if commit_time:
            print(f"  约定时间: {commit_time}")
        print(f"  对话轮数: {len(conversation_log)}")
        print(f"  追问次数: {push_count}")

        result = EvaluationResult(
            session_id=session_id,
            chat_group=chat_group,
            persona=persona,
            description=description,
            success=success,
            commit_time=commit_time,
            conversation_length=len(conversation_log),
            conversation_log=conversation_log,
            expected_success=expected_success,
            resistance_level=resistance_level,
            push_count=push_count,
            stage_completion=stage_completion,
            timestamp=datetime.now().isoformat()
        )

        self.results.append(result)
        self._update_stats(result)

        return result

    async def run_playback_test(self, test_case: PlaybackTestCase) -> EvaluationResult:
        """
        运行单个回放测试
        :param test_case: 回放测试用例，包含用户回复序列
        """
        bot = CollectionChatBot(test_case.chat_group)
        session_id = bot.session_id

        print(f"\n  {'=' * 70}")
        print(f"  回放测试: {test_case.description}")
        print(f"  Case ID: {test_case.case_id}")
        print(f"  催收阶段: {test_case.chat_group}")
        print(f"  预期结果: {'成功' if test_case.expected_success else '失败'}")
        if test_case.expected_commit_time:
            print(f"  预期还款时间: {test_case.expected_commit_time}")
        print(f"  {'=' * 70}")

        conversation_log = []
        stage_completion = {
            "greeting": False,
            "identity": False,
            "purpose": False,
            "ask_time": False
        }

        push_count = 0
        customer_turn_idx = 0
        max_turns = len(test_case.customer_utterances) + 5  # 留一些额外轮次让机器人结束对话

        # 开始对话 - 机器人首先说话
        agent_text, audio_file = await bot.process(use_tts=self.use_tts)
        print(f"  Agent: {agent_text}")
        conversation_log.append({
            "role": "agent",
            "text": agent_text,
            "timestamp": datetime.now().isoformat()
        })

        current_stage = "greeting"
        stage_completion["greeting"] = True

        # 对话循环 - 按照预设的用户回复序列进行
        for turn in range(max_turns):
            if bot.is_finished():
                break

            # 计算被追问次数
            if "jam berapa" in agent_text.lower() or "kapan" in agent_text.lower():
                push_count += 1

            # 获取下一个用户回复
            if customer_turn_idx < len(test_case.customer_utterances):
                customer_text = test_case.customer_utterances[customer_turn_idx]
                customer_turn_idx += 1
            else:
                # 用户回复已经用完，机器人可以结束对话了
                break

            print(f"  Customer: {customer_text}")
            conversation_log.append({
                "role": "customer",
                "text": customer_text,
                "timestamp": datetime.now().isoformat()
            })

            # 机器人回应
            agent_text, audio_file = await bot.process(customer_text, use_tts=self.use_tts)

            if agent_text:
                print(f"  Agent: {agent_text}")
                conversation_log.append({
                    "role": "agent",
                    "text": agent_text,
                    "timestamp": datetime.now().isoformat()
                })

            # 更新当前阶段
            current_stage = self._get_stage_from_state(bot.state)
            if current_stage in stage_completion:
                stage_completion[current_stage] = True

        # 对话结束
        success = bot.is_successful()
        commit_time = bot.commit_time

        # 自动提取关键节点
        actual_key_nodes = self._extract_key_nodes(conversation_log)

        # 合规性检查
        compliance_result = self._check_compliance(conversation_log)

        # 多维度结果对比
        actual_results = {
            "success": success,
            "commit_time": commit_time,
            "key_nodes": actual_key_nodes,
            "compliance": compliance_result
        }

        expected_results = {
            "success": test_case.expected_success,
            "commit_time": test_case.expected_commit_time,
            "key_nodes": test_case.key_nodes,
            "compliance_check": test_case.compliance_check
        }

        comparison_result = self._compare_results(actual_results, expected_results)

        print(f"\n  结果: {'✅ 成功' if success else '❌ 失败'}")
        if commit_time:
            print(f"  实际约定时间: {commit_time}")
        print(f"  对话轮数: {len(conversation_log)}")
        print(f"  追问次数: {push_count}")
        print(f"  用户回复使用: {customer_turn_idx}/{len(test_case.customer_utterances)} 条")

        # 展示多维度匹配结果
        print(f"\n  📊 多维度对比结果:")
        print(f"  总体匹配度: {'✅ 完全匹配' if comparison_result['overall_match'] else '❌ 存在不匹配'}")
        for dim_name, dim_result in comparison_result["dimensions"].items():
            if dim_name == "key_nodes":
                continue  # 关键节点单独展示
            status = "✅" if dim_result["match"] else "❌"
            print(f"  {status} {dim_name}: 预期={dim_result['expected']}, 实际={dim_result['actual']}")

        # 展示关键节点对比
        if "key_nodes" in comparison_result["dimensions"] and comparison_result["dimensions"]["key_nodes"]:
            print(f"\n  🔑 关键节点对比:")
            for node_name, node_result in comparison_result["dimensions"]["key_nodes"].items():
                status = "✅" if node_result["match"] else "❌"
                print(f"  {status} {node_name}: 预期={node_result['expected']}, 实际={node_result['actual']}")

        # 展示合规性检查结果
        if not compliance_result["compliant"]:
            print(f"\n  ⚠️ 合规性警告: 发现{compliance_result['violation_count']}处违规内容")
            for violation in compliance_result["violations"]:
                print(f"    - {violation['position']}: 敏感词'{violation['keyword']}'，内容：{violation['text']}")

        result = EvaluationResult(
            session_id=session_id,
            chat_group=test_case.chat_group,
            persona="real_user",  # 真实用户
            description=test_case.description,
            success=success,
            commit_time=commit_time,
            conversation_length=len(conversation_log),
            conversation_log=conversation_log,
            expected_success=test_case.expected_success,
            resistance_level=None,  # 真实用户没有预设抗拒程度
            push_count=push_count,
            stage_completion=stage_completion,
            timestamp=datetime.now().isoformat()
        )

        # 添加回放测试特有的元数据
        result.metadata = {
            "case_id": test_case.case_id,
            "expected_commit_time": test_case.expected_commit_time,
            "actual_commit_time": commit_time,
            "customer_utterances_used": customer_turn_idx,
            "total_customer_utterances": len(test_case.customer_utterances),
            "result_match": comparison_result["overall_match"],
            "comparison_details": comparison_result,
            "actual_key_nodes": actual_key_nodes,
            "compliance_result": compliance_result,
            "original_metadata": test_case.metadata
        }

        self.results.append(result)
        self._update_stats(result)

        return result

    def _get_stage_from_state(self, state: ChatState) -> str:
        """从状态获取阶段名称"""
        stage_map = {
            ChatState.INIT: "greeting",
            ChatState.GREETING: "greeting",
            ChatState.IDENTITY_VERIFY: "identity",
            ChatState.PURPOSE: "purpose",
            ChatState.ASK_TIME: "ask_time",
            ChatState.PUSH_FOR_TIME: "push",
            ChatState.COMMIT_TIME: "commit",
            ChatState.CONFIRM_EXTENSION: "negotiate",
            ChatState.HANDLE_OBJECTION: "negotiate",
            ChatState.HANDLE_BUSY: "close",
            ChatState.HANDLE_WRONG_NUMBER: "close",
            ChatState.CLOSE: "close",
            ChatState.FAILED: "close",
        }
        return stage_map.get(state, "greeting")

    def _extract_key_nodes(self, conversation_log: List[Dict]) -> Dict[str, Any]:
        """
        从对话日志中自动提取关键节点信息
        返回包含各关键节点是否完成的字典
        """
        key_nodes = {
            "identity_confirm": False,
            "purpose_clear": False,
            "user_resistance": "无",
            "response_effective": True,
            "commitment_confirm": False,
            "pressure_applied": False
        }

        agent_utterances = [msg["text"].lower() for msg in conversation_log if msg["role"] == "agent"]
        user_utterances = [msg["text"].lower() for msg in conversation_log if msg["role"] == "customer"]
        full_agent_text = " ".join(agent_utterances)
        full_user_text = " ".join(user_utterances)

        # 检查身份确认：是否提到确认身份、询问对方是谁相关内容，且用户有明确的确认回复
        identity_keywords = ["dengan bapak", "dengan ibu", "siapa bicara", "konfirmasi identitas", "nama anda"]
        user_confirm_keywords = ["ya", "betul", "saya adalah", "iya", "benar", "ini saya", "ya ini", "dengan saya", "ya saya"]
        agent_asked_identity = any(keyword in full_agent_text for keyword in identity_keywords)
        user_confirmed = any(any(keyword in utterance for keyword in user_confirm_keywords) for utterance in user_utterances)
        if agent_asked_identity and user_confirmed:
            key_nodes["identity_confirm"] = True

        # 检查来意说明：是否明确提到是催收、还款、pinjaman、tagihan相关内容
        purpose_keywords = ["pinjaman", "tagihan", "bayar", "tunggakan", "jatuh tempo", "hutang"]
        if any(keyword in full_agent_text for keyword in purpose_keywords):
            key_nodes["purpose_clear"] = True

        # 识别用户抗拒类型
        resistance_keywords = {
            "忙": ["sibuk", "tidak ada waktu", "lagi kerja", "nanti saja"],
            "没钱": ["tidak ada uang", "uang tidak cukup", "lagi susah", "tidak mampu"],
            "质疑": ["siapa kamu", "aplikasi apa", "buktikan", "tipu", "penipuan"],
            "辱骂": ["anjing", "babi", "goblok", "jangan telepon lagi", "ganggu"]
        }
        for resistance_type, keywords in resistance_keywords.items():
            if any(keyword in full_user_text for keyword in keywords):
                key_nodes["user_resistance"] = resistance_type
                break

        # 检查是否进行了施压：是否提到逾期后果、denda、bunga、影响信用等
        pressure_keywords = ["denda", "bunga", "berakibat", "pengaruh kredit", "blacklist", "masalah hukum"]
        if any(keyword in full_agent_text for keyword in pressure_keywords):
            key_nodes["pressure_applied"] = True

        # 检查是否确认了还款承诺：是否重复用户提到的还款时间、表示确认收到承诺
        commit_keywords = ["ya jam", "baik jam", "saya catat", "konfirmasi", "tidak lupa ya"]
        if any(keyword in full_agent_text for keyword in commit_keywords):
            key_nodes["commitment_confirm"] = True

        return key_nodes

    def _check_compliance(self, conversation_log: List[Dict]) -> Dict[str, Any]:
        """
        合规性检查：检测话术中是否有违规内容
        返回合规性检查结果和违规详情
        """
        # 印尼语违规敏感词列表（催收行业禁止使用）
        forbidden_keywords = [
            "ancam", "bunuh", "pukul", "curi", "curang", "tipu", "keluarga",
            "kabur", "polisi", "penjara", "hina", "jelek", "bodoh", "goblok",
            "anjing", "babi", "maling", "asu", "brengsek", "tai"
        ]

        result = {
            "compliant": True,
            "violations": [],
            "violation_count": 0
        }

        for msg in conversation_log:
            if msg["role"] == "agent":
                text = msg["text"].lower()
                for keyword in forbidden_keywords:
                    if keyword in text:
                        result["compliant"] = False
                        result["violations"].append({
                            "position": f"第{len(result['violations']) + 1}轮对话",
                            "keyword": keyword,
                            "text": msg["text"]
                        })
                        result["violation_count"] += 1

        return result

    def _compare_results(self, actual: Dict, expected: Dict) -> Dict[str, Any]:
        """
        多维度对比实际结果与预期结果
        返回各维度的匹配情况和详细差异
        """
        comparison = {
            "overall_match": True,
            "dimensions": {}
        }

        # 1. 最终结果对比
        result_match = actual["success"] == expected["success"]
        comparison["dimensions"]["result"] = {
            "match": result_match,
            "expected": "成功" if expected["success"] else "失败",
            "actual": "成功" if actual["success"] else "失败"
        }
        if not result_match:
            comparison["overall_match"] = False

        # 2. 还款时间对比（如果成功）
        if expected["success"] and expected.get("commit_time"):
            actual_commit = actual.get("commit_time", "")
            commit_match = actual_commit == expected["commit_time"] or (actual_commit and expected["commit_time"] in actual_commit)
            comparison["dimensions"]["commit_time"] = {
                "match": commit_match,
                "expected": expected["commit_time"],
                "actual": actual_commit
            }
            if not commit_match:
                comparison["overall_match"] = False

        # 3. 关键节点对比
        expected_nodes = expected.get("key_nodes", {})
        actual_nodes = actual.get("key_nodes", {})
        node_comparison = {}
        for node_name, expected_value in expected_nodes.items():
            if node_name in actual_nodes:
                node_match = actual_nodes[node_name] == expected_value
                node_comparison[node_name] = {
                    "match": node_match,
                    "expected": expected_value,
                    "actual": actual_nodes[node_name]
                }
                if not node_match:
                    comparison["overall_match"] = False
        comparison["dimensions"]["key_nodes"] = node_comparison

        # 4. 合规性对比
        expected_compliance = expected.get("compliance_check", True)
        actual_compliance = actual.get("compliance", {}).get("compliant", True)
        compliance_match = expected_compliance == actual_compliance
        comparison["dimensions"]["compliance"] = {
            "match": compliance_match,
            "expected": "合规" if expected_compliance else "违规",
            "actual": "合规" if actual_compliance else "违规",
            "violations": actual.get("compliance", {}).get("violations", [])
        }
        if not compliance_match:
            comparison["overall_match"] = False

        return comparison

    def _update_stats(self, result: EvaluationResult):
        """更新统计数据"""
        self.stats["total"] += 1

        if result.success:
            self.stats["success"] += 1
        else:
            self.stats["failed"] += 1

        if result.success and result.expected_success:
            self.stats["true_positive"] += 1
        elif not result.success and not result.expected_success:
            self.stats["true_negative"] += 1
        elif result.success and not result.expected_success:
            self.stats["false_positive"] += 1
        elif not result.success and result.expected_success:
            self.stats["false_negative"] += 1

        # 按催收阶段统计，动态处理所有阶段类型
        if result.chat_group not in self.stats["by_group"]:
            self.stats["by_group"][result.chat_group] = {"total": 0, "success": 0}
        self.stats["by_group"][result.chat_group]["total"] += 1
        if result.success:
            self.stats["by_group"][result.chat_group]["success"] += 1

        if result.persona not in self.stats["by_persona"]:
            self.stats["by_persona"][result.persona] = {"total": 0, "success": 0}
        self.stats["by_persona"][result.persona]["total"] += 1
        if result.success:
            self.stats["by_persona"][result.persona]["success"] += 1

        if result.resistance_level:
            # 按抗拒程度统计，动态处理所有抗拒程度类型
            if result.resistance_level not in self.stats["by_resistance_level"]:
                self.stats["by_resistance_level"][result.resistance_level] = {"total": 0, "success": 0}
            self.stats["by_resistance_level"][result.resistance_level]["total"] += 1
            if result.success:
                self.stats["by_resistance_level"][result.resistance_level]["success"] += 1

    async def run_full_evaluation(self, num_additional_tests: int = 20, run_golden_cases: bool = True):
        """
        运行完整测评
        :param num_additional_tests: 额外随机测试数量
        :param run_golden_cases: 是否运行Golden测试用例
        """
        print("=" * 70)
        print("增强版智能催收对话系统测评")
        print("=" * 70)

        if run_golden_cases:
            print("\n【阶段1】Golden测试用例")
            print("-" * 70)

            for test_case in self.test_case_provider.get_test_cases():
                await self.run_single_test(
                    test_case.chat_group,
                    test_case.persona,
                    test_case.description,
                    test_case.expected_success,
                    test_case.resistance_level
                )

        if num_additional_tests > 0:
            print(f"\n【阶段2】额外随机测试 ({num_additional_tests}个)")
            print("-" * 70)

            chat_groups = ["H2", "H1", "S0"]
            personas = ["cooperative", "busy", "negotiating", "resistant", "silent", "forgetful", "excuse_master"]
            resistance_levels = ["very_low", "low", "medium", "high", "very_high"]

            for i in range(num_additional_tests):
                chat_group = random.choice(chat_groups)
                persona = random.choice(personas)
                resistance_level = random.choice(resistance_levels)

                expected_success = resistance_level in ["very_low", "low"] or \
                                  (resistance_level == "medium" and persona in ["cooperative", "busy"])

                await self.run_single_test(
                    chat_group, persona, f"随机测试-{i+1}",
                    expected_success, resistance_level
                )

        print("\n" + "=" * 70)
        print("测评完成！生成报告...")
        print("=" * 70)

        self._print_summary()
        self._save_report()

    def _print_summary(self):
        """打印摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        print(f"\n📊 总体结果:")
        print(f"  总测试数: {total}")
        print(f"  成功: {success} ({success_rate:.1f}%)")
        print(f"  失败: {self.stats['failed']}")

        print(f"\n📈 按催收阶段统计:")
        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {group:3}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n👥 按客户类型统计:")
        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {persona:12}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n🎚️ 按抗拒程度统计:")
        for level, data in self.stats["by_resistance_level"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {level:10}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n🎯 预测准确率:")
        tp, tn = self.stats["true_positive"], self.stats["true_negative"]
        fp, fn = self.stats["false_positive"], self.stats["false_negative"]
        total_correct = tp + tn
        accuracy = total_correct / total * 100 if total > 0 else 0
        print(f"  准确预测: {total_correct}/{total} ({accuracy:.1f}%)")
        print(f"  - 真阳性: {tp}")
        print(f"  - 真阴性: {tn}")
        print(f"  - 假阳性: {fp}")
        print(f"  - 假阴性: {fn}")

    def _save_report(self):
        """保存报告"""
        output_dir = _PROJECT_ROOT / "data/outputs/evaluations"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_file = output_dir / f"evaluation_report_v2_{timestamp}.json"
        report_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_tests": len(self.results),
                "version": "v2",
                "use_tts": self.use_tts
            },
            "summary": self.stats,
            "results": [asdict(r) for r in self.results]
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        md_file = output_dir / f"evaluation_summary_v2_{timestamp}.md"
        md_content = self._generate_markdown_summary()

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 报告已保存:")
        print(f"  - 详细JSON: {report_file}")
        print(f"  - 摘要MD: {md_file}")

    async def run_full_playback_evaluation(self, case_ids: Optional[List[str]] = None):
        """
        运行完整的回放测试
        :param case_ids: 可选，指定要运行的测试用例ID列表，不指定则运行所有
        """
        print("=" * 70)
        print("真实对话回放测试")
        print("=" * 70)

        # 加载回放测试用例
        provider = PlaybackTestCaseProvider()
        test_cases = provider.get_test_cases()

        if case_ids:
            # 筛选指定的用例
            test_cases = [tc for tc in test_cases if tc.case_id in case_ids]
            print(f"\n筛选到 {len(test_cases)} 个指定的测试用例")

        if not test_cases:
            print("没有找到有效的测试用例")
            return

        print(f"\n开始运行 {len(test_cases)} 个回放测试...")

        # 运行所有测试用例
        for i, test_case in enumerate(test_cases):
            print(f"\n【测试 {i+1}/{len(test_cases)}】")
            await self.run_playback_test(test_case)

        print("\n" + "=" * 70)
        print("回放测试完成！生成报告...")
        print("=" * 70)

        # 打印回放测试特有的统计
        self._print_playback_summary()
        self._save_report(report_prefix="playback_evaluation")

    async def run_golden_dataset_evaluation(self, case_ids: Optional[List[str]] = None, priority_threshold: Optional[float] = None):
        """
        运行完整的黄金数据集评估
        :param case_ids: 可选，指定要运行的测试用例ID列表，不指定则运行所有
        :param priority_threshold: 可选，优先级阈值，只运行优先级>=该值的用例（数值越大优先级越高）
        """
        print("=" * 70)
        print("黄金数据集评估")
        print("=" * 70)
        print(f"说明：基于标准化后的{len(list(Path('data/raw/gold_dataset').glob('*.json'))) - 2}个真实催收案例（排除模板和示例）")
        print("-" * 70)

        # 加载黄金数据集测试用例
        provider = GoldenDatasetTestCaseProvider()
        test_cases = provider.get_test_cases()

        if case_ids:
            # 筛选指定的用例
            test_cases = [tc for tc in test_cases if tc.case_id in case_ids]
            print(f"\n筛选到 {len(test_cases)} 个指定的测试用例")
        elif priority_threshold is not None:
            # 按优先级筛选
            test_cases = [tc for tc in test_cases if tc.metadata.get("priority", 0) >= priority_threshold]
            print(f"\n筛选到优先级>={priority_threshold}的测试用例共 {len(test_cases)} 个")

        if not test_cases:
            print("没有找到有效的测试用例")
            return

        # 统计用例分布
        categories_count = {}
        resistance_count = {}
        for tc in test_cases:
            for cat in tc.metadata.get("categories", []):
                categories_count[cat] = categories_count.get(cat, 0) + 1
            rl = tc.metadata.get("resistance_level", "unknown")
            resistance_count[rl] = resistance_count.get(rl, 0) + 1

        print(f"\n📋 用例分布统计:")
        print(f"  总用例数: {len(test_cases)}")
        print(f"  场景类型分布:")
        for cat, cnt in categories_count.items():
            print(f"    - {cat}: {cnt}个")
        print(f"  抗拒程度分布:")
        for rl, cnt in resistance_count.items():
            print(f"    - {rl}: {cnt}个")

        print(f"\n开始运行 {len(test_cases)} 个黄金数据集测试...")

        # 运行所有测试用例
        for i, test_case in enumerate(test_cases):
            print(f"\n【测试 {i+1}/{len(test_cases)}】")
            print(f"  Case ID: {test_case.case_id}")
            print(f"  场景: {test_case.description}")
            print(f"  催收阶段: {test_case.chat_group}")
            print(f"  抗拒程度: {test_case.metadata.get('resistance_level', 'unknown')}")
            print(f"  预期结果: {'成功' if test_case.expected_success else '失败'}")
            await self.run_playback_test(test_case)

        print("\n" + "=" * 70)
        print("黄金数据集评估完成！生成报告...")
        print("=" * 70)

        # 打印回放测试特有的统计
        self._print_golden_dataset_summary()
        self._save_report(report_prefix="golden_dataset_evaluation")

    def _print_playback_summary(self):
        """打印回放测试特有的统计摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        # 计算结果匹配率
        match_count = 0
        for result in self.results:
            if hasattr(result, 'metadata') and result.metadata.get("result_match", False):
                match_count += 1
        match_rate = match_count / total * 100 if total > 0 else 0

        print(f"\n📊 回放测试总体结果：")
        print(f"  总测试数：{total}")
        print(f"  成功：{success} ({success_rate:.1f}%)")
        print(f"  失败：{self.stats['failed']}")
        print(f"  结果与预期匹配：{match_count} ({match_rate:.1f}%)")

        print(f"\n📈 按催收阶段统计:")
        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {group:3}: {data['success']}/{data['total']} ({rate:.1f}%)")

        # 打印失败案例列表
        failed_cases = [r for r in self.results if not r.success]
        if failed_cases:
            print(f"\n❌ 失败案例列表 ({len(failed_cases)}个):")
            for result in failed_cases:
                case_id = result.metadata.get("case_id", "unknown") if hasattr(result, 'metadata') else "unknown"
                print(f"  - [{case_id}] {result.description}")

        # 打印不匹配案例列表
        mismatch_cases = [r for r in self.results if hasattr(result, 'metadata') and not result.metadata.get("result_match", True)]
        if mismatch_cases:
            print(f"\n⚠️ 结果不匹配案例列表 ({len(mismatch_cases)}个):")
            for result in mismatch_cases:
                case_id = result.metadata.get("case_id", "unknown")
                expected = "成功" if result.expected_success else "失败"
                actual = "成功" if result.success else "失败"
                print(f"  - [{case_id}] {result.description}: 预期{expected}, 实际{actual}")

    def _print_golden_dataset_summary(self):
        """打印黄金数据集评估特有的统计摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        # 计算结果匹配率
        match_count = 0
        compliance_violation_count = 0
        for result in self.results:
            if hasattr(result, 'metadata') and result.metadata.get("result_match", False):
                match_count += 1
            if hasattr(result, 'metadata') and not result.metadata.get("compliance_result", {}).get("compliant", True):
                compliance_violation_count += 1
        match_rate = match_count / total * 100 if total > 0 else 0
        compliance_rate = (total - compliance_violation_count) / total * 100 if total > 0 else 0

        print(f"\n📊 黄金数据集评估总体结果：")
        print(f"  总测试数：{total}")
        print(f"  成功：{success} ({success_rate:.1f}%)")
        print(f"  失败：{self.stats['failed']} ({(self.stats['failed']/total*100):.1f}%)")
        print(f"  结果与预期匹配：{match_count} ({match_rate:.1f}%)")
        print(f"  合规率：{compliance_rate:.1f}% (违规案例{compliance_violation_count}个)")

        print(f"\n📈 按催收阶段统计:")
        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            print(f"  {group:3}: {data['success']}/{data['total']} ({rate:.1f}%)")

        print(f"\n🎚️ 按抗拒程度统计:")
        for level, data in self.stats["by_resistance_level"].items():
            if data["total"] > 0:
                rate = data["success"] / data["total"] * 100
                print(f"  {level:10}: {data['success']}/{data['total']} ({rate:.1f}%)")

        # 统计按场景类型的成功率
        print(f"\n🔍 按场景类型统计:")
        scenario_stats = {}
        for result in self.results:
            categories = result.metadata.get("categories", []) if hasattr(result, "metadata") else []
            for cat in categories:
                if cat not in scenario_stats:
                    scenario_stats[cat] = {"total": 0, "success": 0}
                scenario_stats[cat]["total"] += 1
                if result.success:
                    scenario_stats[cat]["success"] += 1
        for cat, stats in scenario_stats.items():
            rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {cat:<25}: {stats['success']}/{stats['total']} ({rate:.1f}%)")

        # 打印失败案例列表
        failed_cases = [r for r in self.results if not r.success]
        if failed_cases:
            print(f"\n❌ 失败案例列表 ({len(failed_cases)}个):")
            for result in failed_cases:
                case_id = result.metadata.get("case_id", "unknown") if hasattr(result, 'metadata') else "unknown"
                print(f"  - [{case_id}] {result.description}")

        # 打印不匹配案例列表
        mismatch_cases = [r for r in self.results if hasattr(r, 'metadata') and not r.metadata.get("result_match", True)]
        if mismatch_cases:
            print(f"\n⚠️ 结果不匹配案例列表 ({len(mismatch_cases)}个):")
            for result in mismatch_cases:
                case_id = result.metadata.get("case_id", "unknown")
                expected = "成功" if result.expected_success else "失败"
                actual = "成功" if result.success else "失败"
                print(f"  - [{case_id}] {result.description}: 预期{expected}, 实际{actual}")

        # 打印违规案例列表
        violation_cases = [r for r in self.results if hasattr(r, 'metadata') and not r.metadata.get("compliance_result", {}).get("compliant", True)]
        if violation_cases:
            print(f"\n🚨 合规违规案例列表 ({len(violation_cases)}个):")
            for result in violation_cases:
                case_id = result.metadata.get("case_id", "unknown")
                violations = result.metadata.get("compliance_result", {}).get("violations", [])
                violation_keywords = ", ".join([v.get("keyword", "") for v in violations])
                print(f"  - [{case_id}] {result.description}: 违规关键词={violation_keywords}")

    def _save_report(self, report_prefix: str = "evaluation"):
        """保存报告，支持自定义前缀"""
        output_dir = _PROJECT_ROOT / "data/outputs/evaluations"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_file = output_dir / f"{report_prefix}_v2_{timestamp}.json"
        report_data = {
            "metadata": {
                "timestamp": timestamp,
                "total_tests": len(self.results),
                "version": "v2",
                "use_tts": self.use_tts,
                "test_type": report_prefix
            },
            "summary": self.stats,
            "results": [asdict(r) for r in self.results]
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        md_file = output_dir / f"{report_prefix}_summary_v2_{timestamp}.md"
        md_content = self._generate_markdown_summary()

        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"\n📄 报告已保存:")
        print(f"  - 详细JSON: {report_file}")
        print(f"  - 摘要MD: {md_file}")

    def _generate_markdown_summary(self) -> str:
        """生成Markdown摘要"""
        total = self.stats["total"]
        success = self.stats["success"]
        success_rate = success / total * 100 if total > 0 else 0

        md = f"""# 增强版智能催收对话系统测评报告

**测评时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**测试总数**: {total}
**总体成功率**: {success_rate:.1f}%

---

## 总体结果

| 指标 | 数值 |
|-----|------|
| 总测试数 | {total} |
| 成功 | {success} |
| 失败 | {self.stats['failed']} |
| 成功率 | {success_rate:.1f}% |

---

## 按催收阶段统计

| 阶段 | 测试数 | 成功 | 成功率 |
|-----|--------|-----|--------|
"""

        for group, data in self.stats["by_group"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {group} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += f"""
---

## 按客户类型统计

| 客户类型 | 测试数 | 成功 | 成功率 |
|---------|--------|-----|--------|
"""

        for persona, data in self.stats["by_persona"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {persona} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        md += f"""
---

## 按抗拒程度统计

| 抗拒程度 | 测试数 | 成功 | 成功率 |
|---------|--------|-----|--------|
"""

        for level, data in self.stats["by_resistance_level"].items():
            rate = data["success"] / data["total"] * 100 if data["total"] > 0 else 0
            md += f"| {level} | {data['total']} | {data['success']} | {rate:.1f}% |\n"

        tp, tn = self.stats["true_positive"], self.stats["true_negative"]
        fp, fn = self.stats["false_positive"], self.stats["false_negative"]
        total_correct = tp + tn
        accuracy = total_correct / total * 100 if total > 0 else 0

        md += f"""
---

## 预测准确率

| 指标 | 数值 |
|-----|------|
| 真阳性 | {tp} |
| 真阴性 | {tn} |
| 假阳性 | {fp} |
| 假阴性 | {fn} |
| 总准确率 | {accuracy:.1f}% |
"""

        # 如果是回放测试，添加额外的统计
        has_playback_results = any(hasattr(r, 'metadata') and r.metadata.get("case_id") for r in self.results)
        if has_playback_results:
            # 计算结果匹配率
            match_count = 0
            for result in self.results:
                if hasattr(result, 'metadata') and result.metadata.get("result_match", False):
                    match_count += 1
            match_rate = match_count / total * 100 if total > 0 else 0

            md += f"""
---

## 回放测试匹配度统计

| 指标 | 数值 |
|-----|------|
| 结果与预期匹配数 | {match_count} |
| 结果匹配率 | {match_rate:.1f}% |
"""

            # 添加失败案例列表
            failed_cases = [r for r in self.results if not r.success]
            if failed_cases:
                md += f"""
---

## 失败案例列表

| Case ID | 描述 | 催收阶段 |
|---------|------|----------|
"""
                for result in failed_cases:
                    case_id = result.metadata.get("case_id", "unknown") if hasattr(result, 'metadata') else "unknown"
                    md += f"| {case_id} | {result.description} | {result.chat_group} |\n"

            # 添加不匹配案例列表
            mismatch_cases = [r for r in self.results if hasattr(r, 'metadata') and not r.metadata.get("result_match", True)]
            if mismatch_cases:
                md += f"""
---

## 结果不匹配案例列表

| Case ID | 描述 | 预期结果 | 实际结果 |
|---------|------|----------|----------|
"""
                for result in mismatch_cases:
                    case_id = result.metadata.get("case_id", "unknown")
                    expected = "成功" if result.expected_success else "失败"
                    actual = "成功" if result.success else "失败"
                    md += f"| {case_id} | {result.description} | {expected} | {actual} |\n"

                # 添加详细的不匹配原因
                md += f"""
---

## 不匹配案例详细分析
"""
                for result in mismatch_cases:
                    case_id = result.metadata.get("case_id", "unknown")
                    comparison = result.metadata.get("comparison_details", {})

                    md += f"\n### 案例 {case_id}: {result.description}\n"
                    md += f"- 预期结果: {'成功' if result.expected_success else '失败'}\n"
                    md += f"- 实际结果: {'成功' if result.success else '失败'}\n\n"

                    if "dimensions" in comparison:
                        md += "#### 不匹配维度:\n"
                        for dim_name, dim_result in comparison["dimensions"].items():
                            if dim_name == "key_nodes":
                                continue
                            if not dim_result["match"]:
                                md += f"- ❌ {dim_name}: 预期=`{dim_result['expected']}`, 实际=`{dim_result['actual']}`\n"

                        # 关键节点不匹配
                        if "key_nodes" in comparison["dimensions"] and comparison["dimensions"]["key_nodes"]:
                            node_mismatches = []
                            for node_name, node_result in comparison["dimensions"]["key_nodes"].items():
                                if not node_result["match"]:
                                    node_mismatches.append(f"- ❌ {node_name}: 预期=`{node_result['expected']}`, 实际=`{node_result['actual']}`\n")
                            if node_mismatches:
                                md += "\n#### 关键节点不匹配:\n"
                                for mismatch in node_mismatches:
                                    md += mismatch

                    # 合规性问题
                    compliance = result.metadata.get("compliance_result", {})
                    if not compliance.get("compliant", True):
                        md += "\n#### 合规性问题:\n"
                        for violation in compliance.get("violations", []):
                            md += f"- ⚠️ {violation['position']}: 敏感词=`{violation['keyword']}`, 内容=`{violation['text']}`\n"

        md += """
---

## 测评框架特点

✅ 7种客户类型: cooperative, busy, negotiating, silent, forgetful, resistant, excuse_master

✅ 5种抗拒程度: very_low, low, medium, high, very_high

✅ 40+种拒绝借口: 经济困难、时间忙碌、家庭问题、质疑争议等

✅ 借口链条: 从轻度抗拒到重度抗拒的渐进式借口

✅ 追问计数: 跟踪被追问次数，模拟真实对话压力

---

## 结论"""

        if success_rate >= 75:
            md += "\n✅ **优秀** - 系统表现良好！"
        elif success_rate >= 60:
            md += "\n⚠️ **良好** - 系统基本可用"
        else:
            md += "\n❌ **需要改进** - 系统表现未达预期"

        return md


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="增强版智能催收对话系统测评框架")
    parser.add_argument("--use-tts", action="store_true", help="启用TTS语音合成")
    parser.add_argument("--num-tests", type=int, default=20, help="额外测试数量")
    parser.add_argument("--use-generative", action="store_true", help="使用数据驱动生成式客户模拟器（默认使用规则模拟器）")
    parser.add_argument("--playback", action="store_true", help="运行真实对话回放测试")
    parser.add_argument("--case-id", type=str, help="运行单个指定ID的回放测试用例")
    parser.add_argument("--case-ids", type=str, nargs="+", help="运行多个指定ID的回放测试用例")
    parser.add_argument("--test-multidim", action="store_true", help="测试多维度对比功能")
    parser.add_argument("--golden", action="store_true", help="运行黄金数据集评估")
    parser.add_argument("--priority-threshold", type=float, help="黄金数据集优先级阈值，只运行优先级>=该值的用例")

    args = parser.parse_args()

    # 测试多维度对比功能
    if args.test_multidim:
        framework = EvaluationFrameworkV2(
            simulator=None,
            use_tts=args.use_tts
        )

        # 创建一个手动标注的测试用例
        test_case = PlaybackTestCase(
            case_id="test_manual_001",
            chat_group="H2",
            description="测试多维度对比功能",
            expected_success=True,
            expected_commit_time="jam 2",
            customer_utterances=[
                "Hello, maaf ya?",
                "Ya dengan bapak saya lihat ma ya pak.",
                "Ya bener.",
                "Ya saya tunggu di jam 2 siang ini pembayarannya ya pak, dia bisa cek pak.",
                "Ini baru banyak penasaran.",
                "Orang-orang transfer."
            ],
            key_nodes={
                "identity_confirm": True,
                "purpose_clear": True,
                "user_resistance": "无",
                "commitment_confirm": True,
                "pressure_applied": False
            },
            compliance_check=True
        )

        # 运行测试
        await framework.run_playback_test(test_case)
        print("\n✅ 多维度对比测试完成！")
        return

    # 回放测试模式
    if args.playback or args.case_id or args.case_ids:
        framework = EvaluationFrameworkV2(
            simulator=None,  # 回放测试不需要模拟器
            use_tts=args.use_tts
        )

        case_ids = None
        if args.case_id:
            case_ids = [args.case_id]
        elif args.case_ids:
            case_ids = args.case_ids

        await framework.run_full_playback_evaluation(case_ids=case_ids)
        return

    # 黄金数据集评估模式
    if args.golden:
        framework = EvaluationFrameworkV2(
            simulator=None,  # 回放测试不需要模拟器
            use_tts=args.use_tts
        )

        case_ids = None
        if args.case_id:
            case_ids = [args.case_id]
        elif args.case_ids:
            case_ids = args.case_ids

        await framework.run_golden_dataset_evaluation(
            case_ids=case_ids,
            priority_threshold=args.priority_threshold
        )
        return

    # 普通测试模式
    # 选择模拟器
    if args.use_generative:
        from core.simulator import GenerativeCustomerSimulator
        simulator = GenerativeCustomerSimulator()
        print("使用生成式客户模拟器（基于真实对话语料）")
    else:
        simulator = None  # 使用默认规则模拟器
        print("使用规则增强版客户模拟器")

    framework = EvaluationFrameworkV2(
        simulator=simulator,
        use_tts=args.use_tts
    )
    await framework.run_full_evaluation(num_additional_tests=args.num_tests)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
