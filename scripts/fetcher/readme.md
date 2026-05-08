# 催收语音数据获取工具

从 ClickHouse 数据仓库拉取催收通话记录并下载对应音频文件。

## 数据源

- **Alpha** — 催收通话记录 + 用户画像 + 借贷状态 + 还款行为
- SQL 取数口径见 `sql/alpha_leads.sql`

## 快速开始

```bash
# 1. 配置连接信息
cp config.example.json config.json
# 编辑 config.json 填写实际数据库连接信息

# 2. 拉取通话记录（指定时间段）
python scripts/fetcher/fetch_leads.py --start-date 2026-05-01

# 3. 预览 SQL（不执行）
python scripts/fetcher/fetch_leads.py --start-date 2026-05-01 --dry-run

# 4. 下载音频文件（断点续传）
python scripts/fetcher/download_audio.py
```

## 参数说明

### fetch_leads.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --start-date | 2026-05-01 | 通话起始日期 |
| --end-date | 无 | 通话结束日期 |
| --min-duration | 20 | 最短通话时长（秒） |
| --max-duration | 60 | 最长通话时长（秒） |
| --chat-groups | 全部 | 限定催收阶段: H2 H1 S0 |
| --dry-run | false | 仅打印 SQL 不执行 |

### download_audio.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| --csv | 自动 | 指定 CSV 文件路径 |
| --start | 0 | 起始行号 |
| --end | 全部 | 结束行号 |
| --rate-limit | 5 | 下载间隔秒数 |
| --retry | 3 | 失败重试次数 |
| --dry-run | false | 仅检查状态 |

## 目录结构

```
scripts/fetcher/
├── readme.md
├── config.example.json       # 配置模板（已入 git）
├── config.json               # 实际配置（gitignore）
├── fetch_leads.py            # Step 1: ClickHouse → CSV
├── download_audio.py         # Step 2: CSV → MP3
└── sql/
    └── alpha_leads.sql       # ClickHouse 取数口径
```
