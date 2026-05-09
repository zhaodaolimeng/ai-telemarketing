#!/usr/bin/env python3
"""
P15-C01: LLM 意图精标注管道
从 gold_dataset 提取客户话语，用 LLM 精标注意图，作为 ML 分类器训练数据。
重点挖掘当前被 regex 自动标注器漏掉的异议类意图（no_money, refuse_to_pay, threaten 等）。
"""
import asyncio
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 完整意图分类体系（与 IntentDetector.INTENT_PATTERNS 对齐）
INTENT_CLASSES = [
    "deny_identity",
    "busy_later",
    "threaten",
    "ask_extension",
    "ask_amount",
    "question_identity",
    "request_identity_verification",
    "request_interest_reduction",
    "request_short_extension",
    "complain_high_interest",
    "app_uninstalled",
    "request_payment_reminder",
    "request_settlement_proof",
    "inquire_consequences",
    "borrowing_money",
    "transfer_in_process",
    "no_money",
    "agree_to_pay",
    "confirm_time",
    "greeting",
    "confirm_identity",
    "refuse_to_pay",
    "ask_fee",
    "ask_payment_method",
    "already_paid",
    "partial_payment",
    "third_party",
    "dont_know",
    "unknown",
    "user_abuse",
    "silence",
]

INTENT_DESCRIPTIONS = {
    "deny_identity": "否认身份/打错电话",
    "busy_later": "现在忙，稍后联系",
    "threaten": "威胁投诉/报警",
    "ask_extension": "请求延期还款",
    "ask_amount": "询问欠款金额",
    "question_identity": "质疑催收员身份",
    "request_identity_verification": "要求提供身份证明",
    "request_interest_reduction": "要求减免利息/罚金",
    "request_short_extension": "请求短期延期（2-3天）",
    "complain_high_interest": "抱怨利息/费用太高",
    "app_uninstalled": "已卸载APP/忘记密码",
    "request_payment_reminder": "请求发送还款提醒",
    "request_settlement_proof": "要求开具结清证明",
    "inquire_consequences": "询问逾期后果",
    "borrowing_money": "正在借钱/筹款中",
    "transfer_in_process": "正在转账中",
    "no_money": "表示没钱/经济困难/无法负担",
    "agree_to_pay": "同意还款/承诺支付",
    "confirm_time": "给出具体还款时间",
    "greeting": "问候语",
    "confirm_identity": "确认身份",
    "refuse_to_pay": "明确拒绝还款",
    "ask_fee": "询问费用明细",
    "ask_payment_method": "询问还款方式/账号",
    "already_paid": "声称已经还过款",
    "partial_payment": "询问部分还款/分期",
    "third_party": "第三方接听（家人/同事等）",
    "dont_know": "不知道/不清楚/不了解",
    "unknown": "无法归类的其他意图",
    "user_abuse": "辱骂/人身攻击",
    "silence": "沉默/无回应",
}

SYSTEM_PROMPT = """你是一个印尼语催收对话意图分类专家。给定一段客户（customer）在催收电话中的话语，请判断其意图类别。

## 意图类别定义
""" + "\n".join(f"- **{k}**: {v}" for k, v in INTENT_DESCRIPTIONS.items()) + """

## 重要规则
1. 只返回意图标签，不要解释
2. 如果话语包含多个意图，选择最主要的一个
3. "tidak ada uang"、"belum ada uang"、"sulit" → no_money（不是 unknown）
4. "laporkan OJK"、"polisi" → threaten
5. "sibuk"、"nanti ya" → busy_later
6. 简短的 "ya"、"iya"、"oke" 在没有催收上下文时 → confirm_identity
7. 如果确实无法判断 → unknown
8. 注意口语化表达和ASR错误（如 nasian→lunas, tempat→tempo）

## 输出格式
只返回意图标签，不要任何其他文字。
示例输出: no_money"""


def extract_utterances(gold_dir: Path, max_per_intent: int = 200) -> list[dict]:
    """提取所有客户话语，优先采样式未知意图"""
    all_utterances = []
    unknown_utterances = []
    known_utterances = []

    for gf in gold_dir.glob("*.json"):
        data = json.loads(gf.read_text())
        dialogue = data.get("dialogue", [])
        stage = data.get("basic_info", {}).get("collection_stage", "H2")

        for turn in dialogue:
            if turn.get("speaker") != "customer":
                continue
            text = turn.get("text", "").strip()
            if not text or len(text) < 2:
                continue
            intent = turn.get("user_intent", "").strip()
            utterance = {
                "case_id": gf.stem,
                "text": text,
                "current_intent": intent,
                "stage": stage,
                "turn_number": turn.get("turn_number", 0),
            }
            if intent in ("unknown", "unknown_intent", ""):
                unknown_utterances.append(utterance)
            else:
                known_utterances.append(utterance)

    print(f"Total customer utterances: {len(unknown_utterances) + len(known_utterances)}")
    print(f"  Currently unknown: {len(unknown_utterances)}")
    print(f"  Currently classified: {len(known_utterances)}")

    # 采样：优先取 unknown，再加少量已知意图作为验证
    sample_size = min(max_per_intent, len(unknown_utterances))
    sample = random.sample(unknown_utterances, sample_size) if unknown_utterances else []

    # 加 50 条已知意图用于验证 LLM 标注质量
    if known_utterances:
        val_sample = random.sample(known_utterances, min(50, len(known_utterances)))
        sample.extend(val_sample)

    random.shuffle(sample)
    return sample


async def call_llm_classify(text: str, model: str = "deepseek-chat") -> str:
    """调用 LLM 分类单条客户话语"""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise RuntimeError("请设置 OPENAI_API_KEY 或 ANTHROPIC_AUTH_TOKEN")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    if "deepseek" in base_url.lower():
        base_url = base_url.rstrip("/v1").rstrip("/")

    user_prompt = f"客户话语: {text}"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": 20,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        intent = data["choices"][0]["message"]["content"].strip().lower()
        # 清理可能的格式问题
        intent = intent.replace("'", "").replace('"', "").replace(".", "").strip()
        return intent


async def batch_classify(utterances: list[dict], batch_size: int = 5, delay: float = 0.5) -> list[dict]:
    """批量分类，每批之间稍作延迟"""
    import time

    results = []
    total = len(utterances)

    for i in range(0, total, batch_size):
        batch = utterances[i : i + batch_size]
        tasks = []
        for u in batch:
            tasks.append(classify_one(u))

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for j, result in enumerate(batch_results):
            if isinstance(result, Exception):
                print(f"  ❌ {batch[j]['text'][:60]}... -> Error: {result}")
                batch[j]["llm_intent"] = "error"
                batch[j]["error"] = str(result)
            else:
                batch[j] = result
            results.append(batch[j])

        done = min(i + batch_size, total)
        if done % 50 == 0 or done == total:
            print(f"  [{done}/{total}] classified")
        if i + batch_size < total:
            await asyncio.sleep(delay)

    return results


async def classify_one(u: dict) -> dict:
    """分类单条"""
    intent = await call_llm_classify(u["text"])
    u["llm_intent"] = intent
    return u


def analyze_results(results: list[dict]) -> dict:
    """分析标注结果"""
    stats = {
        "total": len(results),
        "intent_distribution": Counter(),
        "changed_from_unknown": Counter(),
        "agreement_with_current": 0,
        "disagreement_with_current": 0,
        "samples": {},
    }

    for r in results:
        llm = r.get("llm_intent", "error")
        cur = r.get("current_intent", "")

        stats["intent_distribution"][llm] += 1

        if cur in ("unknown", "unknown_intent", ""):
            if llm != "unknown":
                stats["changed_from_unknown"][llm] += 1
        else:
            if llm == cur:
                stats["agreement_with_current"] += 1
            else:
                stats["disagreement_with_current"] += 1

        # 保存每个意图的样本
        if llm not in stats["samples"]:
            stats["samples"][llm] = []
        if len(stats["samples"][llm]) < 3:
            stats["samples"][llm].append(r["text"])

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="P15-C01: LLM 意图精标注管道")
    parser.add_argument("--gold-dir", type=str, default="data/gold_dataset",
                        help="Gold dataset 目录")
    parser.add_argument("--sample-size", type=int, default=400,
                        help="LLM 标注的样本数")
    parser.add_argument("--output", type=str, default="data/llm_intent_labels.json",
                        help="输出文件路径")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅提取和显示统计，不调用 LLM")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    gold_dir = project_root / args.gold_dir
    output_path = project_root / args.output

    print("=" * 60)
    print("P15-C01: LLM 意图精标注管道")
    print("=" * 60)
    print(f"  Gold目录: {gold_dir}")
    print(f"  样本数: {args.sample_size}")

    # 1. 提取话语
    utterances = extract_utterances(gold_dir, max_per_intent=args.sample_size)

    if args.dry_run:
        print(f"\n已提取 {len(utterances)} 条话语（dry-run，不调用 LLM）")
        # 显示当前 unknown 的样本
        unknown_samples = [u for u in utterances if u["current_intent"] in ("unknown", "unknown_intent", "")]
        print(f"\nUnknown 话语样本 (前10条):")
        for u in unknown_samples[:10]:
            print(f"  [{u['case_id']}] {u['text'][:80]}")
        return

    # 2. LLM 分类
    print(f"\n调用 LLM 分类 {len(utterances)} 条话语...")
    results = asyncio.run(batch_classify(utterances))

    # 3. 分析
    stats = analyze_results(results)

    print("\n" + "=" * 60)
    print("LLM 标注结果分析")
    print("=" * 60)
    print(f"总标注数: {stats['total']}")
    print(f"与现有标注一致: {stats['agreement_with_current']}")
    print(f"与现有标注不一致: {stats['disagreement_with_current']}")

    print(f"\n从未知中挖掘出的意图 (Top 10):")
    for intent, cnt in stats["changed_from_unknown"].most_common(10):
        desc = INTENT_DESCRIPTIONS.get(intent, "")
        print(f"  {intent}: {cnt} ({desc})")

    print(f"\nLLM 标注意图分布:")
    for intent, cnt in stats["intent_distribution"].most_common(15):
        desc = INTENT_DESCRIPTIONS.get(intent, "")
        print(f"  {intent}: {cnt} ({desc})")

    print(f"\n各意图样本:")
    for intent, samples in sorted(stats["samples"].items()):
        print(f"  [{intent}]")
        for s in samples:
            print(f"    - {s[:80]}")

    # 4. 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "meta": {
            "task": "P15-C01",
            "description": "LLM 精标注意图标签，用于训练 ML 分类器",
            "total_annotated": stats["total"],
            "intent_classes": len(stats["intent_distribution"]),
        },
        "intent_distribution": dict(stats["intent_distribution"]),
        "changed_from_unknown": dict(stats["changed_from_unknown"]),
        "training_data": [
            {"text": r["text"], "intent": r.get("llm_intent", "unknown")}
            for r in results
            if r.get("llm_intent") not in ("error",)
        ],
    }
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
    print(f"\n结果已保存: {output_path}")
    print(f"训练数据: {len(output_data['training_data'])} 条")


if __name__ == "__main__":
    main()
