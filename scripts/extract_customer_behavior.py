#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从真实对话转写中提取用户行为特征，用于生成式客户模拟器
"""
import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict, Counter

# 配置
DATA_DIR = Path("data/processed/transcripts/")
LABEL_FILE = Path("data/label-chat-sample.xlsx")
OUTPUT_DIR = Path("data/behavior_analysis/")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 印尼语关键词提取
KEYWORDS = {
    # 同意/承诺类
    "agree": ["ya", "iya", "oke", "baik", "siap", "bersedia", "setuju", "ya pak", "ya bu", "bisa"],
    # 还款时间相关
    "time": ["jam", "pukul", "hari", "besok", "nanti", "siang", "pagi", "sore", "malam", "minggu", "bulan"],
    # 拒绝/抗拒类
    "refuse": ["tidak", "nggak", "gak", "bukan", "enggak", "tidak bisa", "nggak bisa", "tidak mau", "nggak mau"],
    # 借口类
    "excuse": ["sibuk", "kerja", "diluar", "perjalanan", "sakit", "keluarga", "anak", "istri", "suami", "uang", "tidak ada uang", "gaji belum keluar", "belum ada uang"],
    # 疑问/质疑类
    "question": ["apa", "siapa", "kenapa", "bagaimana", "dimana", "kapan", "berap", "minta bukti", "surat", "dokumen"],
    # 情绪类
    "emotion_angry": ["ngambek", "marah", "ngga senang", "tidak senang", "ganggu", "gangguan", "jangan telepon lagi"],
    # 协商/延期类
    "negotiate": ["nanti dulu", "besok", "minggu depan", "bulan depan", "diperpanjang", "perpanjang", "lambat", "keterlambatan", "dua hari lagi", "tiga hari lagi"]
}

# 对话阶段映射，对应机器人的状态
STAGE_MAPPING = {
    "greeting": "问候阶段",
    "identity": "身份确认阶段",
    "purpose": "说明来意阶段",
    "ask_time": "询问还款时间阶段",
    "push": "施压催促阶段",
    "commit": "确认承诺阶段",
    "close": "结束阶段"
}

class CustomerBehaviorAnalyzer:
    def __init__(self):
        self.all_customer_utterances: List[Dict[str, Any]] = []
        self.stage_utterances: Dict[str, List[str]] = defaultdict(list)
        self.category_stats: Dict[str, Counter] = defaultdict(Counter)
        self.chat_group_stats: Dict[str, List[str]] = defaultdict(list)
        self.labels = self._load_labels()
        # 统计信息
        self.stats = {
            "total_files": 0,
            "success": 0,
            "format_error": 0,
            "no_customer_turns": 0,
            "other_error": 0
        }

    def _load_labels(self) -> Dict[str, Any]:
        """加载标签数据"""
        try:
            import pandas as pd
            df = pd.read_excel(LABEL_FILE)
            return dict(zip(df["match_key"], df.to_dict("records")))
        except Exception as e:
            print(f"加载标签失败：{e}")
            return {}

    def _get_stage(self, turn_idx: int, total_turns: int, agent_last_text: str) -> str:
        """根据对话轮次和内容推断当前阶段"""
        lower_text = agent_last_text.lower() if agent_last_text else ""

        # 关键词匹配阶段
        if any(greet in lower_text for greet in ["halo", "selamat pagi", "selamat siang", "selamat sore", "apa kabar"]):
            return "greeting"
        elif any(ident in lower_text for ident in ["dengan bapak", "dengan ibu", "nama anda", "siapa", "bapak", "ibu"]):
            return "identity"
        elif any(purpose in lower_text for purpose in ["pinjaman", "tagihan", "hutang", "kredit", "bayar", "tunggakan"]):
            return "purpose"
        elif any(time in lower_text for time in ["jam berapa", "kapan", "bisa bayar", "waktu bayar"]):
            return "ask_time"
        elif any(push in lower_text for push in ["segera", "cepat", "harus bayar", "denda", "bunga", "tekanan"]):
            return "push"
        elif any(commit in lower_text for commit in ["oke jam", "ya jam", "siap jam", "konfirmasi", "terima kasih"]):
            return "commit"

        # 轮次估计
        if turn_idx <= 2:
            return "greeting"
        elif turn_idx <= 4:
            return "identity"
        elif turn_idx <= 6:
            return "purpose"
        elif turn_idx <= 10:
            return "ask_time"
        elif turn_idx <= 15:
            return "push"
        else:
            return "close"

    def _categorize_utterance(self, text: str) -> List[str]:
        """分类用户回复的类型"""
        lower_text = text.lower().strip()
        categories = []

        for category, keywords in KEYWORDS.items():
            if any(keyword in lower_text for keyword in keywords):
                categories.append(category)

        # 沉默/简短回复
        if not categories and len(lower_text.replace(" ", "")) <= 5:
            categories.append("silent_short")

        return categories if categories else ["other"]

    def analyze_file(self, file_path: Path):
        """分析单个转写文件"""
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
                self.stats["format_error"] += 1
                return

            # 获取标签信息
            label_info = self.labels.get(case_id, {})
            chat_group = label_info.get("chat_group", "unknown")
            repay_type = label_info.get("repay_type", "unknown")
            dpd = label_info.get("dpd", 0)

            # 提取用户回复
            agent_last_text = ""
            turn_idx = 0
            valid_customer_turns = 0

            for turn in transcript:
                # 兼容speaker字段的不同格式和大小写
                speaker = turn.get("speaker", turn.get("role", "")).upper()
                text = turn.get("text", "").strip()
                start_time = turn.get("start", 0)
                end_time = turn.get("end", 0)
                duration = end_time - start_time

                # 跳过无效轮次
                if not text or not speaker:
                    continue

                if speaker in ["CUSTOMER", "CLIENT", "PELANGGAN", "USER", "客户"]:  # 兼容不同的客户标识
                    turn_idx += 1
                    stage = self._get_stage(turn_idx, len(transcript), agent_last_text)
                    categories = self._categorize_utterance(text)

                    utterance_info = {
                        "case_id": case_id,
                        "chat_group": chat_group,
                        "repay_type": repay_type,
                        "dpd": dpd,
                        "turn_idx": turn_idx,
                        "stage": stage,
                        "text": text,
                        "duration": duration,
                        "length_char": len(text),
                        "length_word": len(text.split()),
                        "categories": categories
                    }

                    self.all_customer_utterances.append(utterance_info)
                    self.stage_utterances[stage].append(text)
                    self.chat_group_stats[chat_group].append(text)

                    for cat in categories:
                        self.category_stats[cat][text] += 1

                    valid_customer_turns += 1

                elif speaker in ["AGENT", "CS", "CUSTOMER SERVICE", "PETUGAS", "坐席"]:  # 兼容不同的坐席标识
                    agent_last_text = text

            if valid_customer_turns == 0:
                self.stats["no_customer_turns"] += 1
            else:
                self.stats["success"] += 1

        except Exception as e:
            self.stats["other_error"] += 1

    def analyze_all_files(self):
        """分析所有转写文件"""
        all_files = list(DATA_DIR.glob("*.json"))
        self.stats["total_files"] = len(all_files)
        print(f"开始分析 {self.stats['total_files']} 个转写文件...")
        for file_path in all_files:
            self.analyze_file(file_path)

        # 输出统计信息
        print("\n" + "=" * 50)
        print("文件处理统计：")
        print(f"总文件数：{self.stats['total_files']}")
        print(f"成功处理：{self.stats['success']}")
        print(f"格式错误：{self.stats['format_error']}")
        print(f"无客户说话内容：{self.stats['no_customer_turns']}")
        print(f"其他错误：{self.stats['other_error']}")
        print(f"提取用户回复总数：{len(self.all_customer_utterances)} 条")
        print("=" * 50 + "\n")

    def generate_analysis_report(self):
        """生成分析报告"""
        # 总体统计
        total_utterances = len(self.all_customer_utterances)
        avg_length_char = sum(u["length_char"] for u in self.all_customer_utterances) / total_utterances
        avg_length_word = sum(u["length_word"] for u in self.all_customer_utterances) / total_utterances
        avg_duration = sum(u["duration"] for u in self.all_customer_utterances) / total_utterances

        report = {
            "overview": {
                "total_utterances": total_utterances,
                "avg_length_char": round(avg_length_char, 2),
                "avg_length_word": round(avg_length_word, 2),
                "avg_duration_seconds": round(avg_duration, 2)
            },
            "category_distribution": {},
            "stage_distribution": {},
            "chat_group_distribution": {},
            "stage_examples": {},
            "category_examples": {}
        }

        # 分类统计
        total_categories = sum(len(u["categories"]) for u in self.all_customer_utterances)
        category_counter = Counter()
        for u in self.all_customer_utterances:
            for cat in u["categories"]:
                category_counter[cat] += 1

        for cat, count in category_counter.most_common():
            report["category_distribution"][cat] = {
                "count": count,
                "percentage": round(count / total_categories * 100, 2)
            }

        # 阶段统计
        for stage, utterances in self.stage_utterances.items():
            report["stage_distribution"][stage] = {
                "count": len(utterances),
                "percentage": round(len(utterances) / total_utterances * 100, 2),
                "stage_name": STAGE_MAPPING.get(stage, stage)
            }
            # 保存示例
            examples = list(set(utterances))[:5]
            report["stage_examples"][stage] = examples

        # 催收阶段统计
        for chat_group, utterances in self.chat_group_stats.items():
            report["chat_group_distribution"][chat_group] = {
                "count": len(utterances),
                "percentage": round(len(utterances) / total_utterances * 100, 2)
            }

        # 各分类高频示例
        for cat in KEYWORDS.keys():
            if cat in self.category_stats:
                top_examples = [text for text, count in self.category_stats[cat].most_common(10)]
                report["category_examples"][cat] = top_examples

        # 保存报告
        with open(OUTPUT_DIR / "customer_behavior_analysis.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 保存用户回复语料库，用于模拟器
        corpus = {
            "stage_corpus": {stage: list(set(utterances)) for stage, utterances in self.stage_utterances.items()},
            "category_corpus": {cat: [text for text, count in counter.most_common()] for cat, counter in self.category_stats.items()},
            "chat_group_corpus": {group: list(set(utterances)) for group, utterances in self.chat_group_stats.items()},
            "metadata": report["overview"]
        }

        with open(OUTPUT_DIR / "customer_response_corpus.json", "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=2)

        print(f"分析报告已保存到 {OUTPUT_DIR}")
        return report

    def print_summary(self, report):
        """打印分析摘要"""
        print("\n" + "=" * 70)
        print("用户行为特征分析摘要")
        print("=" * 70)

        print(f"\n📊 总体统计：")
        print(f"总用户回复数：{report['overview']['total_utterances']}")
        print(f"平均长度：{report['overview']['avg_length_char']} 字符，{report['overview']['avg_length_word']} 词")
        print(f"平均回复时长：{report['overview']['avg_duration_seconds']} 秒")

        print(f"\n🏷️ 回复类型分布：")
        for cat, stat in sorted(report['category_distribution'].items(), key=lambda x: x[1]['count'], reverse=True):
            print(f"{cat:15} : {stat['count']:4} ({stat['percentage']:5.1f}%)")

        print(f"\n🔄 对话阶段分布：")
        for stage, stat in sorted(report['stage_distribution'].items()):
            print(f"{stat['stage_name']:15} : {stat['count']:4} ({stat['percentage']:5.1f}%)")

        print(f"\n📈 催收阶段分布：")
        for group, stat in sorted(report['chat_group_distribution'].items()):
            print(f"{group:15} : {stat['count']:4} ({stat['percentage']:5.1f}%)")

        print("\n📚 各类型回复示例：")
        for cat, examples in report['category_examples'].items():
            if examples:
                print(f"\n{cat}:")
                for ex in examples[:3]:
                    print(f"  - {ex.strip()}")

        print("\n" + "=" * 70)

def main():
    analyzer = CustomerBehaviorAnalyzer()
    analyzer.analyze_all_files()
    report = analyzer.generate_analysis_report()
    analyzer.print_summary(report)

if __name__ == "__main__":
    main()
