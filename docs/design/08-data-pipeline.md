# 数据流水线

## 概述

从 ClickHouse 生产数据库中提取催收通话记录，批量下载音频文件，经 ASR 转写和自动标注后，形成可供模型训练和评估的黄金数据集。

## 流水线架构

```
ClickHouse (生产库)              本地文件系统
     │                              │
     ├─ fetch_leads.py ─────────────┤  fetched_leads_*.csv
     │  (HTTP API 参数化查询)         │  (去重合并)
     │                              │
     │                              ├─ download_audio.py ──── voice_recordings/*.mp3
     │                              │  (限速下载, 断点续传)
     │                              │
     │                              ├─ batch_asr_transcribe.py ── processed/transcripts/*.json
     │                              │  (Faster-Whisper, 监听模式)
     │                              │
     │                              ├─ batch_annotate.py ──────── gold_dataset/*.json
     │                              │  (规则自动标注, 监听模式)
     │                              │
     │                              └─ reannotate_intents.py ──── llm_intent_labels.json
     │                                 (LLM 精标注, P15-C01 数据飞轮)
     │
     ├── 训练: simple_classifier.py (ML 分类器)
     └── 评估: playback_test.py / test_regression.py / robustness_test.py
```

## 阶段说明

### 阶段1: 数据提取 (`scripts/fetcher/fetch_leads.py`)

从 ClickHouse HTTP API 提取催收通话记录，按日期、通话时长、业务分组过滤。

```bash
# 提取2026年3月全量数据, 通话时长20-60秒
python scripts/fetcher/fetch_leads.py \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --min-duration 20 \
  --max-duration 60
```

**输出**: `data/fetched_leads_<timestamp>.csv`  
**字段**: user_id, loan_no, new_flag, mobile, call_time, match_key, talk_duration, record_url, chat_group 等 38 个字段  
**配置**: `scripts/fetcher/config.json` (gitignored, 含 ClickHouse 连接信息)  
**SQL**: `scripts/fetcher/sql/alpha_leads.sql` (10+ 表 JOIN 查询)

### 阶段2: 去重合并

多次提取的 CSV 可能存在记录重叠，按 `record_url` 去重。

```bash
# 自动去重合并所有 fetched_leads_*.csv
python3 -c "
import csv
from pathlib import Path
base = Path('data')
seen = set()
rows = []
for f in sorted(base.glob('fetched_leads_*.csv')):
    with open(f) as fh:
        for row in csv.DictReader(fh):
            if row['record_url'] not in seen:
                seen.add(row['record_url'])
                rows.append(row)
out = base / 'fetched_leads_deduped.csv'
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)
print(f'{len(rows)} unique records')
"
```

### 阶段3: 音频下载 (`scripts/fetcher/download_audio.py`)

按 `record_url` 批量下载 MP3 通话录音，内置限速、断点续传、代理自适应。

```bash
# 全量下载 (默认5s间隔, 断点续传)
python scripts/fetcher/download_audio.py --csv data/fetched_leads_deduped.csv

# 低频下载
python scripts/fetcher/download_audio.py --csv data/fetched_leads_deduped.csv --rate-limit 10

# 预览不下载
python scripts/fetcher/download_audio.py --csv data/fetched_leads_deduped.csv --dry-run
```

**输出**: `data/voice_recordings/<match_key>.mp3`  
**特性**:
- 自动检测代理（直连优先，失败降级到系统代理）
- 已存在且大于 `--min-bytes` 的文件自动跳过
- 支持 `--start/--end` 分段下载
- 失败自动重试（`--retry`，默认3次）

### 阶段4: ASR 转写 (`scripts/batch_asr_transcribe.py`)

基于 Faster-Whisper (CTranslate2) 批量转写印尼语通话录音。

```bash
# 一次性转写
python scripts/batch_asr_transcribe.py

# 监听模式: 每60秒扫描新文件自动转写
python scripts/batch_asr_transcribe.py --watch --interval 60

# 指定输入输出目录
python scripts/batch_asr_transcribe.py --input data/voice_recordings/ --output data/processed/transcripts/

# 强制覆盖
python scripts/batch_asr_transcribe.py --force
```

**输出**: `data/processed/transcripts/<match_key>.json`  
**模型**: Faster-Whisper small, int8 量化, CPU 推理  
**格式**: 含 `transcript` (逐词时间戳)、`transcript_with_speakers` (AGENT/CUSTOMER 交替)、`full_text`

### 阶段5: 自动标注 (`scripts/annotation/batch_annotate.py`)

规则驱动自动标注，将 ASR 转写结果标注为标准化黄金数据集。

```bash
# 监听模式: 每60秒扫描新转写自动标注
python3 -c "
import time
from pathlib import Path
from scripts.annotation.batch_annotate import annotate_transcript

td = Path('data/processed/transcripts')
gd = Path('data/gold_dataset')
gd.mkdir(parents=True, exist_ok=True)

while True:
    existing = {f.stem for f in gd.glob('*.json')}
    new = sorted({f.stem for f in td.glob('*.json')} - existing)
    if new:
        print(f'发现 {len(new)} 个新转录')
        for stem in new:
            annotate_transcript(td / f'{stem}.json', gd)
    time.sleep(60)
"
```

**输出**: `data/gold_dataset/<case_id>.json`  
**标注内容**: 对话阶段、用户意图、合规检查、催收成功判定  
**标注方法**: 规则引擎（ASR纠错 + 关键词匹配 + 阶段推断）

### 阶段6: LLM 意图精标注 (`src/experiments/reannotate_intents.py`)

规则自动标注的意图识别有盲区 — regex 只能覆盖已知模式，81% 的客户话语被标为 `unknown`。LLM 精标注阶段从 `unknown` 池中挖掘真实意图，形成数据飞轮。

```bash
# Round 1: 采样标注 + 训练 ML 分类器
python3 src/experiments/reannotate_intents.py --sample-size 400
# 产出: data/llm_intent_labels.json → 用于重训 ML

# Round 2: 开放式发现新意图
python3 src/experiments/discover_new_intents.py --limit 500
# 产出: data/llm_discovery_results.json → 分析后改进 regex

# 重训 ML 分类器
python3 -c "
from core.simple_classifier import train_and_save_model
train_and_save_model(llm_labels_path='data/llm_intent_labels.json')
"
```

**输出**: `data/llm_intent_labels.json` (训练数据), `models/simple_intent_classifier.pkl` (更新后的模型)  
**标注方法**: DeepSeek API 批量分类 + 开放式发现  
**迭代周期**: 每次管道产出入库后，按需运行精标注更新模型

**数据飞轮闭环**:

```
规则标注 (快速, 有盲区)
    │
    ├─ 81% → unknown 池
    │         │
    │         ▼
    │     LLM 精标注 (慢, 准确)
    │         │
    │         ├─ 归入已知意图 → 扩大训练集
    │         ├─ 发现新意图   → 补充 regex 模式
    │         └─ 仍无法判断   → ASR 质量问题跟踪
    │
    ▼
重训 ML 分类器 → 上线 → 下一次管道产出继续收集
```

## 一键启动全流水线

```bash
# 终端1: 音频下载
python scripts/fetcher/download_audio.py --csv data/fetched_leads_deduped.csv --rate-limit 10

# 终端2: ASR 监听
python scripts/batch_asr_transcribe.py --watch --interval 60

# 终端3: 标注监听
# (见阶段5的监听脚本)
```

三个进程可并行运行，互不阻塞。下游进程自动跳过已处理的文件，支持随时中断和恢复。

## 数据统计

| 指标 | 当前值 (2026-05-09) |
|------|---------------------|
| 已提取原始记录 | 1,892 条 (2个批次) |
| 去重后 | 1,459 条 |
| 已下载音频 | 2,578 个 |
| ASR 转写 | 2,288 条 |
| 黄金标注 | 2,210 个 |
| LLM 精标注 | 550 条 (P15-C01 两轮) |
| ML 分类器类别 | 25 类 (从 16 类扩充) |
| unknown 挖掘率 | ~82% (从 81%→18% unknown) |

## 待扩展

- [x] LLM 意图精标注管道（P15-C01 数据飞轮）
- [ ] ASR 纠错增强（印尼语专项优化）
- [ ] 说话人分离（pyannote 替代固定交替分配）
- [ ] 标注质量自动审核（人工抽检 + 一致性检查）
- [ ] 增量数据版本管理（标注版本追踪）
- [ ] 流水线监控与告警（下载失败率、转写异常检测）
