# 批量测试工具使用指南

## 概述
`src/tests/run_small_scale_test.py`是用于大规模自动化测试智能催收系统的工具，支持多维度参数配置、并发测试、多格式报告生成和版本对比功能，能够快速评估系统在不同场景下的表现。

## 功能特点
- ✅ **多维度测试配置**：支持按催收阶段、用户类型、抗拒程度等参数组合测试
- ✅ **多模拟器支持**：同时支持规则模拟器和生成式客户模拟器
- ✅ **高并发测试**：支持多线程并发执行，大幅提升测试效率
- ✅ **多格式报告**：支持生成Markdown和CSV格式的测试报告
- ✅ **版本对比**：支持与历史测试报告对比，快速发现效果变化
- ✅ **下钻分析**：支持按各个维度统计分析结果，定位问题场景

## 使用方法

### 基础使用
```bash
# 默认使用规则模拟器运行1000次测试
python src/tests/run_small_scale_test.py

# 使用生成式模拟器运行2000次测试
python src/tests/run_small_scale_test.py 2000 --use-generative
```

### 定向场景测试
```bash
# 仅测试H1阶段（宽限期前1天）的抗拒型用户
python src/tests/run_small_scale_test.py 1000 --use-generative --chat-groups H1 --personas resistant

# 测试高抗拒程度场景
python src/tests/run_small_scale_test.py 500 --use-generative --resistance-levels high very_high

# 组合多个条件测试
python src/tests/run_small_scale_test.py 1000 --use-generative --chat-groups H2 H1 --personas cooperative busy negotiating --resistance-levels low medium
```

### 生成报告
```bash
# 生成Markdown格式报告，包含失败案例日志
python src/tests/run_small_scale_test.py 1000 --use-generative --generate-md --include-logs

# 生成CSV格式结果，用于后续数据分析
python src/tests/run_small_scale_test.py 2000 --use-generative --generate-csv

# 自定义报告输出前缀
python src/tests/run_small_scale_test.py 1000 --use-generative --generate-md --output-prefix v1.0.0_test
```

### 版本对比
```bash
# 运行新版本测试并与旧版本报告对比
python src/tests/run_small_scale_test.py 1000 --use-generative --generate-md --compare reports/v0.9.0_test.md
```

### 性能优化
```bash
# 使用更高并发数提升测试速度（默认20，建议不超过CPU核心数的2倍）
python src/tests/run_small_scale_test.py 5000 --use-generative --concurrency 50
```

## 参数说明

### 位置参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `num_tests` | 测试总次数 | 1000 |

### 可选参数
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--use-generative` | 使用数据驱动生成式客户模拟器，不指定则使用规则模拟器 | 关闭 |
| `--chat-groups` | 指定测试的催收阶段，可多选：`H2`(宽限期前2天)/`H1`(宽限期前1天)/`S0`(实质性逾期) | 全部 |
| `--personas` | 指定测试的客户类型，可多选：`cooperative`(合作型)/`busy`(忙碌型)/`negotiating`(协商型)/`resistant`(抗拒型)/`silent`(沉默型)/`forgetful`(健忘型)/`excuse_master`(借口大师) | 全部 |
| `--resistance-levels` | 指定测试的抗拒程度，可多选：`very_low`/`low`/`medium`/`high`/`very_high` | 全部 |
| `--include-logs` | 在报告中包含失败案例的完整对话日志 | 关闭 |
| `--concurrency` | 并发测试线程数 | 20 |
| `--output-prefix` | 输出报告文件的前缀 | `test_report` |
| `--compare` | 指定历史报告路径，进行版本对比 | 无 |
| `--generate-md` | 生成Markdown格式的详细测试报告 | 关闭 |
| `--generate-csv` | 生成CSV格式的原始测试结果 | 关闭 |
| `-h, --help` | 显示帮助信息 | - |

## 输出报告说明

### Markdown报告包含内容
1. **总体统计**：总测试次数、成功率、平均对话轮数、平均时长等核心指标
2. **催收阶段分布**：不同逾期阶段的成功率对比
3. **用户类型分布**：不同类型用户的成功率对比
4. **抗拒程度分布**：不同抗拒程度的成功率对比
5. **失败原因分析**：各类失败场景的占比统计
6. **失败案例日志**：可选包含，展示失败对话的完整流程，便于定位问题

### CSV报告包含内容
每条测试的详细数据：
- 测试ID、催收阶段、用户类型、抗拒程度
- 最终结果、对话轮数、通话时长
- 失败原因（如果失败）
- 完整对话日志

## 对比功能说明
使用`--compare`参数可以对比当前测试结果与历史测试结果的差异：
- 核心指标变化（成功率、平均轮数等）
- 各维度下的效果变化
- 自动标记提升和下降的场景
- 帮助快速评估版本优化效果

## 最佳实践
1. **版本发布前**：运行全量测试（≥5000次），覆盖所有场景，生成完整报告
2. **功能优化后**：运行定向测试，对比优化前后的效果变化
3. **CI/CD集成**：每次代码提交自动运行核心场景测试，保障基础功能不 regression
4. **问题定位**：针对失败率高的场景，增加测试次数，导出详细日志分析