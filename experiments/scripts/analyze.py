"""
会话分析脚本 - 状态发现、话术分析
"""
import json
from pathlib import Path
from typing import List, Dict
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    import hdbscan
    import umap
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


def load_dialogues(data_dir: str) -> List[Dict]:
    """
    加载所有对话数据
    """
    dialogues = []
    data_path = Path(data_dir)

    # 加载转写
    transcript_files = list(data_path.glob("transcripts/*.json"))
    for f in transcript_files:
        with open(f, encoding="utf-8") as fp:
            dialogues.append(json.load(fp))

    # 加载元数据并合并
    cases_csv = data_path.parent / "cases.csv"
    if cases_csv.exists():
        import csv
        metadata = {}
        with open(cases_csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                metadata[row["case_id"]] = row

        # 合并到对话数据中
        for dialogue in dialogues:
            case_id = dialogue.get("case_id")
            if case_id in metadata:
                dialogue["metadata"] = metadata[case_id]

    return dialogues


def discover_conversation_states(dialogues: List[Dict], output_dir: str):
    """
    无监督发现会话状态
    """
    if not ML_AVAILABLE:
        print("ML libraries not available, skipping state discovery")
        return

    print("Extracting utterance features...")

    # 1. 收集所有utterance
    all_utterances = []
    for d in dialogues:
        for turn in d["transcript"]:
            all_utterances.append({
                "text": turn["text"],
                "speaker": turn["speaker"],
                "case_id": d["case_id"],
                "turn_idx": len(all_utterances)
            })

    # 2. 提取embedding
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode([u["text"] for u in all_utterances])

    # 3. 聚类
    print("Clustering...")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=50, prediction_data=True)
    labels = clusterer.fit_predict(embeddings)

    # 4. 可视化（可选）
    # reducer = umap.UMAP()
    # umap_embeddings = reducer.fit_transform(embeddings)

    # 5. 保存结果
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 保存簇和样本
    clusters = {}
    for idx, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(all_utterances[idx])

    # 每个簇保存一些样本供人工查看
    for label, utterances in clusters.items():
        sample_file = output_path / f"state_{label}_samples.json"
        with open(sample_file, "w", encoding="utf-8") as f:
            json.dump({
                "state_id": int(label),
                "total_count": len(utterances),
                "samples": utterances[:50]  # 保存前50个样本
            }, f, ensure_ascii=False, indent=2)

    print(f"Found {len(clusters)} clusters, saved to {output_dir}")


def analyze_utterance_effectiveness(dialogues: List[Dict], output_dir: str):
    """
    分析话术有效性
    """
    print("Analyzing utterance effectiveness...")

    # TODO: 实现
    # 1. 按回款状态分组
    # 2. 对比两组的话术
    # 3. 计算提升率和显著性
    # 4. 保存结果

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 占位结果
    results = {
        "note": "Please implement the analysis logic",
        "total_dialogues": len(dialogues)
    }

    with open(output_path / "utterance_effectiveness.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze collection dialogues")
    parser.add_argument("--data", default="data/processed", help="Data directory")
    parser.add_argument("--output", default="results", help="Output directory")
    args = parser.parse_args()

    print("Loading dialogues...")
    dialogues = load_dialogues(args.data)

    print("Discovering conversation states...")
    discover_conversation_states(dialogues, args.output + "/states")

    print("Analyzing utterance effectiveness...")
    analyze_utterance_effectiveness(dialogues, args.output + "/utterances")

    print("Done!")


if __name__ == "__main__":
    main()
