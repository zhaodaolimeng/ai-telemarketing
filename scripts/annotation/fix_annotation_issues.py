#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复标注一致性问题
"""
import json
import re
from pathlib import Path
from typing import List, Dict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DIR = _PROJECT_ROOT / "data/gold_dataset"
REPORT_FILE = str(_PROJECT_ROOT / "data/annotation_consistency_report.json")

# 违规词汇列表（与检查脚本一致）
BAD_WORDS = ["ancam", "polisi", "keluarga", "rumah", "anjing", "goblok", "asu"]

def fix_file_issues(file_name: str, issues: List[Dict]) -> bool:
    """修复单个文件的问题，返回是否有修改"""
    file_path = GOLD_DIR / file_name
    if not file_path.exists():
        print(f"文件不存在: {file_name}")
        return False

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False

        # 提前提取agent的所有文本，用于违规检查
        agent_texts = [turn.get("text", "").lower() for turn in data.get("dialogue", []) if turn.get("speaker") == "agent"]
        full_agent_text = ' '.join(agent_texts)

        # 遍历所有问题，逐个修复
        for issue in issues:
            message = issue["message"]

            # 1. 修复：对话中没有customer/agent轮次
            if "没有customer轮次" in message or "没有agent轮次" in message:
                if "basic_info" not in data:
                    data["basic_info"] = {}
                data["basic_info"]["is_valid"] = False
                modified = True
                print(f"  ✅ 标记为无效样本: {message}")

            # 2. 修复：call_result标记为success但没有还款时间承诺
            elif "call_result标记为success" in message:
                if "basic_info" in data:
                    data["basic_info"]["call_result"] = "failure"
                    modified = True
                    print(f"  ✅ 修复call_result: success → failure")

            # 3. 修复：标记为合规但存在违规词汇
            elif "标记为合规，但agent对话中存在违规词汇" in message:
                if "compliance" not in data:
                    data["compliance"] = {"has_violation": False, "violation_details": ""}
                data["compliance"]["has_violation"] = True
                # 找出具体的违规词汇
                bad_words_found = [kw for kw in BAD_WORDS if kw in full_agent_text]
                data["compliance"]["violation_details"] = f"检测到违规词汇: {', '.join(bad_words_found)}"
                modified = True
                print(f"  ✅ 修复合规标记: 合规 → 有违规, 违规词汇: {bad_words_found}")

            # 4. 修复：标记为有违规但没有找到违规内容
            elif "标记为有合规违规，但未在agent对话中找到违规内容" in message:
                if "compliance" in data:
                    data["compliance"]["has_violation"] = False
                    data["compliance"]["violation_details"] = ""
                    modified = True
                    print(f"  ✅ 修复合规标记: 有违规 → 合规")

            # 5. 修复：不推荐的labeler取值
            elif "不推荐的labeler取值" in message:
                if "annotation_info" in data:
                    data["annotation_info"]["labeler"] = "auto-annotator"
                    modified = True
                    print(f"  ✅ 修复labeler取值为: auto-annotator")

        # 如果有修改，保存文件
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return modified

    except Exception as e:
        print(f"  ❌ 修复文件失败: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("批量修复标注一致性问题")
    print("=" * 80)

    # 读取一致性报告
    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        report = json.load(f)

    problematic_files = report.get("problematic_files", [])
    total_files = len(problematic_files)
    print(f"待修复文件数量: {total_files}")

    modified_count = 0

    # 逐个修复文件
    for i, pf in enumerate(problematic_files, 1):
        file_name = pf["file"]
        issues = pf["issues"]
        print(f"\n[{i}/{total_files}] 处理文件: {file_name}")
        print(f"  问题数量: {len(issues)}")

        if fix_file_issues(file_name, issues):
            modified_count += 1

    # 输出结果
    print(f"\n" + "=" * 80)
    print("修复完成!")
    print("=" * 80)
    print(f"已修改文件数: {modified_count}/{total_files}")
    print("\n建议重新运行一致性检查，确认所有问题已解决。")

    # 重新运行一致性检查
    print("\n正在重新运行一致性检查...")
    import subprocess
    result = subprocess.run(["python", "src/check_annotation_consistency.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"检查错误: {result.stderr}")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
