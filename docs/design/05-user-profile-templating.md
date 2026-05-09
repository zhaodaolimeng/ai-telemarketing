# 用户画像与话术模板化配置

## 概述

支持丰富的用户信息输入，并将这些信息结合到话术模板中，实现个性化对话。

---

## 用户信息模型

### 1. 用户个人信息 (User Demographics)
```yaml
user_profile:
  # 基础信息
  name: "Pak Budi"              # 客户称呼
  gender: "male"                # 性别
  age: 45                       # 年龄
  marital_status: "married"     # 婚姻状况
  education_level: "college"    # 教育程度
  
  # 联系方式
  phone: "62812xxxxxx"          # 电话号码
  address: "Jakarta Selatan"    # 地址
  
  # 职业/收入
  occupation: "employee"         # 职业
  income_level: "medium"         # 收入等级 (low/medium/high)
  employment_status: "employed"  # 就业状态
  
  # 家庭信息
  family_size: 4                 # 家庭人数
  dependents: 2                 # 被抚养人数
  house_ownership: "owned"      # 住房状况
```

### 2. 用户业务状态 (Business Status)
```yaml
business_context:
  # 产品信息
  product_name: "Extra Cash"    # 产品名称
  loan_amount: 5000000          # 借款金额
  tenure: 12                    # 期数
  interest_rate: 12.5           # 利率
  
  # 还款状态
  current_stage: "H2"           # 当前环节 (H2/H1/S0)
  days_overdue: 15              # 逾期天数
  amount_overdue: 2500000       # 逾期金额
  total_outstanding: 5000000    # 剩余本金
  missed_payments: 1            # 已逾期期数
  
  # 历史记录
  history_repayment_rate: 0.85   # 历史还款率
  number_of_loans: 3            # 历史借款次数
  last_payment_date: "2026-04-01"  # 上次还款日期
  last_contact_date: "2026-04-15"  # 上次联系日期
  
  # 催收状态
  times_contacted_this_cycle: 2  # 本周期已联系次数
  last_contact_result: "promised_but_default"  # 上次联系结果
  previously_agreed_time: "17:00"  # 上次约定时间
```

---

## 话术模板变量设计

### 变量命名规范
- 使用 `{variable_name}` 格式
- 支持点号访问嵌套属性
- 支持默认值：`{variable_name|default_value}`

### 变量列表

#### 1. 通用变量
| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{name}` | 客户称呼 | Pak Budi |
| `{stage}` | 当前环节 | H2 |
| `{days_overdue}` | 逾期天数 | 15 |
| `{amount_overdue}` | 逾期金额 | 2500000 |
| `{total_outstanding}` | 剩余金额 | 5000000 |
| `{loan_amount}` | 原始借款额 | 5000000 |
| `{product_name}` | 产品名称 | Extra Cash |

#### 2. 用户信息变量
| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{gender}` | 性别 | male |
| `{age}` | 年龄 | 45 |
| `{occupation}` | 职业 | employee |
| `{income_level}` | 收入等级 | medium |
| `{family_size}` | 家庭人数 | 4 |
| `{dependents}` | 被抚养人数 | 2 |

#### 3. 历史记录变量
| 变量 | 说明 | 示例值 |
|------|------|--------|
| `{history_repayment_rate}` | 历史还款率 | 0.85 |
| `{number_of_loans}` | 历史借款次数 | 3 |
| `{last_payment_date}` | 上次还款日期 | 2026-04-01 |
| `{times_contacted}` | 已联系次数 | 2 |
| `{last_contact_result}` | 上次联系结果 | promised_but_default |
| `{previously_agreed_time}` | 上次约定时间 | 17:00 |

---

## 话术模板示例

### 示例1: 欢迎话术 - 根据历史记录调整
```yaml
greeting:
  - greeting_standard: "Halo {name}, selamat siang. Saya dari {product_name}."
  - greeting_with_history: "Halo {name}! Sudah lama tidak mendengar kabar Anda."
  - greeting_remind_last: "Halo {name}! Masih ingat janji Anda sebelumnya jam {previously_agreed_time}?"
```

### 示例2: 目的说明 - 根据逾期天数调整
```yaml
purpose:
  - purpose_mild: "Saya ingin mengingatkan tentang pembayaran pinjaman Anda yang akan jatuh tempo."
  - purpose_medium: "Saya ingin bertanya tentang pembayaran pinjaman Anda yang sudah terlambat {days_overdue} hari."
  - purpose_serious: "Saya perlu berbicara tentang pembayaran yang terlambat {days_overdue} hari dengan jumlah {amount_overdue}."
```

### 示例3: 询问时间 - 根据用户信息调整
```yaml
ask_time:
  - ask_time_simple: "Kapan kira-kira Anda bisa melakukan pembayaran?"
  - ask_time_consider_occupation: "Mengingat pekerjaan Anda sebagai {occupation}, kapan waktu yang nyaman bagi Anda?"
  - ask_time_consider_history: "Dengan catatan pembayaran sebelumnya, jam berapa yang bisa Anda janjikan?"
```

### 示例4: 确认 - 根据历史调整
```yaml
confirm:
  - confirm_standard: "Baik {name}, saya catat jam {time} ya. Terima kasih!"
  - confirm_remind_history: "Baik {name}, saya catat jam {time}. Ini sudah sesuai janji Anda kemarin, tolong ingat ya."
```

---

## 话术选择策略

### 策略1: 根据环节选择
```yaml
stage_selection:
  H2:
    - purpose: purpose_mild
  H1:
    - purpose: purpose_medium
  S0:
    - purpose: purpose_serious
```

### 策略2: 根据用户画像选择
```yaml
profile_selection:
  low_income:
    - ask_time: ask_time_simple
  medium_income:
    - ask_time: ask_time_consider_occupation
  high_income:
    - ask_time: ask_time_simple
```

### 策略3: 根据历史记录选择
```yaml
history_selection:
  first_contact:
    - greeting: greeting_standard
  second_contact_with_broken_promise:
    - greeting: greeting_remind_last
  good_repayment_history:
    - confirm: confirm_standard
  bad_repayment_history:
    - confirm: confirm_remind_history
```

---

## 模板配置结构

```yaml
# 话术库结构示例
scripts:
  H2:
    greeting:
      - text: "Halo {name}, selamat siang."
        conditions:
          - times_contacted = 0
      - text: "Halo {name}! Sudah lama tidak mendengar kabar Anda."
        conditions:
          - times_contacted > 0
    purpose:
      - text: "Saya ingin mengingatkan tentang pembayaran Anda."
        conditions:
          - days_overdue <= 15
    ask_time:
      - text: "Kapan kira-kira Anda bisa bayar?"
        conditions:
          - true
    push:
      - text: "Jam 5 sore masih bisa, {name}?"
        conditions:
          - true
    confirm:
      - text: "Baik, saya catat jam {time}."
        conditions:
          - true
    close:
      - text: "Terima kasih {name}!"
        conditions:
          - true
```

---

## 优先级规则

1. 环节匹配 (H2/H1/S0) → 最高优先级
2. 用户画像 (income_level, occupation)
3. 历史记录 (good/bad repayment, broken promise)
4. 默认话术 → 最低优先级

---

## 画像驱动施压策略（2026-05-08）

### 策略总览

基于 CSV 中已有的 39 个字段，将用户画像维度映射为可执行的话术策略。当前 chatbot 仅利用了 `chat_group` 一个画像维度做话术选择，以下策略可将有效字段全部用起来。

---

### 策略1：新客 vs 老客

| 画像判断 | 判定条件 | 施压策略 | 话术方向 |
|---------|---------|---------|---------|
| 纯新客 | `total_loan_cnt = 1` | 教育型 | 解释逾期后果、建立还款意识、语气温和 |
| 有借有还 | `paidoff_loan_cnt >= 2` | 认同型 | 肯定历史记录、"这次为什么不一样"、唤起责任感 |
| 多次借贷 | `total_loan_cnt >= 5` | 依赖型 | 强调长期合作关系、提醒信用记录影响后续借款 |
| 首次违约 | `paidoff_loan_cnt > 0` 且当前逾期 | 落差型 | 对比历史良好记录与当前状态、"之前都能按时还的" |

### 策略2：收入适配

| 画像判断 | 判定条件 | 施压策略 | 话术方向 |
|---------|---------|---------|---------|
| 高收入低负债 | `monthly_income / approved_amount > 5` | 直接施压 | 质疑为何不还、"您的收入完全能覆盖" |
| 中等收入 | `monthly_income / approved_amount 2~5` | 方案引导 | 给展期/部分还款选项、强调灵活性 |
| 低收入高负债 | `monthly_income / approved_amount < 2` | 减轻压力 | 优先推展期、强调"我们理解困难"、提供最小还款额 |
| 支出占比高 | `expenditure / monthly_income > 0.7` | 同理型 | 承认经济压力、强调展期是最优解 |

### 策略3：承诺违约升级

| 画像判断 | 判定条件 | 施压策略 | 话术方向 |
|---------|---------|---------|---------|
| 首次联系 | `promise_repay_date` 为空 | 标准流程 | 正常话术 |
| 曾承诺未兑现 | `promise_repay_date` 非空且仍逾期 | 升级追问 | "上次您承诺X日但未付款，这次需要更明确的时间" |
| 多次承诺多次违约 | 历史联系记录 ≥ 2 次未履约 | 最后通牒 | 告知后果、限定最后期限、准备上报 |

### 策略4：人口特征适配

| 画像维度 | 判定条件 | 策略调整 |
|---------|---------|---------|
| 年龄 18-25 | 年轻用户 | 语气更轻松、多用 APP/转账等数字支付引导 |
| 年龄 26-45 | 中年用户 | 标准话术、强调家庭责任 |
| 年龄 46+ | 年长用户 | 语速暗示放缓、多确认理解、避免复杂选项 |
| 已婚有子女 | `marital_status=2` 且 `number_of_children>0` | 唤起家庭责任感、"家人的信用也会受影响" |
| 低教育程度 | `education <= 2` | 简化话术、避免法律/金融术语、多用比喻 |

### 策略5：职业/行业适配

| 画像维度 | 判定条件 | 策略调整 |
|---------|---------|---------|
| 固定收入（雇员） | `occupation=1` | 建议发薪日前后还款 |
| 自雇/自由职业 | `occupation=2` | 建议交易高峰时段后还款 |
| 农业/渔业 | `industry` 含 `KAB` | 建议收成季节、语气更接地气 |
| 高流动性职业 | `industry` 含运输/物流 | 建议休息日/非出车时段 |

---

### 实施优先级

| 优先级 | 策略 | 原因 |
|--------|------|------|
| P0 | 策略1（新客/老客） | 数据现成、逻辑简单、差异感知明显 |
| P0 | 策略3（承诺违约升级） | 直接提升回款率、不需要复杂画像计算 |
| P1 | 策略2（收入适配） | 需要计算比值但逻辑清晰、对展期转化有帮助 |
| P2 | 策略4（人口特征） | 需要较多话术变体、边际收益相对小 |
| P2 | 策略5（职业适配） | 需要行业分类映射表、部分字段为文本需清洗 |

---

## 紧急联系人施压策略

### 前提

借款人已在申请贷款时授权联系紧急联系人，无合规风险。

### 策略设计

| 阶段 | 触发条件 | 动作 | 话术要点 |
|------|---------|------|---------|
| H2 | 不触发 | 宽限期内不打扰第三方 | — |
| H1 | 本人 ≥ 2 次未接/拒绝 | 联系紧急联系人 | 不透露债务、"Bapak/Ibu {name} 有重要事宜请其回电" |
| S0 | 本人 ≥ 3 次联系失败 | 逐个联系所有紧急联系人 | 同上，增加紧迫感但依旧不透露金额和性质 |

### 核心技术要点

1. **隐私保护**：对紧急联系人仅告知"请转达回电"，不透露债务金额、逾期天数、借款产品
2. **联系人顺序**：按优先级逐个联系（主联系人 → 次联系人），间隔 ≥ 2 小时避免骚扰
3. **去重**：同一号码 3 天内不重复拨打
4. **状态追踪**：记录哪些联系人已通知、是否承诺转达、是否有反馈

### 数据库扩展

```sql
ALTER TABLE user_profile ADD COLUMN emergency_contacts JSON;
-- 格式: [{"name": "Ibu Sari", "phone": "62812xxx", "relation": "ibu", "priority": 1}, ...]
ALTER TABLE contact_log ADD COLUMN contact_type TEXT;  -- 'direct' / 'emergency'
ALTER TABLE contact_log ADD COLUMN contact_result TEXT; -- 'notified' / 'promised_to_relay' / 'no_answer'
```

---

## 下一步开发

### Phase 1: 数据模型
- 定义用户画像数据结构
- 定义业务状态数据结构
- 数据库字段设计（新增 `emergency_contacts`、`contact_log` 扩展）

### Phase 2: 模板引擎
- 变量替换引擎（扩展至画像维度变量）
- 条件判断逻辑（支持画像条件匹配）
- 话术选择策略（画像维度 × 催收阶段 交叉选优）

### Phase 3: 管理界面
- 模板编辑界面
- 规则配置界面
- 变量预览界面
