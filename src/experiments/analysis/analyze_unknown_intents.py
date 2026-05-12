#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析所有unknown意图的用户回复，挖掘高频语义模式，识别需要新增的意图类型
同时检查intention为空的异常情况
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GOLD_DIR = _PROJECT_ROOT / "data/raw/gold_dataset"

# 印尼语常用停用词
STOP_WORDS = {
    'yang', 'dan', 'di', 'dari', 'ini', 'itu', 'saya', 'anda', 'dia', 'kita', 'kami',
    'ada', 'tidak', 'ya', 'tidak', 'bisa', 'untuk', 'dengan', 'pada', 'ke', 'dalam',
    'jika', 'akan', 'telah', 'sudah', 'belum', 'mau', 'ingin', 'boleh', 'saja', 'hanya',
    'sangat', 'lebih', 'kurang', 'dulu', 'sekarang', 'nanti', 'besok', 'hari', 'bulan',
    'tahun', 'jam', 'menit', 'detik', 'aku', 'gue', 'gua', 'lu', 'kamu', 'dia', 'mereka',
    'ini', 'itu', 'sini', 'sana', 'situ', 'bagaimana', 'apa', 'siapa', 'kapan', 'dimana',
    'kenapa', 'mengapa', 'berapa', 'bagaimanapun', 'apapun', 'siapapun', 'kapanpun',
    'dimanapun', 'kenapapun', 'berapapun', 'yang', 'yg', 'dgn', 'dg', 'utk', 'untk'
}

def clean_text(text: str) -> str:
    """清理文本，去除特殊字符和标点"""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_keywords(text: str, n: int = 2) -> List[str]:
    """提取n-gram关键词"""
    words = [w for w in text.split() if w not in STOP_WORDS and len(w) > 2]
    keywords = []
    # 1-gram
    keywords.extend(words)
    # 2-gram
    if n >= 2:
        for i in range(len(words) - 1):
            keywords.append(f"{words[i]} {words[i+1]}")
    # 3-gram
    if n >= 3:
        for i in range(len(words) - 2):
            keywords.append(f"{words[i]} {words[i+1]} {words[i+2]}")
    return keywords

def analyze_unknown_intents():
    """分析所有unknown意图的用户回复"""
    unknown_utterances = []
    empty_intent_utterances = []
    total_customer_utterances = 0
    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    for file_path in all_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for turn in data.get("dialogue", []):
                if turn.get("speaker") == "customer":
                    total_customer_utterances += 1
                    intent = turn.get("user_intent", "")
                    text = turn.get("text", "").strip()
                    if not text:
                        continue
                    if intent == "":
                        empty_intent_utterances.append({
                            "file": file_path.stem,
                            "text": text,
                            "turn": turn.get("turn_number", 0)
                        })
                    elif intent == "unknown":
                        unknown_utterances.append({
                            "file": file_path.stem,
                            "text": text,
                            "turn": turn.get("turn_number", 0)
                        })
        except Exception as e:
            print(f"处理文件{file_path.name}出错: {e}")
    # 统计信息
    print("=" * 100)
    print("Unknown意图分析报告")
    print("=" * 100)
    print(f"总用户回复数: {total_customer_utterances}")
    print(f"Unknown意图数: {len(unknown_utterances)} ({len(unknown_utterances)/total_customer_utterances*100:.1f}%)")
    print(f"空意图数: {len(empty_intent_utterances)} ({len(empty_intent_utterances)/total_customer_utterances*100:.1f}%)")
    # 分析unknown的关键词分布
    print(f"\n🔍 Unknown文本关键词Top 30:")
    all_keywords = []
    for utt in unknown_utterances:
        all_keywords.extend(get_keywords(clean_text(utt['text']), n=2))
    keyword_counter = Counter(all_keywords)
    for keyword, count in keyword_counter.most_common(30):
        print(f"  {count:<5} | {keyword}")
    # 语义聚类，识别候选新意图
    print(f"\n🧠 候选新意图识别:")
    # 定义语义模式和对应的候选意图（和IntentDetector保持一致，使用单词边界提高精度）
    pattern_to_intent = [
        # 否认身份（优先级最高）
        (r'\b(bukan|salah nomor|anda salah orang|saya tidak kenal|ini bukan nomornya|salah orang|bukan orang yang anda cari)\b', 'deny_identity', '否认身份/错号'),
        # 忙碌
        (r'\b(sibuk|nanti ya|saya lagi diluar|nanti saya hubungi balik|sebentar lagi|saya lagi mengemudi|saya sedang rapat|nanti saya telepon kembali|saya tidak bisa bicara sekarang)\b', 'busy_later', '忙/不方便'),
        # 威胁
        (r'\b(laporkan|lapor ke|polisi|ojk|asosiasi|komplain|pengaduan|ancam|saya akan laporkan ke ojk|saya akan lapor polisi|anda ancam saya|saya akan lapor ke pihak berwenang|saya akan komplain)\b', 'threaten', '威胁投诉/报警'),
        # 申请展期
        (r'\b(perpanjang|perpanjangan|bisa nggak diperpanjang|extension|tunda bayar|bisa ditunda ya|saya mau perpanjang|berapa hari bisa ditunda|nanti minggu depan baru bisa bayar)\b', 'ask_extension', '申请延期/展期'),
        # 询问金额
        (r'\b(berapa|jumlahnya berapa|tagihan berapa|besarnya berapa|berapa nominalnya|besar tagihan|berapa bayarnya)\b', 'ask_amount', '询问欠款金额'),
        # 质疑身份
        (r'\b(siapa kamu|anda dari mana|mana buktinya|saya tidak percaya|penipuan|apakah ini penipuan|anda siapa|saya tidak pinjam|tidak pernah pinjam|salah orang)\b', 'question_identity', '质疑身份/债务真实性'),
        # 没钱
        (r'\b(tidak ada duit|saya tidak punya uang|lagi susah|belum ada uang|saya sedang kesulitan keuangan|uang saya belum masuk|gaji belum cair|sulit|kesulitan|keberatan|tidak mampu|belum mampu)\b', 'no_money', '没钱/经济困难'),
        # 确认时间
        (r'\b(jam [0-9]+|jp [0-9]+|hari ini|besok|minggu ini|saya bayar jam [0-9]+|nanti jam [0-9]+|jam [0-9]+ ya|sore hari|pagi hari|siang hari|nanti sore|nanti pagi|jam berapa|tanggal berapa|hari apa|nanti sore)\b', 'confirm_time', '告知还款时间'),
        # 同意还款
        (r'\b(siap bayar|bolehan|bisa|ok|setuju|saya akan bayar|saya bayar nanti|nanti saya transfer|saya bayar besok|saya proses sekarang|saya bayar hari ini|iya, saya bayar|baik, saya bayar|saya bayar|transfer segera)\b', 'agree_to_pay', '同意还款'),
        # 拒绝还款
        (r'\b(tidak mau bayar|gak bayar|saya tidak akan bayar|saya tidak mau membayar|tidak usah ditagih|saya tidak bayar|tidak bayar)\b', 'refuse_to_pay', '明确拒绝还款'),
        # 问候
        (r'\b(halo|hai|pagi|siang|sore|selamat pagi|selamat siang|selamat sore|selamat malam|apa kabar|hi|hello)\b', 'greeting', '问候/打招呼'),
        # 确认身份
        (r'\b(iya|betul|ya|iya benar|saya adalah|iya ini|betul saya|baik|iya, ini saya|benar, saya yang|benar|iya betul)\b', 'confirm_identity', '确认身份'),
        # 询问费用
        (r'\b(bunga berapa|denda berapa|biaya admin berapa|kenapa begitu besar|biaya berapa)\b', 'ask_fee', '询问利息/滞纳金/费用'),
        # 询问支付方式
        (r'\b(transfer kemana|rekening mana|nomor rekening|bayar kemana|bagaimana cara bayar)\b', 'ask_payment_method', '询问还款方式/账户'),
        # 已经付款
        (r'\b(sudah bayar|sudah transfer|saya sudah bayar|tadi sudah bayar|sudah dibayar)\b', 'already_paid', '告知已经还款'),
        # 部分还款
        (r'\b(mau bayar berapa|bisa bayar setengah dulu|bayar sebagian|cicil|bayar sedikit dulu)\b', 'partial_payment', '询问/申请部分还款/分期'),
        # 第三方接听
        (r'\b(keluarga dia|orang tua dia|anak dia|saudara dia|dia tidak ada|saya bukan orang yang anda cari|dia sedang keluar)\b', 'third_party', '第三方接听'),
        # 不知道
        (r'\b(tidak tahu|saya tidak tahu|tidak mengerti|tidak paham|saya tidak paham)\b', 'dont_know', '表示不知道/不清楚'),
    ]
    # 统计每个候选意图的匹配数量
    intent_candidates = defaultdict(list)
    for utt in unknown_utterances:
        text = utt['text'].lower()
        matched = False
        for pattern, intent, desc in pattern_to_intent:
            if re.search(pattern, text):
                intent_candidates[intent].append({
                    "text": utt['text'],
                    "file": utt['file'],
                    "description": desc
                })
                matched = True
                break
        if not matched:
            intent_candidates['other'].append({
                "text": utt['text'],
                "file": utt['file'],
                "description": "其他无法归类的表达"
            })
    # 输出候选新意图统计
    print(f"{'意图名称':<25} {'匹配数量':<8} {'描述':<40} {'占比':<8}")
    print("-" * 100)
    new_intent_list = []
    for intent, items in sorted(intent_candidates.items(), key=lambda x: -len(x[1])):
        if intent == 'other':
            continue
        count = len(items)
        percentage = count / len(unknown_utterances) * 100
        description = items[0]['description'] if items else ''
        # 超过10个样本的可以作为新意图
        if count >= 10:
            new_intent_list.append({
                "intent": intent,
                "description": description,
                "count": count,
                "percentage": percentage,
                "examples": [item['text'] for item in items[:3]]
            })
            print(f"✅ {intent:<23} {count:<8} {description:<40} {percentage:.1f}%")
        else:
            print(f"⚠️ {intent:<23} {count:<8} {description:<40} {percentage:.1f}% (样本不足)")
    print(f"\n其他无法归类的unknown数量: {len(intent_candidates.get('other', []))} ({len(intent_candidates.get('other', []))/len(unknown_utterances)*100:.1f}%)")
    # 输出建议新增的意图列表
    print(f"\n🚀 建议新增的意图列表（样本量>=10）:")
    for idx, ni in enumerate(new_intent_list, 1):
        print(f"\n{idx}. {ni['intent']} ({ni['description']})")
        print(f"   样本量: {ni['count']}个, 占unknown比例: {ni['percentage']:.1f}%")
        print(f"   示例:")
        for example in ni['examples']:
            print(f"     - {example[:60]}{'...' if len(example) > 60 else ''}")
    # 输出空意图的示例
    if empty_intent_utterances:
        print(f"\n⚠️ 空意图示例 (共{len(empty_intent_utterances)}个):")
        for ei in empty_intent_utterances[:5]:
            print(f"  文件: {ei['file']}, 轮次: {ei['turn']}, 文本: {ei['text'][:50]}...")
    # 保存分析结果
    result = {
        "total_customer_utterances": total_customer_utterances,
        "unknown_count": len(unknown_utterances),
        "empty_intent_count": len(empty_intent_utterances),
        "new_intent_candidates": new_intent_list,
        "intent_pattern_match": {k: len(v) for k, v in intent_candidates.items()},
        "top_keywords": [{"keyword": k, "count": v} for k, v in keyword_counter.most_common(50)]
    }
    output_file = Path("data/outputs/unknown_intent_analysis.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n完整分析结果已保存到: {output_file}")
    return result

if __name__ == "__main__":
    analyze_unknown_intents()
