# 评估工具使用指南
本文档介绍评估体系中的各种工具的使用方法。

---

## 1. 批量测试工具 (run_small_scale_test.py)
### 功能
- 使用生成式客户模拟器进行大规模对话测试
- 支持多维度统计分析
- 生成结构化测试报告

### 使用方法
```bash
# 基础使用，默认1000次测试
python src/tests/run_small_scale_test.py

# 指定测试次数
python src/tests/run_small_scale_test.py 2000

# 使用生成式模拟器
python src/tests/run_small_scale_test.py 1000 --use-generative

# 指定测试场景
python src/tests/run_small_scale_test.py 1000 --use-generative --chat-groups H2 H1 --personas cooperative resistant --resistance-levels medium high

# 生成Markdown报告，包含失败案例
python src/tests/run_small_scale_test.py 1000 --use-generative --generate-md --include-logs

# 生成CSV报告
python src/tests/run_small_scale_test.py 1000 --use-generative --generate-csv

# 与历史报告对比
python src/tests/run_small_scale_test.py 1000 --use-generative --compare reports/old_report.json
```

### 参数说明
| 参数 | 说明 | 默认值 |
|------|------|--------|
| num_tests | 测试次数 | 1000 |
| --use-generative | 使用生成式模拟器 | 关闭 |
| --chat-groups | 指定催收阶段: H2/H1/S0 | 全部 |
| --personas | 指定用户类型: cooperative/busy/negotiating/resistant/silent/forgetful/excuse_master | 全部 |
| --resistance-levels | 指定抗拒程度: very_low/low/medium/high/very_high | 全部 |
| --include-logs | 报告中包含失败案例日志 | 关闭 |
| --concurrency | 并发数 | 20 |
| --output-prefix | 输出文件前缀 | test_report |
| --compare | 对比历史报告路径 | 无 |
| --generate-md | 生成Markdown报告 | 关闭 |
| --generate-csv | 生成CSV报告 | 关闭 |

---

## 2. 鲁棒性测试工具 (robustness_test.py)
### 功能
- 测试机器人在高风险场景下的应对能力
- 覆盖120+测试用例，包括恶意对抗、质疑身份、逻辑陷阱等场景
- 自动检测合规问题
- 生成详细测试报告

### 使用方法
```bash
# 列出所有测试用例
python src/tests/robustness_test.py --list-cases

# 运行单个测试用例
python src/tests/robustness_test.py --case-id R-1-001

# 运行特定类别的测试用例
python src/tests/robustness_test.py --category "恶意对抗类"

# 运行所有测试用例
python src/tests/robustness_test.py
```

### 测试报告
运行完成后会在`data/robustness_tests/`目录下生成JSON和Markdown格式的报告，包含：
- 总体通过率统计
- 按类别和难度的通过率分布
- 失败用例详情和原因分析

---

## 3. 合规检查工具 (compliance_checker.py)
### 功能
- 检测催收话术是否符合监管要求
- 内置15条合规规则，覆盖高/中/低三个风险等级
- 支持单文本检查和整个对话检查
- 自动生成合规报告

### 使用方法
#### 命令行使用
```bash
# 检查单个文本
python src/core/compliance_checker.py --text "Kamu harus bayar sekarang!"

# 检查对话日志文件
python src/core/compliance_checker.py --file data/conversation_log.json
```

#### 代码中使用
```python
from core.compliance_checker import get_compliance_checker

checker = get_compliance_checker()

# 检查单个文本
text = "Kamu harus bayar sekarang, jika tidak saya akan datang ke rumah kamu."
is_ok, violations = checker.check(text)
print(checker.generate_report(violations))

# 检查整个对话
conversation = [
    {"agent": "Halo Pak, saya dari aplikasi Extra.", "customer": "Ada apa?"},
    {"agent": "Untuk tagihan yang jatuh tempo ya Pak.", "customer": "Saya tidak punya uang."}
]
is_ok, violations = checker.check_conversation(conversation)
print(checker.generate_report(violations))
```

### 合规规则说明
| 规则ID | 描述 | 严重程度 |
|--------|------|----------|
| C-001 | 禁止使用辱骂性词汇 | high |
| C-002 | 禁止威胁用户（上门、联系家人、报警等） | high |
| C-003 | 禁止泄露用户隐私 | high |
| C-004 | 禁止虚假承诺（减免利息、删除征信等） | high |
| C-005 | 禁止冒充其他机构人员 | high |
| C-011 | 禁止使用诱导性表述（礼品、折扣等） | medium |
| C-012 | 禁止在不合适时间催收（晚9点到早8点） | medium |
| C-013 | 禁止重复拨打骚扰 | medium |
| C-014 | 禁止询问无关信息 | medium |
| C-015 | 禁止使用不文明用语 | medium |
| C-021 | 建议使用礼貌用语 | low |
| C-022 | 建议使用用户称呼 | low |
| C-023 | 建议表达理解 | low |

---

## 4. 用户行为提取工具 (extract_customer_behavior.py)
### 功能
- 从真实对话转写中提取用户行为特征
- 构建和更新生成式模拟器的语料库
- 分析用户回复的类型和分布

### 使用方法
```bash
python src/experiments/analysis/extract_customer_behavior.py
```

### 输出
- 分析报告: `data/behavior_analysis/customer_behavior_analysis.json`
- 语料库文件: `data/behavior_analysis/customer_response_corpus.json`（用于生成式模拟器）

---

## 5. 批量转写工具 (batch_asr_transcribe.py)
### 功能
- 批量将催收语音转写为文本
- 支持印尼语语音识别
- 自动输出符合格式要求的转写文件

### 使用方法
```bash
python scripts/batch_asr_transcribe.py
```

### 说明
- 输入语音目录: `data/chat-sample/`
- 输出转写目录: `data/processed/transcripts/`
- 支持断点续传，不会重复转写已处理的文件

---

## 6. 对话回放测试工具 (playback_test.py)
### 功能
- 加载黄金测试数据集，自动回放历史对话
- 多维度评估机器人回复：正确性、合规性、阶段匹配度
- 生成详细的测试报告，包括通过率、失败案例分析
- 用于版本迭代时的回归测试，确保优化不会引入新问题

### 使用方法
```bash
# 运行所有测试用例并生成报告
python src/tests/playback_test.py

# 运行单个测试用例
python src/tests/playback_test.py --case 628123786631808-20260419104006.json

# 指定报告输出目录
python src/tests/playback_test.py --output-dir reports/
```

### 测试报告
运行完成后会在`data/playback_reports/`目录下生成JSON和Markdown格式的报告，包含：
- 总体通过率和准确率统计
- 按催收阶段、用户类型、抗拒程度的细分统计
- 失败用例详情和原因分析
- 合规违规详情和改进建议

---

## 7. CI/CD集成测试

CI/CD 已通过 GitHub Actions 配置（`.github/workflows/ci.yml`），包含以下测试阶段：

1. **代码检查** — Ruff lint + format check
2. **单元测试** — `src/tests/test_api.py`
3. **核心测试** — 回归测试 + 对话回放测试

### 本地运行 CI 测试
```bash
# 对话回放测试（黄金数据集回归测试）
python src/tests/playback_test.py

# 带通过率阈值（CI 模式）
python src/tests/playback_test.py --ci-mode --min-pass-rate 0.90
```

如果测试不通过，CI 流程会自动失败，阻止代码合并。

---

## 8. 离线合成对照评估工具 (offline_evaluation.py)
### 功能
- 基于历史人工催收数据，模拟机器人在相同场景下的催收效果
- 多维度对比机器人与人工的表现：成功率、回款金额、回款天数
- 预测机器人上线后的真实业务效果，为上线决策提供数据支持
- 分场景分析机器人的优劣势，指明优化方向

### 前置准备
1. 准备历史催收数据，放到`data/historical/`目录下，格式参考示例文件
2. 历史数据需要包含：对话记录、实际催收结果、回款金额、回款天数等信息

### 使用方法
```bash
# 运行完整评估，使用所有历史数据
python src/tests/offline_evaluation.py

# 抽样评估，使用前100个样本
python src/tests/offline_evaluation.py --sample-size 100

# 评估单个案例
python src/tests/offline_evaluation.py --case 628123786631808-20260419104006

# 指定历史数据目录和报告输出目录
python src/tests/offline_evaluation.py --historical-data-path ./my_data/ --output-dir ./reports/
```

### 评估报告
运行完成后会在`data/offline_evaluation_reports/`目录下生成JSON和Markdown格式的报告，包含：
- 核心指标对比：成功率、回款金额、回款天数
- 上线决策结论：是否达到上线标准
- 预期业务价值：成本节约、效率提升等
- 分场景分析：按用户类型、催收阶段、抗拒程度细分对比
- 优化建议：优先需要优化的场景和方向

### 预测模型
内置基于业务经验的回款预测模型，支持后续优化：
- 多因子加权计算回款概率：用户承诺、抗拒程度、通话时长、回复相关性、合规性
- 可根据实际业务数据训练调整权重，提高预测准确率
- 预测结果与真实效果相关性目标≥85%

---

## 9. 多模态语音仿真测试工具 (voice_simulation_test.py)
### 功能
- 端到端模拟真实语音交互全链路，覆盖ASR识别、对话处理、TTS合成三个核心环节
- 支持多场景测试：印尼各地口音模拟（爪哇、巽他、巴厘、巴布亚等）、各种背景噪音模拟（交通、人群、风噪、回声等）、用户打断场景模拟
- 统计全链路核心指标：ASR识别准确率、机器人响应延迟、单轮对话延迟、用户打断处理成功率、合规违规率、TTS语音自然度
- 提供详细的性能分析和优化建议，保障上线后的用户体验

### 前置准备
1. 准备语音测试用例，放到`data/voice_test_cases/`目录下，格式参考示例文件
2. 准备真实语音样本，覆盖各种口音和噪音场景
3. （可选）集成真实的ASR和TTS服务，替换默认的模拟客户端

### 使用方法
```bash
# 运行所有语音测试用例
python src/tests/voice_simulation_test.py

# 抽样测试，使用前50个用例
python src/tests/voice_simulation_test.py --sample-size 50

# 运行单个测试用例
python src/tests/voice_simulation_test.py --case VOICE_TEST_001

# 仅测试特定口音的用例
python src/tests/voice_simulation_test.py --filter-accent javanese

# 仅测试特定噪音场景的用例
python src/tests/voice_simulation_test.py --filter-noise traffic

# 指定测试用例目录和报告输出目录
python src/tests/voice_simulation_test.py --test-cases-dir ./my_cases/ --output-dir ./reports/
```

### 测试报告
运行完成后会在`data/voice_simulation_reports/`目录下生成JSON和Markdown格式的报告，包含：
- 核心指标汇总：整体成功率、ASR准确率、各环节延迟、打断处理成功率、合规率、TTS自然度
- 分维度对比分析：不同口音表现、不同噪音环境表现、不同对话场景表现
- 错误分析：按错误类型分类统计，给出针对性优化建议
- 上线评估：自动判断所有指标是否达到上线标准，给出明确的上线决策建议

### 合格标准（可根据业务需求调整）
- 整体成功率 ≥ 90%
- ASR平均识别准确率 ≥ 85%
- 机器人平均响应延迟 ≤ 1.5s
- 平均单轮对话延迟 ≤ 3.0s
- 用户打断处理成功率 ≥ 90%
- 合规违规率 ≤ 5%
- TTS语音自然度 ≥ 90%

### 扩展说明
- 默认使用模拟的ASR和TTS客户端，方便快速测试
- 实际使用时，只需替换`MockASRClient`和`MockTTSClient`为真实的服务客户端即可
- 支持根据业务需求自定义指标阈值和测试场景

---

## 数据目录说明
```
data/
├── chat-sample/                  # 原始语音文件
├── processed/
│   └── transcripts/              # 转写后的文本文件
├── behavior_analysis/
│   ├── customer_behavior_analysis.json  # 行为分析报告
│   └── customer_response_corpus.json    # 生成式模拟器语料库
├── test_reports/                 # 批量测试报告
└── robustness_tests/             # 鲁棒性测试报告
```
