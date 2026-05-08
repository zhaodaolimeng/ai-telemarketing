#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量更新标注文件中的user_intent字段，基于新的19类意图识别体系
仅更新speaker为customer且当前user_intent为unknown/空的字段
"""
import json
import re
from pathlib import Path
from typing import Dict, List

# 路径配置
GOLD_DIR = Path("/Users/li/Workspace/ai-telemarketing/data/gold_dataset")

# 和IntentDetector完全一致的意图匹配规则（优先级顺序相同）
INTENT_PATTERNS = [
    ('deny_identity', [r'\b(bukan|salah nomor|anda salah orang|saya tidak kenal|ini bukan nomornya|salah orang|bukan orang yang anda cari)\b']),
    ('busy_later', [r'\b(sibuk|nanti ya|saya lagi diluar|nanti saya hubungi balik|sebentar lagi|saya lagi mengemudi|saya sedang rapat|nanti saya telepon kembali|saya tidak bisa bicara sekarang)\b']),
    ('threaten', [r'\b(laporkan|lapor ke|polisi|ojk|asosiasi|komplain|pengaduan|ancam|saya akan laporkan ke ojk|saya akan lapor polisi|anda ancam saya|saya akan lapor ke pihak berwenang|saya akan komplain)\b']),
    ('ask_extension', [r'\b(perpanjang|perpanjangan|bisa nggak diperpanjang|extension|tunda bayar|bisa ditunda ya|saya mau perpanjang|berapa hari bisa ditunda|nanti minggu depan baru bisa bayar)\b']),
    ('ask_amount', [r'\b(berapa|jumlahnya berapa|tagihan berapa|besarnya berapa|berapa nominalnya|besar tagihan|berapa bayarnya)\b']),
    ('question_identity', [r'\b(siapa kamu|anda dari mana|mana buktinya|saya tidak percaya|penipuan|apakah ini penipuan|anda siapa|saya tidak pinjam|tidak pernah pinjam|salah orang)\b']),
    ('no_money', [r'\b(tidak ada duit|saya tidak punya uang|lagi susah|belum ada uang|saya sedang kesulitan keuangan|uang saya belum masuk|gaji belum cair|sulit|kesulitan|keberatan|tidak mampu|belum mampu)\b']),
    ('confirm_time', [r'\b(jam [0-9]+|jp [0-9]+|hari ini|besok|minggu ini|saya bayar jam [0-9]+|nanti jam [0-9]+|jam [0-9]+ ya|sore hari|pagi hari|siang hari|nanti sore|nanti pagi|jam berapa|tanggal berapa|hari apa|nanti sore)\b']),
    ('agree_to_pay', [r'\b(siap bayar|bolehan|bisa|ok|setuju|saya akan bayar|saya bayar nanti|nanti saya transfer|saya bayar besok|saya proses sekarang|saya bayar hari ini|iya, saya bayar|baik, saya bayar|saya bayar|transfer segera)\b']),
    ('refuse_to_pay', [r'\b(tidak mau bayar|gak bayar|saya tidak akan bayar|saya tidak mau membayar|tidak usah ditagih|saya tidak bayar|tidak bayar)\b']),
    ('greeting', [r'\b(halo|hai|pagi|siang|sore|selamat pagi|selamat siang|selamat sore|selamat malam|apa kabar|hi|hello)\b']),
    ('confirm_identity', [r'\b(iya|betul|ya|iya benar|saya adalah|iya ini|betul saya|baik|iya, ini saya|benar, saya yang|benar|iya betul)\b']),
    ('ask_fee', [r'\b(bunga berapa|denda berapa|biaya admin berapa|kenapa begitu besar|biaya berapa)\b']),
    ('ask_payment_method', [r'\b(transfer kemana|rekening mana|nomor rekening|bayar kemana|bagaimana cara bayar)\b']),
    ('already_paid', [r'\b(sudah bayar|sudah transfer|saya sudah bayar|tadi sudah bayar|sudah dibayar)\b']),
    ('partial_payment', [r'\b(mau bayar berapa|bisa bayar setengah dulu|bayar sebagian|cicil|bayar sedikit dulu)\b']),
    ('third_party', [r'\b(keluarga dia|orang tua dia|anak dia|saudara dia|dia tidak ada|saya bukan orang yang anda cari|dia sedang keluar)\b']),
    ('dont_know', [r'\b(tidak tahu|saya tidak tahu|tidak mengerti|tidak paham|saya tidak paham)\b']),
]

def detect_intent(text: str) -> str:
    """识别用户意图，和IntentDetector逻辑完全一致"""
    if not text:
        return 'unknown'

    text_lower = text.lower()

    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return intent

    return 'unknown'

def update_single_file(file_path: Path) -> Dict:
    """更新单个文件的user_intent字段，返回更新统计"""
    stats = {
        'total_turns': 0,
        'customer_turns': 0,
        'unknown_turns': 0,
        'updated_turns': 0,
        'intent_counts': {}
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        modified = False

        if 'dialogue' in data:
            for turn in data['dialogue']:
                stats['total_turns'] += 1

                if turn.get('speaker') == 'customer':
                    stats['customer_turns'] += 1
                    current_intent = turn.get('user_intent', 'unknown')

                    if current_intent in ['unknown', '']:
                        stats['unknown_turns'] += 1
                        text = turn.get('text', '')
                        new_intent = detect_intent(text)

                        if new_intent != 'unknown':
                            turn['user_intent'] = new_intent
                            modified = True
                            stats['updated_turns'] += 1

                            # 统计更新的意图分布
                            intent_name = new_intent
                            if intent_name not in stats['intent_counts']:
                                stats['intent_counts'][intent_name] = 0
                            stats['intent_counts'][intent_name] += 1

        # 保存更新
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        return stats

    except Exception as e:
        print(f"处理文件{file_path.name}出错: {e}")
        return {}

def main():
    print("=" * 80)
    print("批量更新标注文件user_intent字段")
    print("=" * 80)

    all_files = [f for f in GOLD_DIR.glob("*.json") if f.stem != "annotation_template"]
    print(f"待处理文件数量: {len(all_files)}")

    total_stats = {
        'total_files': len(all_files),
        'total_turns': 0,
        'customer_turns': 0,
        'unknown_turns': 0,
        'updated_turns': 0,
        'intent_counts': {}
    }

    for i, file_path in enumerate(all_files, 1):
        if i % 100 == 0:
            print(f"已处理: {i}/{len(all_files)}")

        stats = update_single_file(file_path)
        if not stats:
            continue

        # 汇总统计
        total_stats['total_turns'] += stats.get('total_turns', 0)
        total_stats['customer_turns'] += stats.get('customer_turns', 0)
        total_stats['unknown_turns'] += stats.get('unknown_turns', 0)
        total_stats['updated_turns'] += stats.get('updated_turns', 0)

        # 统计意图分布
        for intent, cnt in stats.get('intent_counts', {}).items():
            if intent not in total_stats['intent_counts']:
                total_stats['intent_counts'][intent] = 0
            total_stats['intent_counts'][intent] += cnt

    # 输出结果
    print(f"\n处理完成!")
    print("-" * 80)
    print(f"总对话轮数: {total_stats['total_turns']}")
    print(f"用户回复轮数: {total_stats['customer_turns']}")
    print(f"原unknown/空意图轮数: {total_stats['unknown_turns']}")
    print(f"成功更新意图轮数: {total_stats['updated_turns']}")
    if total_stats['unknown_turns'] > 0:
        print(f"更新成功率: {total_stats['updated_turns']/total_stats['unknown_turns']*100:.1f}%")
    else:
        print(f"更新成功率: 0%（无unknown意图需要更新）")

    print(f"\n更新的意图分布:")
    for intent, cnt in sorted(total_stats['intent_counts'].items(), key=lambda x: -x[1]):
        print(f"  {intent}: {cnt}个样本")

    # 运行一致性检查
    print(f"\n正在运行标注一致性检查...")
    import subprocess
    result = subprocess.run(['python', 'src/check_annotation_consistency.py'], capture_output=True, text=True)
    print(result.stdout)

    if result.stderr:
        print(f"检查错误: {result.stderr}")

    # 重新分析意图分布
    print(f"\n正在重新分析意图分布...")
    result = subprocess.run(['python', 'src/analyze_intent_distribution.py'], capture_output=True, text=True)
    print(result.stdout)

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
