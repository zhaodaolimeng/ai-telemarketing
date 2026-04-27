#!/usr/bin/env python3
"""
测试分析脚本
"""

from pathlib import Path
from scripts.analyze import load_dialogues

def main():
    print("=" * 60)
    print("测试加载对话数据")
    print("=" * 60)

    data_dir = Path("data/processed")
    dialogues = load_dialogues(str(data_dir))

    print(f"\n加载了 {len(dialogues)} 个对话")

    for dialogue in dialogues:
        print(f"\n--- {dialogue.get('case_id')} ---")
        if "metadata" in dialogue:
            print(f"元数据: {dialogue['metadata']}")
        print(f"转写段落数: {len(dialogue.get('transcript', []))}")
        if "full_text" in dialogue:
            preview = dialogue['full_text'][:100] + "..." if len(dialogue['full_text']) > 100 else dialogue['full_text']
            print(f"内容预览: {preview}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()
