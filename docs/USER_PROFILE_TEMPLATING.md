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

## 下一步开发

### Phase 1: 数据模型
- 定义用户画像数据结构
- 定义业务状态数据结构
- 数据库字段设计

### Phase 2: 模板引擎
- 变量替换引擎
- 条件判断逻辑
- 话术选择策略

### Phase 3: 管理界面
- 模板编辑界面
- 规则配置界面
- 变量预览界面
