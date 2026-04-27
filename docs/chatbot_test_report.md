# 智能催收对话机器人 - 测试报告

## 测试概要

- **测试日期**: 2026-04-26
- **测试场景数**: 10
- **成功场景**: 7
- **失败场景**: 3
- **总体成功率**: 70.0%

---

## 机器人架构

### 状态机设计

```
INIT → GREETING → IDENTIFY → PURPOSE → ASK_TIME → COMMIT_TIME → CONFIRM → CLOSE
                   ↓
                FAILED
```

### 状态定义

| 状态 | 说明 | 关键话术 |
|------|------|----------|
| INIT | 初始状态 | Halo? |
| GREETING | 问候 | Halo? / Halo. / Hello? |
| IDENTIFY | 身份确认 | Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra. |
| PURPOSE | 说明目的 | Untuk pinjaman ya Pak/Bu. |
| ASK_TIME | 询问时间 | Kapan bisa bayar Pak/Bu? / Jam berapa ya? |
| COMMIT_TIME | 约定时间 | Oke, jam X ya Pak/Bu. |
| CONFIRM | 确认确认 | Ya, ya, ya. / Iya. |
| CLOSE | 结束 | Saya tunggu ya. Terima kasih. |

---

## 话术库

### 按环节分类

#### H2 (早期催收，成功率73%)

**问候类**
- "Halo?"
- "Halo."
- "Hello?"

**确认类**
- "Halo, selamat pagi Pak/Bu."
- "Halo, selamat siang Pak/Bu."
- "Halo, selamat sore Pak/Bu."

**身份类**
- "Saya dari aplikasi Extra."

**目的类**
- "Untuk pinjaman ya Pak/Bu."

**询问时间类**
- "Kapan bisa bayar Pak/Bu?"
- "Jam berapa ya?"

**约定时间类**
- "Oke, {time} ya Pak/Bu."
- "Ya, ya, ya. {time} ya Pak/Bu."
- "Baik, saya tunggu {time}."

**确认类**
- "Ya, ya, ya."
- "Iya."
- "Baik."
- "Ya, ya."

**等待类**
- "Saya tunggu ya."
- "Saya tunggu {time}."

**结束类**
- "Terima kasih."
- "Terima kasih. Selamat pagi."
- "Terima kasih. Selamat siang."
- "Terima kasih. Selamat sore."

**追问类**
- "Jam berapa tepatnya?"
- "Hari ini jam berapa ya?"

---

#### H1 (中期催收，成功率38.9%)

**问候类**
- "Halo?"
- "Halo."
- "Halo, selamat pagi."

**确认类**
- "Halo, selamat pagi Pak/Bu."
- "Halo, selamat siang Pak/Bu."

**身份类**
- "Saya dari aplikasi Extra."

**目的类**
- "Untuk pinjaman yang sudah jatuh tempo."

**询问时间类**
- "Kapan bisa melakukan pembayaran?"
- "Jam berapa ya?"

**约定时间类**
- "Ya, ya. Oke, {time} ya Pak/Bu."
- "Saya tunggu {time}."

**确认类**
- "Ya, ya."
- "Iya."
- "Baik."

**等待类**
- "Saya tunggu ya."

**结束类**
- "Terima kasih."
- "Terima kasih. Selamat siang."

**追问类**
- "Jam berapa tepatnya?"
- "Besok jam berapa ya?"

---

#### S0 (晚期催收，成功率37.9%)

**问候类**
- "Halo?"
- "Halo."

**确认类**
- "Halo, selamat sore Pak/Bu."

**身份类**
- "Saya dari aplikasi Extra."

**目的类**
- "Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu."

**询问时间类**
- "Bagaimana rencana pembayaran Pak/Bu?"
- "Kapan bisa bayar ya?"

**约定时间类**
- "Ya, ya, ya. Oke, {time} ya Pak/Bu."
- "Baik, saya tunggu {time}."

**确认类**
- "Ya, ya, ya."
- "Baik."

**等待类**
- "Saya tunggu ya."

**结束类**
- "Terima kasih."
- "Terima kasih. Selamat sore."

**追问类**
- "Jam berapa tepatnya?"
- "Hari apa ya?"
- "Jam berapa ya?"

---

## 测试结果详解

### 场景1: H2早期 + 合作客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo.
CUSTOMER: Iya?
AGENT: Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Iya.
AGENT: Untuk pinjaman ya Pak/Bu.
CUSTOMER: Oh, ingatnya.
AGENT: Jam berapa ya?
CUSTOMER: Jam 5 ya.
AGENT: Baik, saya tunggu jam 5.
CUSTOMER: Oke.
AGENT: Iya.
CUSTOMER: Oke.
AGENT: Saya tunggu jam 5. Terima kasih. Selamat pagi.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: jam 5

---

### 场景2: H2早期 + 忙碌客户 ❌ FAILED

**对话日志**
```
AGENT: Halo?
CUSTOMER: Ada apa?
AGENT: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Nanti ya.
AGENT: Untuk pinjaman ya Pak/Bu.
CUSTOMER: Saya lagi sibuk.
AGENT: Jam berapa ya?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Nanti ya.
AGENT: Hari ini jam berapa ya?
CUSTOMER: Saya lagi luar.
AGENT: Hari ini jam berapa ya?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Saya lagi luar.
```

**结果**: FAILED
**失败原因**: 客户一直说忙，追问策略无效

---

### 场景3: H2早期 + 协商客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Hello?
CUSTOMER: Ada apa?
AGENT: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya.
AGENT: Untuk pinjaman ya Pak/Bu.
CUSTOMER: Oh, bisa nggak diperpanjang?
AGENT: Kapan bisa bayar Pak/Bu?
CUSTOMER: Minggu ini bisa?
AGENT: Jam berapa tepatnya?
CUSTOMER: Minggu ini bisa?
AGENT: Hari ini jam berapa ya?
CUSTOMER: Besok bisa?
AGENT: Oke, besok ya Pak/Bu.
CUSTOMER: Oke, besok jam 3.
AGENT: Baik.
CUSTOMER: Iya.
AGENT: Saya tunggu besok. Terima kasih. Selamat pagi.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: besok

---

### 场景4: H2早期 + 沉默客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo?
CUSTOMER: (沉默)
AGENT: Halo, selamat siang Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: ...
AGENT: Untuk pinjaman ya Pak/Bu.
CUSTOMER: Oh.
AGENT: Jam berapa ya?
CUSTOMER: Jam 5.
AGENT: Oke, jam 5 ya Pak/Bu.
CUSTOMER: Iya.
AGENT: Ya, ya.
CUSTOMER: Iya.
AGENT: Saya tunggu ya. Terima kasih. Selamat sore.
CUSTOMER: ...
```

**结果**: SUCCESS
**约定时间**: jam 5

---

### 场景5: H1中期 + 合作客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo, selamat pagi.
CUSTOMER: Siang.
AGENT: Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya.
AGENT: Untuk pinjaman yang sudah jatuh tempo.
CUSTOMER: Oh ya.
AGENT: Jam berapa ya?
CUSTOMER: Besok jam 2.
AGENT: Ya, ya. Oke, jam 2 ya Pak/Bu.
CUSTOMER: Ya.
AGENT: Iya.
CUSTOMER: Oke.
AGENT: Saya tunggu ya. Terima kasih. Selamat siang.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: jam 2

---

### 场景6: H1中期 + 协商客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo?
CUSTOMER: Halo.
AGENT: Halo, selamat pagi Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya.
AGENT: Untuk pinjaman yang sudah jatuh tempo.
CUSTOMER: Oh, bisa nggak diperpanjang?
AGENT: Kapan bisa melakukan pembayaran?
CUSTOMER: Besok bisa?
AGENT: Ya, ya. Oke, besok ya Pak/Bu.
CUSTOMER: Oke, besok jam 3.
AGENT: Iya.
CUSTOMER: Iya.
AGENT: Saya tunggu ya. Terima kasih. Selamat siang.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: besok

---

### 场景7: H1中期 + 忙碌客户 ❌ FAILED

**对话日志**
```
AGENT: Halo.
CUSTOMER: Sebentar ya.
AGENT: Halo, selamat siang Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Nanti ya.
AGENT: Untuk pinjaman yang sudah jatuh tempo.
CUSTOMER: Nanti saya hubungi balik.
AGENT: Kapan bisa melakukan pembayaran?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Nanti ya.
AGENT: Jam berapa tepatnya?
CUSTOMER: Saya lagi luar.
```

**结果**: FAILED
**失败原因**: 客户一直回避，追问策略无效

---

### 场景8: S0晚期 + 合作客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo?
CUSTOMER: Sore.
AGENT: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya, betul.
AGENT: Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu.
CUSTOMER: Oh, ingatnya.
AGENT: Kapan bisa bayar ya?
CUSTOMER: Besok jam 2.
AGENT: Ya, ya, ya. Oke, jam 2 ya Pak/Bu.
CUSTOMER: Ya.
AGENT: Baik.
CUSTOMER: Iya.
AGENT: Saya tunggu ya. Terima kasih. Selamat sore.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: jam 2

---

### 场景9: S0晚期 + 协商客户 ⭐ SUCCESS

**对话日志**
```
AGENT: Halo.
CUSTOMER: Ada apa?
AGENT: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya.
AGENT: Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu.
CUSTOMER: Oh, bisa nggak diperpanjang?
AGENT: Kapan bisa bayar ya?
CUSTOMER: Besok bisa?
AGENT: Ya, ya, ya. Oke, besok ya Pak/Bu.
CUSTOMER: Oke, besok jam 3.
AGENT: Baik.
CUSTOMER: Iya.
AGENT: Saya tunggu ya. Terima kasih.
CUSTOMER: Terima kasih.
```

**结果**: SUCCESS
**约定时间**: besok

---

### 场景10: S0晚期 + 抗拒客户 ❌ FAILED

**对话日志**
```
AGENT: Halo?
CUSTOMER: Halo?
AGENT: Halo, selamat sore Pak/Bu. Saya dari aplikasi Extra.
CUSTOMER: Ya, apa?
AGENT: Kita bicara tentang pinjaman yang sudah agak lama ya Pak/Bu.
CUSTOMER: Nanti dulu ya.
AGENT: Bagaimana rencana pembayaran Pak/Bu?
CUSTOMER: Gak bisa.
AGENT: Jam berapa ya?
CUSTOMER: Saya belum punya duit.
AGENT: Jam berapa ya?
CUSTOMER: Saya belum punya duit.
```

**结果**: FAILED
**失败原因**: 客户明确拒绝还款，无法推进

---

## 结果汇总

### 按环节统计

| 环节 | 测试数 | 成功数 | 成功率 |
|------|--------|--------|--------|
| H2 | 4 | 3 | 75.0% |
| H1 | 3 | 2 | 66.7% |
| S0 | 3 | 2 | 66.7% |
| **总计** | **10** | **7** | **70.0%** |

### 按客户类型统计

| 客户类型 | 测试数 | 成功数 | 成功率 |
|----------|--------|--------|--------|
| 合作客户 | 3 | 3 | 100.0% |
| 协商客户 | 3 | 3 | 100.0% |
| 沉默客户 | 1 | 1 | 100.0% |
| 忙碌客户 | 2 | 0 | 0.0% |
| 抗拒客户 | 1 | 0 | 0.0% |

---

## 成功关键因素

### 成功场景的共同特征
1. ✅ **简洁开场白** - "Halo?" / "Halo."
2. ✅ **明确的时间约定** - "Oke, jam X ya Pak/Bu."
3. ✅ **多次确认** - "Ya, ya, ya." / "Iya."
4. ✅ **主动表达等待** - "Saya tunggu ya."
5. ✅ **礼貌结束** - "Terima kasih."

### 失败场景的共同问题
1. ❌ **过度追问** - 客户说忙后继续追问
2. ❌ **缺乏替代方案** - 客户拒绝后无法处理
3. ❌ **单一策略** - 所有情况都用同样话术

---

## 改进建议

### 1. 增加状态转移逻辑

**当前问题**: 客户说"忙"后一直追问
**建议改进**:
```
IF customer says "sibuk" OR "nanti ya" OR "luar":
    → ASK: "Kalau gitu, besok jam berapa bisa?"
    → 或者 OFFER: "Kita janjian besok ya, jam berapa?"
```

### 2. 增加拒绝处理逻辑

**当前问题**: 客户说"gak bisa"后继续追问
**建议改进**:
```
IF customer says "gak bisa" OR "belum punya duit":
    → ASK: "Kapan kira-kira bisa?"
    → 或者 OFFER: "Kalau minggu depan bisa?"
```

### 3. 优化话术库

**增加的话术**:
- "Kalau gitu, besok bisa?"
- "Kapan kira-kira bisa?"
- "Kita janjian besok ya, jam berapa?"

---

## 最终总结

### 成果
1. ✅ **建立完整话术库** - 按H2/H1/S0分类
2. ✅ **实现状态对话机器人** - 7个状态的完整流程
3. ✅ **测试10个场景** - 70%成功率
4. ✅ **覆盖5种客户类型** - 合作/协商/沉默/忙碌/抗拒

### 成功率
- **总体**: 70.0% (7/10)
- **合作客户**: 100.0%
- **协商客户**: 100.0%
- **沉默客户**: 100.0%

### 下一步建议
1. 增加拒绝处理分支
2. 增加忙处理分支
3. 优化S0环节的策略
4. 增加更多测试场景
5. 真人测试验证
