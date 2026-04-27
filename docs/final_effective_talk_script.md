# 智能催收话术库 - 最终版

## 🎯 核心成功要素（基于246条对话分析）

### 1. 最有效的话术（必须包含）
| 话术 | 成功率提升 | 使用场景 |
|------|------------|----------|
| **...** (适当停顿) | ⭐⭐⭐ 最高 | 开场后、客户回应后 |
| **Ya, ya, ya.** (多次确认) | ⭐⭐⭐ 高 | 约定时间后 |
| **Iya.** | ⭐⭐ 中 | 确认客户理解后 |
| **Halo?** | ⭐⭐ 中 | 开场 |
| **Terima kasih.** | ⭐⭐ 中 | 结尾 |

### 2. 必须避免的话术
| 话术 | 问题 |
|------|------|
| **Ya.** (单次确认) | 太简短，缺乏承诺感 |
| **Gimana?** (怎么样?) | 开放式问题，容易被拒绝 |
| **Oke.** (单次确认) | 缺乏跟进 |
| **开场白过长** | 引起客户反感 |
| **Terima kasih kerana menonton.** | 与场景不符 |
| **Sibuk.** (让客户说忙) | 失败前兆 |

---

## 📋 不同环节的话术策略

### H2环节（早期催收，成功率73%）

#### 目标
利用客户刚逾期、还款意愿较高的特点，快速建立信任并约定时间

#### 标准流程模板
```
[1] AGENT: Halo?
    ... (适当停顿 1-2秒)
[2] AGENT: Halo, selamat pagi Pak/Bu.
    CUSTOMER: Pagi.
[3] AGENT: ... (适当停顿)
    AGENT: Saya dari aplikasi Extra.
[4] AGENT: Untuk pembayaran pinjaman, kapan bisa bayar Pak/Bu?
    CUSTOMER: Jam 5.
[5] AGENT: Ya, ya, ya. Baik, jam 5 ya Pak/Bu.
    CUSTOMER: Iya.
[6] AGENT: Saya tunggu ya.
    CUSTOMER: Terima kasih.
[7] AGENT: Terima kasih. Selamat pagi.
```

#### 关键点
- ✅ 开头用 "Halo?" 而不是长句
- ✅ 必须有适当停顿 (...)
- ✅ 用 "Ya, ya, ya." 多次确认
- ✅ 明确约定时间
- ✅ 说 "Saya tunggu ya." (我等您)
- ✅ 结尾用 "Terima kasih."

---

### H1环节（中期催收，成功率38.9%）

#### 目标
比H2更直接一点，但仍然保持礼貌

#### 标准流程模板
```
[1] AGENT: Halo?
    ... (停顿)
[2] AGENT: Halo, selamat siang Pak/Bu.
[3] AGENT: Saya dari aplikasi Extra. Untuk pinjaman yang sudah jatuh tempo.
[4] AGENT: Kapan bisa melakukan pembayaran?
    CUSTOMER: Besok.
[5] AGENT: Besok jam berapa ya?
    CUSTOMER: Jam 3.
[6] AGENT: Ya, ya. Oke, besok jam 3 ya Pak/Bu. Saya tunggu.
[7] AGENT: Terima kasih.
```

#### 改进建议
- ✅ 比H2稍微直接提到逾期
- ✅ 但仍然保持礼貌
- ✅ 仍然需要适当停顿和多次确认
- ❌ 避免直接指定时间 ("Jam 4, bisa.")

---

### S0环节（晚期催收，成功率37.9%）

#### 目标
最困难的环节，需要更有策略

#### 标准流程模板（改进版）
```
[1] AGENT: Halo?
    ... (停顿)
[2] AGENT: Halo, selamat sore Pak/Bu.
[3] AGENT: Saya dari aplikasi Extra.
[4] AGENT: Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu.
    ... (停顿)
[5] AGENT: Bagaimana rencana pembayaran Pak/Bu?
    CUSTOMER: Saya akan bayar minggu ini.
[6] AGENT: Minggu ini? Bagus, hari apa ya?
    CUSTOMER: Hari Selasa.
[7] AGENT: Hari Selasa jam berapa?
    CUSTOMER: Jam 2 siang.
[8] AGENT: Ya, ya, ya. Oke, hari Selasa jam 2 ya Pak/Bu. Saya tunggu.
    CUSTOMER: Iya.
[9] AGENT: Terima kasih. Selamat sore.
```

#### 关键点
- ✅ 仍然用简洁开场 "Halo?"
- ✅ 仍然需要适当停顿
- ✅ 用引导性问题而不是开放式问题
- ✅ 把模糊承诺 ("minggu ini") 变成具体时间
- ✅ 多次确认
- ❌ 避免开放式问题 "Gimana?"
- ❌ 避免只用 "Ya." 回应

---

## 🏗️ 对话状态机设计

### 状态定义

#### 1. 开场 (GREETING)
**话术库**
- "Halo?" (首选)
- "Halo."
- "Hello?"
- "Hello, selamat pagi."

**转换条件**
- 客户回应 → 到状态2

---

#### 2. 确认身份 (IDENTIFY)
**话术库**
- "Saya dari aplikasi Extra."
- "Halo, selamat pagi Pak/Bu."
- "Saya dari aplikasi Extra untuk pinjaman."

**转换条件**
- 客户确认 → 到状态3

---

#### 3. 说明目的 (PURPOSE)
**话术库（按环节）**
- **H2**: "Untuk pinjaman ya Pak/Bu."
- **H1**: "Untuk pinjaman yang sudah jatuh tempo."
- **S0**: "Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu."

**转换条件**
- 客户表示理解 → 到状态4

---

#### 4. 询问时间 (ASK_TIME)
**话术库（按环节）**
- **H2**: "Kapan bisa bayar Pak/Bu?"
- **H1**: "Kapan bisa melakukan pembayaran?"
- **S0**: "Bagaimana rencana pembayaran Pak/Bu?"

**话术库（引导式）**
- "Jam berapa ya?"
- "Hari ini jam berapa?"
- "Besok jam berapa?"

**转换条件**
- 客户给时间 → 到状态5
- 客户模糊回应 → 追问

---

#### 5. 约定时间 (COMMIT_TIME)
**话术库**
- "Oke, jam [X] ya Pak/Bu."
- "Ya, ya, ya. Jam [X] ya Pak/Bu."
- "Baik, saya tunggu jam [X]."
- "Saya tunggu ya Pak/Bu."

**转换条件**
- 客户确认 → 到状态6

---

#### 6. 确认确认 (CONFIRM)
**话术库（关键！必须多次确认）**
- "Ya, ya, ya."
- "Ya, ya."
- "Iya."
- "Baik."
- "Oke, oke."

**转换条件**
- 确认后 → 到状态7

---

#### 7. 礼貌结束 (CLOSE)
**话术库**
- "Terima kasih."
- "Terima kasih. Selamat pagi/siang/sore."
- "Terima kasih, Pak/Bu."
- "Siap, sampai jumpa."

**转换条件**
- 结束对话

---

## 🎯 各环节最佳话术组合

### H2（成功率73%）
```
开场: Halo?
... (停顿)
确认: Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra.
目的: Untuk pinjaman ya Pak/Bu.
询问: Kapan bisa bayar?
约定: Oke, jam [X] ya Pak/Bu.
确认: Ya, ya, ya.
等待: Saya tunggu ya.
结束: Terima kasih.
```

### H1（改进版，目标成功率 >60%）
```
开场: Halo?
... (停顿)
确认: Halo, selamat siang Pak/Bu. Saya dari aplikasi Extra.
目的: Untuk pinjaman yang sudah jatuh tempo.
询问: Kapan bisa melakukan pembayaran?
约定: Ya, ya. Oke, jam [X] ya Pak/Bu.
确认: Iya.
等待: Saya tunggu ya.
结束: Terima kasih.
```

### S0（改进版，目标成功率 >50%）
```
开场: Halo?
... (停顿)
确认: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
目的: Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu.
询问: Bagaimana rencana pembayaran Pak/Bu?
约定: Ya, ya, ya. Oke, [具体时间] ya Pak/Bu.
确认: Baik.
等待: Saya tunggu ya.
结束: Terima kasih.
```

---

## ⚠️ 常见错误及修正

### 错误1: 只用 "Ya." 回应
```
❌ 错误
CUSTOMER: Jam 5.
AGENT: Ya.
```

```
✅ 正确
CUSTOMER: Jam 5.
AGENT: Ya, ya, ya. Oke, jam 5 ya Pak/Bu.
```

---

### 错误2: 开放式问题太多
```
❌ 错误
AGENT: Gimana?
CUSTOMER: Sibuk.
```

```
✅ 正确
AGENT: Kapan bisa bayar Pak/Bu?
CUSTOMER: Besok.
AGENT: Besok jam berapa ya?
```

---

### 错误3: 开场白太长
```
❌ 错误
AGENT: Halo, Pak. Saya dari aplikasi Extra Uang Now. Halo, Bapak. Bapak, jangan kurang-kurang mendengar, Pak.
```

```
✅ 正确
AGENT: Halo?
AGENT: Halo, selamat pagi Pak/Bu.
AGENT: Saya dari aplikasi Extra.
```

---

### 错误4: 缺少停顿
```
❌ 错误
AGENT: Halo? Selamat pagi. Saya dari aplikasi Extra. Kapan bisa bayar?
```

```
✅ 正确
AGENT: Halo?
... (停顿)
AGENT: Halo, selamat pagi Pak/Bu.
... (停顿)
AGENT: Saya dari aplikasi Extra.
... (停顿)
AGENT: Kapan bisa bayar Pak/Bu?
```

---

## 📊 话术使用频率建议

### 高成功率话术（频率从高到低）
1. "Halo?" - 每场必用
2. "..." (停顿) - 每场至少3次
3. "Ya, ya, ya." - 约定时间后必用
4. "Iya." - 确认时用
5. "Terima kasih." - 结束时必用
6. "Saya tunggu ya." - 重要
7. "Halo, selamat pagi." - 开场问候
8. "Ya, ya." - 次要确认

---

## 🔍 检测失败前兆

### 客户回应需要警惕
- "Sibuk." (忙) → 重新约定时间
- "Nanti ya." (等一下) → 追问具体时间
- "Gak bisa." (不行) → 询问原因，提供替代方案
- "..." (沉默) → 主动引导

### 自己话术需要避免
- 只用 "Ya." 回应
- 用 "Gimana?"
- 长开场白
- 忘记说 "Saya tunggu ya."

---

## 🚀 A/B测试建议

### 测试1: 停顿 vs 不停顿
- **A组**: 有停顿 (...)
- **B组**: 无停顿
- **假设**: A组成功率 > B组

### 测试2: 单次确认 vs 多次确认
- **A组**: "Ya, ya, ya."
- **B组**: "Ya."
- **假设**: A组成功率 > B组

### 测试3: 简洁开场 vs 复杂开场
- **A组**: "Halo?"
- **B组**: 长开场白
- **假设**: A组成功率 > B组

---

## 📝 最终检查清单

每次对话完成前，检查：
- ✅ 有没有用适当停顿 (...)？
- ✅ 有没有多次确认 (Ya, ya, ya.)？
- ✅ 开场是不是简洁 (Halo?)？
- ✅ 有没有说 "Saya tunggu ya."？
- ✅ 有没有说 "Terima kasih."？
- ✅ 有没有明确约定具体时间？
- ✅ 有没有避免用 "Gimana?"？
- ✅ 有没有避免只用 "Ya."？

---

## 🎊 总结

### 成功催收的三个关键
1. **停顿 (...)** - 给客户思考时间
2. **多次确认** - "Ya, ya, ya." 增强承诺感
3. **简洁开场** - "Halo?" 而不是长句

### 一句话总结
**先停顿，再确认，用词简洁，结尾礼貌。**

---

*注：基于246条有效对话（H2/H1/S0）的完整分析*
