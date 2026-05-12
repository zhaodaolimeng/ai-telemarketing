#!/usr/bin/env python3
"""
P15-C01 Round 2: 开放式意图发现
从 unknown 池中批量 LLM 分类，标记不适合现有 31 类意图体系的话语，
发现潜在新意图类别。
"""
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DISCOVERY_PROMPT = """你是印尼语催收对话意图分类专家。分析以下客户话语，判断其意图。

## 现有意图类别
deny_identity, busy_later, threaten, user_abuse, ask_extension, ask_amount,
question_identity, request_identity_verification, request_interest_reduction,
request_short_extension, complain_high_interest, app_uninstalled,
request_payment_reminder, request_settlement_proof, inquire_consequences,
borrowing_money, transfer_in_process, no_money, agree_to_pay, confirm_time,
greeting, confirm_identity, refuse_to_pay, ask_fee, ask_payment_method,
already_paid, partial_payment, third_party, dont_know, unknown, silence

## 任务
对每条话语，做两件事：
1. 判断最匹配的现有意图（如果确实匹配）
2. 如果不匹配任何现有类别，标记为 "NEW: <建议的新类别名称>"

## 重要规则
- 注意 ASR转写错误（印尼口语 → Whisper误识别），尝试理解真实含义
- "Nanti lah" (ASR→"Kuala"), "lunas"(ASR→"nasian"), "tempo"(ASR→"tempat")
- 短确认词(ya/iya/oke/hmm)在身份确认上下文 → confirm_identity
- 如果话语是完整句子但意图模糊 → unknown
- 如果话语断断续续/无意义噪音 → silence_or_noise
- **关键: 如果发现有新的、不在31类中的意图模式，标记为 "NEW: xxx"**

## 输出格式 (每行一条)
<话语文本> | <意图标签>

示例:
Halo pagi pak | greeting
Saya sudah transfer tadi pagi | already_paid
Tolong kirim bukti pembayaran ke WA | request_payment_reminder
Nanti saya kasih tau istri dulu | NEW: consult_spouse
"""


async def call_llm_batch(utterances: list[dict], model: str = "deepseek-chat") -> list[dict]:
    """批量调用 LLM 分类"""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        raise RuntimeError("请设置 OPENAI_API_KEY 或 ANTHROPIC_AUTH_TOKEN")

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    if "deepseek" in base_url.lower():
        base_url = base_url.rstrip("/v1").rstrip("/")

    # 每 50 条一批
    batch_size = 50
    all_results = []

    for i in range(0, len(utterances), batch_size):
        batch = utterances[i : i + batch_size]
        lines = "\n".join(
            f"{j+1}. {u['text']}" for j, u in enumerate(batch)
        )
        user_prompt = f"分类以下 {len(batch)} 条客户话语:\n\n{lines}"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": DISCOVERY_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 2000,
                        "temperature": 0.1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()

            # 解析结果
            for line in content.split("\n"):
                line = line.strip()
                if not line or "|" not in line:
                    continue
                # 去掉行号前缀
                if ". " in line[:5]:
                    line = line.split(". ", 1)[1]
                parts = line.rsplit("|", 1)
                if len(parts) == 2:
                    text = parts[0].strip()
                    intent = parts[1].strip().lower().replace(" ", "_")
                    all_results.append({"text": text, "intent": intent})

        except Exception as e:
            print(f"  Batch {i//batch_size + 1} error: {e}")
            for u in batch:
                all_results.append({"text": u["text"], "intent": "llm_error"})

        done = min(i + batch_size, len(utterances))
        print(f"  [{done}/{len(utterances)}] classified")
        if i + batch_size < len(utterances):
            await asyncio.sleep(1.0)

    return all_results


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="data/processed/unknown_discovery_sample.json")
    parser.add_argument("--output", type=str, default="data/outputs/llm_discovery_results.json")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    input_path = project_root / args.input
    output_path = project_root / args.output

    print("=" * 60)
    print("P15-C01 Round 2: 开放式意图发现")
    print("=" * 60)

    with open(input_path) as f:
        data = json.load(f)

    utterances = data["utterances"][:args.limit]
    print(f"待分类: {len(utterances)} 条")

    results = asyncio.run(call_llm_batch(utterances))

    # 分析
    intent_dist = Counter()
    new_intents = Counter()
    for r in results:
        intent = r["intent"]
        intent_dist[intent] += 1
        if intent.startswith("new:"):
            new_intents[intent] += 1

    print("\n" + "=" * 60)
    print("发现结果")
    print("=" * 60)
    print(f"总分类数: {len(results)}")

    print(f"\n=== 新意图发现 ({len(new_intents)} 种, {sum(new_intents.values())} 条) ===")
    for intent, cnt in new_intents.most_common():
        print(f"  {intent}: {cnt}")

    print(f"\n=== 完整意图分布 (Top 20) ===")
    for intent, cnt in intent_dist.most_common(20):
        marker = " *** NEW ***" if intent.startswith("new:") else ""
        print(f"  {intent}: {cnt}{marker}")

    # 打印每个新意图的样本
    print(f"\n=== 新意图样本 ===")
    for new_intent in new_intents:
        print(f"\n[{new_intent}]")
        samples = [r for r in results if r["intent"] == new_intent]
        for s in samples[:5]:
            print(f"  - {s['text'][:100]}")

    # 保存
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "meta": {"task": "P15-C01-round2", "total": len(results)},
        "new_intents_discovered": dict(new_intents),
        "full_distribution": dict(intent_dist),
        "results": results,
    }
    output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2))
    print(f"\n结果已保存: {output_path}")


if __name__ == "__main__":
    main()
