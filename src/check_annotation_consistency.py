#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查所有黄金数据集标注的一致性问题，确保所有标注规范统一
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Any

# 路径配置
GOLD_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset")
ANNOTATION_LIST_FILE = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset_annotation_list.json")

# 合法取值集合，与标注规范完全一致
VALID_STAGES = {
    "greeting", "identity_verification", "purpose", "negotiation",
    "ask_time", "push", "confirm", "close", "handle_objection",
    "handle_extension", "identity"
}

VALID_INTENTS = {
    "deny_identity", "busy_later", "threaten", "ask_extension",
    "ask_amount", "question_identity", "no_money", "confirm_time",
    "agree_to_pay", "refuse_to_pay", "confirm_identity", "unknown"
}

VALID_RESISTANCE_LEVELS = {"very_low", "low", "medium", "high", "very_high"}
VALID_PERSONAS = {"cooperative", "resistant", "neutral"}
VALID_CALL_RESULTS = {"success", "failure"}
VALID_LABELERS = {"auto-annotator", "ai-annotator", "human-annotator"}

# 字段规范
REQUIRED_FIELDS = {
    "version", "case_id", "basic_info", "user_profile", "dialogue",
    "compliance", "annotation_info"
}

BASIC_INFO_FIELDS = {"collection_stage", "call_duration", "call_result"}
USER_PROFILE_FIELDS = {"persona", "resistance_level"}
COMPLIANCE_FIELDS = {"has_violation", "violation_details"}
ANNOTATION_INFO_FIELDS = {"labeler", "label_time", "notes"}

DIALOGUE_TURN_FIELDS = {
    "turn_number", "speaker", "text", "stage", "is_correct",
    "standard_response", "user_intent", "notes"
}

def check_single_file(file_path: Path) -> List[Dict]:
    """检查单个标注文件的一致性问题，返回问题列表"""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        case_id = file_path.stem
        # 1. 检查必填字段是否存在
        for field in REQUIRED_FIELDS:
            if field not in data:
                issues.append({
                    "type": "missing_field",
                    "severity": "high",
                    "message": f"缺少顶层必填字段: {field}"
                })
        # 2. 检查basic_info字段
        if "basic_info" in data:
            basic_info = data["basic_info"]
            for field in BASIC_INFO_FIELDS:
                if field not in basic_info:
                    issues.append({
                        "type": "missing_field",
                        "severity": "high",
                        "message": f"basic_info缺少必填字段: {field}"
                    })
            # 检查call_result合法性
            if "call_result" in basic_info and basic_info["call_result"] not in VALID_CALL_RESULTS:
                issues.append({
                    "type": "invalid_value",
                    "severity": "medium",
                    "message": f"无效的call_result: {basic_info['call_result']}, 必须是success/failure"
                })
            # 检查call_duration是数字
            if "call_duration" in basic_info and not isinstance(basic_info["call_duration"], (int, float)):
                issues.append({
                    "type": "invalid_value",
                    "severity": "medium",
                    "message": f"call_duration必须是数字类型, 当前是: {type(basic_info['call_duration'])}"
                })
        # 3. 检查user_profile字段
        if "user_profile" in data:
            user_profile = data["user_profile"]
            for field in USER_PROFILE_FIELDS:
                if field not in user_profile:
                    issues.append({
                        "type": "missing_field",
                        "severity": "high",
                        "message": f"user_profile缺少必填字段: {field}"
                    })
            # 检查resistance_level合法性
            if "resistance_level" in user_profile and user_profile["resistance_level"] not in VALID_RESISTANCE_LEVELS:
                issues.append({
                    "type": "invalid_value",
                    "severity": "medium",
                    "message": f"无效的resistance_level: {user_profile['resistance_level']}, 必须是very_low/low/medium/high/very_high"
                })
            # 检查persona合法性
            if "persona" in user_profile and user_profile["persona"] not in VALID_PERSONAS:
                issues.append({
                    "type": "invalid_value",
                    "severity": "low",
                    "message": f"无效的persona: {user_profile['persona']}, 建议是cooperative/resistant"
                })
        # 4. 检查compliance字段
        if "compliance" in data:
            compliance = data["compliance"]
            for field in COMPLIANCE_FIELDS:
                if field not in compliance:
                    issues.append({
                        "type": "missing_field",
                        "severity": "high",
                        "message": f"compliance缺少必填字段: {field}"
                    })
            # 检查has_violation是布尔类型
            if "has_violation" in compliance and not isinstance(compliance["has_violation"], bool):
                issues.append({
                    "type": "invalid_value",
                    "severity": "medium",
                    "message": f"has_violation必须是布尔类型, 当前是: {type(compliance['has_violation'])}"
                })
        # 5. 检查annotation_info字段
        if "annotation_info" in data:
            annotation_info = data["annotation_info"]
            for field in ANNOTATION_INFO_FIELDS:
                if field not in annotation_info:
                    issues.append({
                        "type": "missing_field",
                        "severity": "high",
                        "message": f"annotation_info缺少必填字段: {field}"
                    })
            # 检查labeler合法性
            if "labeler" in annotation_info and annotation_info["labeler"] not in VALID_LABELERS:
                issues.append({
                    "type": "invalid_value",
                    "severity": "low",
                    "message": f"不推荐的labeler取值: {annotation_info['labeler']}"
                })
            # 检查label_time格式 YYYY-MM-DD
            if "label_time" in annotation_info:
                label_time = annotation_info["label_time"]
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', label_time):
                    issues.append({
                        "type": "invalid_format",
                        "severity": "low",
                        "message": f"label_time格式不正确: {label_time}, 应该是YYYY-MM-DD"
                    })
        # 6. 检查dialogue字段
        if "dialogue" in data:
            dialogue = data["dialogue"]
            if not isinstance(dialogue, list) or len(dialogue) == 0:
                issues.append({
                    "type": "invalid_value",
                    "severity": "high",
                    "message": "dialogue必须是非空列表"
                })
            else:
                turn_numbers = set()
                has_agent_turn = False
                has_customer_turn = False
                for i, turn in enumerate(dialogue, 1):
                    # 检查对话轮字段
                    for field in DIALOGUE_TURN_FIELDS:
                        if field not in turn:
                            issues.append({
                                "type": "missing_field",
                                "severity": "high",
                                "message": f"对话轮{i}缺少必填字段: {field}"
                            })
                    # 检查turn_number连续性
                    if "turn_number" in turn:
                        turn_num = turn["turn_number"]
                        if turn_num in turn_numbers:
                            issues.append({
                                "type": "invalid_value",
                                "severity": "medium",
                                "message": f"对话轮{i}存在重复的turn_number: {turn_num}"
                            })
                        turn_numbers.add(turn_num)
                    # 检查speaker取值
                    if "speaker" in turn:
                        speaker = turn["speaker"]
                        if speaker not in ["agent", "customer"]:
                            issues.append({
                                "type": "invalid_value",
                                "severity": "medium",
                                "message": f"对话轮{i}无效的speaker: {speaker}, 必须是agent/customer"
                            })
                        if speaker == "agent":
                            has_agent_turn = True
                        else:
                            has_customer_turn = True
                    # 检查stage取值
                    if "stage" in turn:
                        stage = turn["stage"]
                        if stage not in VALID_STAGES:
                            issues.append({
                                "type": "invalid_value",
                                "severity": "medium",
                                "message": f"对话轮{i}无效的stage: {stage}"
                            })
                    # 检查is_correct取值
                    if "is_correct" in turn:
                        is_correct = turn["is_correct"]
                        speaker = turn.get("speaker", "")
                        if speaker == "agent" and not isinstance(is_correct, bool):
                            issues.append({
                                "type": "invalid_value",
                                "severity": "medium",
                                "message": f"对话轮{i}(agent)的is_correct必须是布尔值, 当前是: {type(is_correct)}"
                            })
                        elif speaker == "customer" and is_correct is not None:
                            issues.append({
                                "type": "invalid_value",
                                "severity": "low",
                                "message": f"对话轮{i}(customer)的is_correct应该是null, 当前是: {is_correct}"
                            })
                    # 检查user_intent取值（仅customer）
                    if "user_intent" in turn:
                        intent = turn["user_intent"]
                        speaker = turn.get("speaker", "")
                        if speaker == "customer" and intent not in VALID_INTENTS:
                            issues.append({
                                "type": "invalid_value",
                                "severity": "medium",
                                "message": f"对话轮{i}无效的user_intent: {intent}"
                            })
                        elif speaker == "agent" and intent != "":
                            issues.append({
                                "type": "invalid_value",
                                "severity": "low",
                                "message": f"对话轮{i}(agent)的user_intent应该为空, 当前是: {intent}"
                            })
                # 检查是否至少有一轮agent和一轮customer
                if not has_agent_turn:
                    issues.append({
                        "type": "logic_error",
                        "severity": "high",
                        "message": "对话中没有agent轮次"
                    })
                if not has_customer_turn:
                    issues.append({
                        "type": "logic_error",
                        "severity": "high",
                        "message": "对话中没有customer轮次"
                    })
        # 7. 逻辑一致性检查
        if "basic_info" in data and "dialogue" in data:
            call_result = data["basic_info"].get("call_result")
            dialogue = data["dialogue"]
            if call_result == "success":
                # 成功案例应该有明确的还款时间承诺
                has_time_commit = False
                for turn in dialogue:
                    if turn.get("speaker") == "customer":
                        text = turn.get("text", "").lower()
                        intent = turn.get("user_intent", "")
                        if intent == "confirm_time" or any([kw in text for kw in ["jam", "hari", "besok", "tanggal", "transfer", "bayar"]]):
                            has_time_commit = True
                            break
                if not has_time_commit:
                    issues.append({
                        "type": "logic_error",
                        "severity": "medium",
                        "message": "call_result标记为success，但对话中没有找到明确的还款时间承诺"
                    })
            # 检查合规标记与对话内容是否一致
            if "compliance" in data:
                has_violation = data["compliance"].get("has_violation", False)
                violation_details = data["compliance"].get("violation_details", "")
                agent_texts = [turn.get("text", "").lower() for turn in dialogue if turn.get("speaker") == "agent"]
                full_agent_text = ' '.join(agent_texts)
                has_bad_words = any([kw in full_agent_text for kw in ["ancam", "polisi", "keluarga", "rumah", "anjing", "goblok", "asu"]])
                if has_violation and not has_bad_words:
                    issues.append({
                        "type": "logic_error",
                        "severity": "low",
                        "message": "标记为有合规违规，但未在agent对话中找到违规内容"
                    })
                if not has_violation and has_bad_words:
                    issues.append({
                        "type": "logic_error",
                        "severity": "medium",
                        "message": "标记为合规，但agent对话中存在违规词汇"
                    })
    except json.JSONDecodeError:
        issues.append({
            "type": "invalid_json",
            "severity": "critical",
            "message": "JSON格式错误，无法解析"
        })
    except Exception as e:
        issues.append({
            "type": "unknown_error",
            "severity": "high",
            "message": f"解析文件时发生未知错误: {str(e)}"
        })
    return issues

def check_annotation_list_consistency() -> List[Dict]:
    """检查标注列表文件与实际文件的一致性"""
    issues = []
    try:
        with open(ANNOTATION_LIST_FILE, 'r', encoding='utf-8') as f:
            annotation_list = json.load(f)
        items = annotation_list.get("items", [])
        # 获取所有实际存在的文件
        actual_files = {f.stem for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"}
        # 检查列表中的文件是否都存在
        list_files = set()
        for item in items:
            file_stem = item.get("file", "").replace(".json", "")
            if file_stem:
                list_files.add(file_stem)
                if file_stem not in actual_files and file_stem != "annotation_template":
                    issues.append({
                        "type": "list_inconsistency",
                        "severity": "medium",
                        "message": f"标注列表中存在但实际文件不存在: {file_stem}"
                    })
        # 检查实际存在的文件是否都在列表中
        for file_stem in actual_files:
            if file_stem not in list_files and file_stem != "annotation_template":
                issues.append({
                    "type": "list_inconsistency",
                    "severity": "medium",
                    "message": f"实际文件存在但标注列表中缺失: {file_stem}"
                })
        # 检查列表字段一致性
        for i, item in enumerate(items, 1):
            required_item_fields = {"id", "file", "priority", "categories", "resistance_level", "turns", "duration", "stage_count", "status", "notes"}
            for field in required_item_fields:
                if field not in item:
                    issues.append({
                        "type": "list_field_missing",
                        "severity": "low",
                        "message": f"标注列表第{i}项缺少字段: {field}"
                    })
    except Exception as e:
        issues.append({
            "type": "list_error",
            "severity": "critical",
            "message": f"解析标注列表文件失败: {str(e)}"
        })
    return issues

def main():
    print("=" * 80)
    print("黄金数据集标注一致性检查")
    print("=" * 80)
    # 获取所有标注文件
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    print(f"待检查文件数量: {len(all_files)}")
    # 统计结果
    total_issues = 0
    issue_stats = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0
    }
    issue_type_stats = {}
    # 检查所有文件
    problematic_files = []
    for i, file_path in enumerate(all_files, 1):
        if i % 100 == 0:
            print(f"已检查: {i}/{len(all_files)}")
        issues = check_single_file(file_path)
        if issues:
            total_issues += len(issues)
            problematic_files.append({
                "file": file_path.name,
                "issues": issues
            })
            for issue in issues:
                severity = issue["severity"]
                issue_type = issue["type"]
                issue_stats[severity] += 1
                issue_type_stats[issue_type] = issue_type_stats.get(issue_type, 0) + 1
    # 检查标注列表一致性
    print(f"\n正在检查标注列表一致性...")
    list_issues = check_annotation_list_consistency()
    if list_issues:
        total_issues += len(list_issues)
        for issue in list_issues:
            severity = issue["severity"]
            issue_type = issue["type"]
            issue_stats[severity] += 1
            issue_type_stats[issue_type] = issue_type_stats.get(issue_type, 0) + 1
    # 输出汇总结果
    print("\n" + "=" * 80)
    print("检查完成!")
    print("=" * 80)
    print(f"总文件数: {len(all_files)}")
    print(f"存在问题的文件数: {len(problematic_files)}")
    print(f"总问题数: {total_issues}")
    print(f"\n问题严重程度分布:")
    for severity, count in issue_stats.items():
        if count > 0:
            print(f"  {severity}: {count}个")
    print(f"\n问题类型分布:")
    for issue_type, count in sorted(issue_type_stats.items(), key=lambda x: -x[1]):
        print(f"  {issue_type}: {count}个")
    # 输出详细问题（最多前20个）
    if problematic_files:
        print(f"\n前20个有问题的文件详情:")
        for pf in problematic_files[:20]:
            print(f"\n📄 {pf['file']}:")
            for issue in pf['issues'][:3]:  # 每个文件最多显示3个问题
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue['severity'], "⚪")
                print(f"  {severity_icon} {issue['message']}")
            if len(pf['issues']) > 3:
                print(f"  ... 还有{len(pf['issues']) - 3}个问题")
    # 输出列表问题
    if list_issues:
        print(f"\n📋 标注列表问题:")
        for issue in list_issues[:10]:
            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(issue['severity'], "⚪")
            print(f"  {severity_icon} {issue['message']}")
    # 保存完整检查报告
    report = {
        "check_time": "2026-05-06",
        "total_files": len(all_files),
        "problematic_files_count": len(problematic_files),
        "total_issues": total_issues,
        "severity_distribution": issue_stats,
        "type_distribution": issue_type_stats,
        "problematic_files": problematic_files,
        "list_issues": list_issues
    }
    report_file = "/Users/li/Workspace/ai-telemarketing/data/annotation_consistency_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n完整检查报告已保存到: {report_file}")
    # 总结建议
    print("\n" + "=" * 80)
    print("总结建议:")
    if total_issues == 0:
        print("✅ 所有标注完全一致，没有任何问题！")
    elif issue_stats.get("critical", 0) == 0 and issue_stats.get("high", 0) == 0:
        print("✅ 没有严重/高危问题，只有少量低优先级问题可以后续优化")
    else:
        print(f"⚠️ 发现{issue_stats.get('critical', 0)}个严重问题和{issue_stats.get('high', 0)}个高危问题，建议优先修复")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
