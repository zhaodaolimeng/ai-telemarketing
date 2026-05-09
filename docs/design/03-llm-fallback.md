# LLM Fallback 架构设计

## 概述

这是一个**混合式对话架构**：
- **主要路径**：高性能规则引擎处理标准场景
- **兜底路径**：当规则无法处理时，自动切换到LLM

## 架构图示

```
┌─────────────────────────────────────────────────────────────┐
│                    用户输入                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           Fallback 检测器 (FallbackDetector)                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 1. too_many_pushes - 连续多次追问失败                  │  │
│  │ 2. irrelevant_response - 客户回复不相关/转移话题         │  │
│  │ 3. complex_resistance - 客户提出多种抗拒理由             │  │
│  │ 4. too_silent - 客户沉默/回复过于简短                  │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────────┘
                 │
         ┌───────┴───────┐
         │               │
      需要Fallback?    不需要
         │               │
         ▼               ▼
   ┌───────────┐   ┌─────────────────┐
   │  LLM     │   │  规则引擎        │
   │处理      │   │ (Rule Engine)   │
   └─────┬─────┘   └────────┬────────┘
         │                  │
         └───────┬──────────┘
                 │
                 ▼
         ┌───────────────┐
         │  时间检测器   │
         └───────┬───────┘
                 │
         ┌───────┴───────┐
         │ 获取到时间?   │
         └────┬──────┬───┘
              │      │
            是      否
              │      │
              ▼      ▼
        ┌────────┐ ┌─────────────────┐
        │切回规则│ │ LLM轮数检查     │
        │完成确认│ │ max_llm_turns=3 │
        └────────┘ └──────┬──────────┘
                          │
                    未超限 ├───────────► 超限
                          │              │
                          ▼              ▼
                    继续LLM处理   切回规则继续
```

## 核心组件

### 1. FallbackDetector - Fallback检测器

**职责**：判断是否需要切换到LLM

**触发条件**（可扩展）：
| 条件 | 说明 | 严重度 |
|------|------|--------|
| too_many_pushes | 连续多次追问失败 | 高 |
| irrelevant_response | 客户回复不相关/转移话题 | 中 |
| complex_resistance | 客户提出多种抗拒理由 | 高 |
| too_silent | 客户沉默/回复过于简短 | 中 |

**扩展接口**：
```python
def custom_trigger(bot) -> bool:
    # 自定义判断逻辑
    return should_fallback

detector.triggers.append(FallbackTrigger(
    name="custom",
    condition=custom_trigger,
    description="自定义触发"
))
```

### 2. LLMInterface - LLM接口

**职责**：封装LLM调用，支持多种Provider

**当前实现**：
- Mock LLM：演示用（内置预设回复）
- 可扩展：OpenAI、Anthropic、本地模型

**接口设计**：
```python
async def generate(
    self,
    conversation_history: List[Dict[str, str]],
    system_prompt: str,
    context: Dict[str, Any]
) -> str
```

### 3. CollectionChatBotV4 - 主机器人

**状态机**：
```python
class ChatState(Enum):
    INIT = auto()
    GREETING = auto()
    IDENTIFY = auto()
    PURPOSE = auto()
    ASK_TIME = auto()
    PUSH_FOR_TIME = auto()
    COMMIT_TIME = auto()
    CONFIRM = auto()
    CLOSE = auto()
    FAILED = auto()
    LLM_FALLBACK = auto()  # ← 新增状态
```

## 关键设计决策

### 1. 何时切换回规则引擎？

**策略1**：检测到时间信息
```python
# LLM生成回复后，立即检测是否有时间信息
detected_time = self.time_detector.detect(llm_response)
if detected_time:
    # 获取到时间了，立即切回规则进行确认和关闭
    self.in_llm_fallback = False
    self.state = ChatState.COMMIT_TIME
```

**策略2**：LLM轮数限制
```python
self.max_llm_turns = 3  # 最多让LLM回复3轮
if self.llm_conversation_count >= self.max_llm_turns:
    self.in_llm_fallback = False  # 切回规则
```

**策略3**：手动触发
```python
# 外部可以随时干预
bot.in_llm_fallback = False
bot.state = ChatState.PUSH_FOR_TIME
```

### 2. 如何记录和分析？

**数据结构**：
```python
@dataclass
class ChatTurn:
    agent: str
    customer: Optional[str] = None
    is_llm_fallback: bool = False  # 标记这轮是否LLM生成
```

**统计信息**：
```python
{
    "total_turns": 8,
    "llm_turns": 2,
    "used_fallback": True,
    "objection_count": 1,
    "success": True,
    "commit_time": "jam 5"
}
```

## 使用示例

### 基本用法
```python
bot = CollectionChatBotV4("H2", "Pak Budi")

# 首次回复
agent_says = await bot.process()
print(f"AGENT: {agent_says}")

# 用户说话
while not bot.is_finished():
    customer_says = input("CUSTOMER: ")
    agent_says = await bot.process(customer_says)

    # 检查是否LLM生成
    if bot.conversation[-1].is_llm_fallback:
        print(f"AGENT (LLM): {agent_says}")
    else:
        print(f"AGENT: {agent_says}")
```

### 自定义Fallback条件
```python
def angry_customer(bot) -> bool:
    if not bot.conversation:
        return False
    last_customer = bot.conversation[-1].customer or ""
    angry_words = ["ngentot", "bangsat", "goblok"]
    return any(w in last_customer.lower() for w in angry_words)

bot.fallback_detector.triggers.append(FallbackTrigger(
    name="angry_customer",
    condition=angry_customer,
    description="客户情绪激动"
))
```

### 替换真实LLM
```python
class RealLLMInterface(LLMInterface):
    async def generate(self, conversation_history, system_prompt, context):
        # 调用真实的LLM API
        return await openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation_history
            ]
        )

bot.llm = RealLLMInterface()
```

## 优势

1. **成本控制**：LLM只在需要时调用
2. **性能优先**：标准场景走规则，响应快
3. **可观测**：清楚知道何时用了LLM
4. **可扩展**：易于添加新的触发条件
5. **安全**：规则引擎作为主体，LLM作为补充

## 下一步可能的扩展

- [ ] 从LLM回复自动提取时间和意图
- [ ] 不同场景使用不同的LLM提示词
- [ ] 基于LLM回复质量的评分和反馈
- [ ] 混合策略：规则生成+LLM润色
- [ ] LLM回复合规性检查

---

## LLM 能力扩展方向（2026-05-08）

当前 LLM 仅用作被动兜底（"救火队员"），以下是两个投入产出比最高的主动利用方向。

### 方向 1：LLM 批量生成话术变体

**现状**：话术库 ~45 类别，每类仅 3 条变体，对抗性场景下容易被用户"摸透"模式，重复话术降低体验。

**方案**：LLM 为每个话术类别批量生成 20-30 条变体，按 chat_group、用户画像、策略类型标注，人工审核后导入。

**Prompt 设计**（以 silence_level_2 为例）：

```
你是印尼催收话术专家。请为以下场景生成 8 条印尼语话术变体：

场景：沉默用户第2级回应 — 在用户持续沉默时，主动介绍账单信息
催收阶段：{H2 | H1 | S0}
用户画像：{新客首次借贷 | 老客有违约记录 | 中等收入已婚}
变量：{name}, {amount}, {days}

要求：
1. 每条 ≤ 25 词
2. 语气从温和到坚定各 2 条
3. 避免重复句式，用不同方式表达同一信息
4. 符合印尼口语习惯，不要翻译腔
5. 每条标注 tone（warm/neutral/firm）和适合的用户画像
```

**流水线**：

```
LLM 批量生成 → JSON 输出 → 人工审核（标注人员浏览+勾选）
        → 按 chat_group + 画像标签 分类入库
        → _get_script() 扩展为支持画像维度选优
```

**成本估算**：45 类别 × 3 阶段 × 3 变体 = 约 400 条话术，按 GPT-4o 定价约 $2-3。

### 方向 2：LLM 策略路由

**现状**：状态机对所有用户使用相同流程，仅通过 `chat_group` 区分话术模板。用户画像数据（39 个字段）未被用于策略决策。

**方案**：在对话开始时（或关键决策点），用 LLM 分析用户画像 + 对话上下文，输出策略参数，状态机按参数调整行为——**LLM 决定"怎么说服"，状态机保证"不出格"**。

**架构**：

```
用户画像 + 历史记录
        │
        ▼
┌─────────────────────┐
│  Strategy Router     │  对话开始时调用 1 次
│  (LLM 单次推理)       │  关键决策点可选再次调用
│                      │
│  输入:               │
│   - chat_group       │
│   - new_flag         │
│   - total_loan_cnt   │
│   - paidoff_loan_cnt │
│   - monthly_income   │
│   - promise_repay_date（是否曾违约）
│   - age, occupation  │
│                      │
│  输出 (JSON):         │
│   - primary_strategy │
│   - opening_tone     │
│   - push_intensity   │
│   - extension_priority│
│   - avoid_topics     │
│   - risk_level       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  状态机 (不变)        │  用策略参数调整行为
│                      │
│  根据 strategy_params: │
│  - opening_tone →   │
│    选对应语气的开场白  │
│  - push_intensity →  │
│    调整追问次数上限    │
│  - extension_priority │
│    → 是否优先推展期   │
│  - avoid_topics →    │
│    跳过特定话题       │
└─────────────────────┘
```

**策略参数定义**：

```python
@dataclass
class StrategyParams:
    primary_strategy: str       # "education" | "urgency" | "empathy" | "legal_warning"
    opening_tone: str           # "warm" | "neutral" | "firm"
    push_intensity: int         # 1-5，追问次数上限
    extension_priority: float   # 0-1，优先推展期的概率
    max_turns_before_close: int # 最大对话轮次
    avoid_topics: List[str]     # 需避免的话题 ["legal_threat", "family_pressure"]
    risk_level: str             # "low" | "medium" | "high"
    suggested_fallback: str     # 如果主策略失败，fallback 策略
```

**Prompt 设计**：

```
你是印尼信贷催收策略专家。根据以下用户画像，推荐最优催收策略。

用户信息：
- 催收阶段: {chat_group}
- 客户类型: {new_flag}
- 历史借贷次数: {total_loan_cnt}
- 已结清次数: {paidoff_loan_cnt}
- 当前逾期天数: {days}
- 欠款金额: Rp {amount}
- 月收入: Rp {monthly_income}
- 年龄: {age}
- 职业: {occupation}
- 曾承诺还款日期: {promise_repay_date or "无"}

请以 JSON 格式输出策略参数：
{
  "primary_strategy": "education|urgency|empathy|legal_warning",
  "opening_tone": "warm|neutral|firm",
  "push_intensity": 1-5,
  "extension_priority": 0.0-1.0,
  "max_turns_before_close": 6-15,
  "avoid_topics": [],
  "risk_level": "low|medium|high",
  "reasoning": "一句话解释策略选择理由"
}
```

**关键设计决策**：

| 决策 | 选择 | 理由 |
|------|------|------|
| LLM 调几次 | 对话开始调 1 次，关键决策点可选调 | 避免延迟累积，策略稳定可预期 |
| 状态机是否变 | 不变 | LLM 参数化行为，不替代流程控制 |
| 降级策略 | LLM 超时/不可用 → 默认策略参数 | 保证可用性 |
| 缓存 | 同一用户短期内复用策略 | 减少 API 调用 |

**与现有 Fallback 的关系**：

```
方向 2 策略路由（对话前） ≠ 现有 LLM Fallback（对话中）

现有 Fallback 仍然保留，两种 LLM 调用互补：
- 策略路由：决定"怎么开始"
- Fallback：处理"中间卡住了怎么办"
```

---

## 方向 2 深化：LLM 策略调度的第一性原理

### 核心命题

LLM 和规则引擎的根本差异不是"谁更聪明"，而是**信息处理边界**：

| | 规则引擎 | LLM |
|------|---------|-----|
| 处理方式 | 在预定义维度上做确定性映射 | 在开放维度上做概率性推理 |
| 优势 | 快、稳、可解释 | 可处理模糊、矛盾、多义输入 |
| 劣势 | 无法处理未预见的输入组合 | 慢、贵、不稳定 |

策略调度的问题本质：**输入的维度远超规则能覆盖的范围**。39 个用户画像字段 × 7 种客户类型 × 5 级抗拒 × 3 个催收阶段 = 4095+ 种组合，每种写一条规则不可能。所以当前系统退化为只用 `chat_group` 一个维度做策略选择——放弃了 99% 的输入信息。

**LLM 在策略层的价值不是"替换规则"，而是压缩高维信息到低维策略参数，让规则引擎在低维空间里继续做它擅长的事。**

---

### 策略的原子维度

抛开系统实现，从催收业务本身看，一个催收策略由以下独立维度构成：

| 策略维度 | 含义 | 取值范围 |
|---------|------|---------|
| `primary_approach` | 说服主线 | education / urgency / empathy / legal_warning |
| `tone` | 对话的情感色彩 | warm / neutral / firm |
| `push_intensity` | 对承诺时间的push力度 | 1-5（轻问→追问→施压→最后通牒） |
| `extension_priority` | 是否主动推展期方案 | 0.0-1.0（0=不推, 1=首推） |
| `max_turns` | 在什么时机结束对话 | 6-15 轮 |
| `avoid_topics` | 哪些话题不能触碰 | legal_threat / family_pressure / competitor_compare |
| `fallback_approach` | 主策略失败后的备选 | education / extension / urgency / legal_warning |

这 7 个维度构成了策略空间的全部自由度。不同用户画像 = 这 7 个参数的不同取值组合。

---

### 架构：LLM 作为"降维引擎"

```
39维用户画像 ──→ [LLM 降维] ──→ 7维策略参数 ──→ [规则引擎执行]
     │                    │                    │
     │ 结构化+非结构化     │ 一次推理             │ 确定性状态机
     │ 矛盾信息可以共存    │ 概率性判断            │ 可预测、可审计
```

每层做自己擅长的事：
- **LLM**：从高维、含噪、可能有矛盾的输入中提取模式，输出结构化的策略参数
- **规则引擎**：在低维、确定性的策略参数约束下稳定执行，不越界

---

### 三个调度时机

**T1：对话前调度（信息量最大，投入产出比最高）**

- 输入：完整用户画像（39字段）+ 历史通话记录 + 当前催收阶段
- 输出：初始策略参数（7维度）
- 时机：拨号前调用一次
- 降级：LLM 不可用 → 按 `chat_group` 使用默认策略参数（即当前行为）

**T2：关键节点重调度（信息增量最大）**

- 输入：对话前的画像 + 本轮对话摘要 + 用户最新意图/情绪
- 输出：调整后的策略参数（增量修改，非全量重算）
- 触发条件（规则化）：`push_count >= 3 AND no_time_commitment` / `new_objection_type_detected` / `user_emotion_shift`
- 降级：LLM 不可用 → 保持当前策略参数继续执行

**T3：跨通话演化调度（趋势信息最大）**

- 输入：前 N 次通话摘要 + 每次结果 + `repay_type` 真值
- 输出：下次通话的策略调整建议
- 时机：通话之间的离线分析
- 价值：LLM 从多通通话的轨迹中识别模式（"第一次接受教育、第二次开始找借口、第三次可能直接挂断"），预判演化方向

---

### 策略-执行接口

关键原则：**策略参数是约束，不是指令**。LLM 不决定"先做什么再做什么"，只决定"什么边界内执行"。

```python
# LLM输出 → 规则引擎读取

strategy = {
    "primary_approach": "empathy",      # 共情主线
    "tone": "warm",                     # 温和语气
    "push_intensity": 2,                # 追问力度偏轻
    "extension_priority": 0.8,          # 优先推展期
    "max_turns": 10,                    # 最多10轮
    "avoid": ["legal_threat"],          # 不说法律后果
    "fallback_approach": "education"    # 共情不行就转教育
}

# 规则引擎的行为调整：
# - push_intensity=2 → PUSH_FOR_TIME最多追问2轮就转入展期
# - extension_priority=0.8 → ASK_TIME后优先跳CONFIRM_EXTENSION而非PUSH_FOR_TIME
# - tone=warm → _get_script() 优先选对应语气标签的话术
# - max_turns=10 → 第10轮仍未拿到承诺 → CLOSE
# - avoid=["legal_threat"] → 跳过法律后果相关话术类别
```

**反模式（应避免）**：

```python
# LLM决定执行步骤 —— 这是侵入执行层
strategy = {
    "steps": [
        "先确认身份",
        "然后告知金额",
        "再问还款时间",
        "如果拒绝就推展期"
    ]
}
# 状态机已经有这些流转逻辑，LLM不应重复
```

---

### 失败模式与降级链

| 失败模式 | 降级方案 | 影响 |
|---------|---------|------|
| LLM 超时（>2s） | 使用该用户上次缓存的策略参数 | 无感知 |
| LLM 返回格式错误 | 使用该 `chat_group` 的默认策略参数 | 回退到当前行为 |
| LLM 不可用（quota/网络） | 回退到完全规则模式 | 回退到当前行为 |
| LLM 策略与合规冲突 | 合规优先，自动修正冲突参数 | 策略可能偏保守 |

核心保证：**最差情况 = 当前系统行为**。LLM 是在基线之上做个性化微调，不是替代。

---

### Gold 样本推演

以下用 4 个代表性 gold 样本，推演策略路由是否逻辑闭环。

#### Case 1: H2 silent — high resistance（当前：失败 ❌）

**画像推理**（基于 silent 客户的行为特征）：
```
new_flag=0（新客，不了解流程）, age=22, total_loan_cnt=1,
monthly_income=3M, approved_amount=1M, occupation=1（雇员）,
promise_repay_date=null, paidoff_loan_cnt=0
```

**LLM 策略推理**：
> 新客首次借贷，年轻，收入偏低。沉默可能是因为不了解催收流程、不确定如何回应，而非恶意逃避。应以教育为主，降低回应门槛，避免施压导致进一步退缩。

**策略参数**：
```json
{
  "primary_approach": "education",
  "tone": "warm",
  "push_intensity": 1,
  "extension_priority": 0.6,
  "max_turns": 8,
  "avoid_topics": ["legal_threat", "family_pressure"],
  "fallback_approach": "education"
}
```

**规则引擎行为变化**：

| 状态 | 原行为 | 策略路由后 |
|------|--------|-----------|
| IDENTITY_VERIFY | 标准身份确认 | tone=warm，选亲和力高的话术 |
| PURPOSE | 告知账单信息 | education 主线 + 简短解释逾期含义 |
| ASK_TIME | 开放提问"什么时候能付" | push_intensity=1 → 改为是非题"您收到我们的短信提醒了吗？"降低回应门槛 |
| SILENCE_L1 | 确认通话质量 | 不变，但更快进入主动介绍（max_turns=8 约束） |
| 展期 | 仅在用户询问时介绍 | extension_priority=0.6 → 主动提"如果您需要更长时间..." |

**推演结果**：silent 用户需要的是低门槛回应入口。改为是非题 + 主动介绍信息后，即使用户只是简短回应"iya"，也能推进到展期或CLOSE。**预期改善**。

---

#### Case 2: S0 excuse_master — very_high resistance（当前：失败 ❌）

**画像推理**（基于 excuse_master 的行为特征）：
```
new_flag=2（老客）, age=38, total_loan_cnt=8, paidoff_loan_cnt=5,
monthly_income=8M, approved_amount=3M, dpd=90+,
promise_repay_date=2026-04-15（曾承诺未兑现）, occupation=1（雇员）
```

**LLM 策略推理**：
> 老客多次借贷有还款历史，但当前已逾期 90+ 天且曾承诺未兑现。收入能力足够覆盖欠款却找借口拖延，属于策略性回避。应以坚定态度施压，限定轮次，不纠缠借口细节，快速引导至后果告知。

**策略参数**：
```json
{
  "primary_approach": "legal_warning",
  "tone": "firm",
  "push_intensity": 4,
  "extension_priority": 0.3,
  "max_turns": 8,
  "avoid_topics": ["competitor_compare"],
  "fallback_approach": "legal_warning"
}
```

**规则引擎行为变化**：

| 状态 | 原行为 | 策略路由后 |
|------|--------|-----------|
| IDENTITY_VERIFY | 标准身份确认 | tone=firm，语气坚定不寒暄 |
| PURPOSE | 告知账单信息 | 追加提及"上次承诺 4/15 未兑现" |
| 遇到借口 | 逐条反驳→被链式借口拖入 unknown | push_intensity=4 → 反驳2轮后不继续纠缠，直接进入后果告知 |
| 展期 | 询问是否需要 | extension_priority=0.3 → 不主动提展期，用户要求才回应 |
| 第 8 轮 | - | max_turns=8 → 直接进入 close + 告知后果 |

**推演结果**：excuse_master 的失败根因是被借口链拖入 unknown 循环。策略路由通过 push_intensity=4 + max_turns=8 限制了纠缠深度，并且利用"曾承诺未兑现"信息增加了施压点。**预期改善**。

---

#### Case 3: H2 cooperative — very_low resistance（当前：通过 ✅）

**画像推理**：
```
new_flag=2（老客）, age=35, total_loan_cnt=5, paidoff_loan_cnt=5,
monthly_income=10M, approved_amount=2M, dpd=3,
promise_repay_date=null, 无历史违约
```

**LLM 策略推理**：
> 老客有完美还款记录，逾期仅 3 天，极可能是遗忘而非故意。温和提醒即可，不需要任何施压。

**策略参数**：
```json
{
  "primary_approach": "education",
  "tone": "warm",
  "push_intensity": 1,
  "extension_priority": 0.0,
  "max_turns": 6,
  "avoid_topics": ["legal_threat", "family_pressure", "competitor_compare"],
  "fallback_approach": "education"
}
```

**规则引擎行为变化**：几乎不变。合作型客户本身不需要复杂策略，LLM 的策略参数与当前 H2 默认行为高度一致。**预期保持通过**，且对话更简洁（max_turns=6 提前收束）。

---

#### Case 4: H2 resistant — medium resistance（当前：失败 ❌）

**画像推理**（基于 resistant 客户的行为特征）：
```
new_flag=1（第二笔借贷）, age=28, total_loan_cnt=2, paidoff_loan_cnt=1,
monthly_income=5M, approved_amount=1.5M, dpd=5,
promise_repay_date=null, occupation=2（自由职业）
```

**LLM 策略推理**：
> 第二次借贷，有一次还款记录。自由职业者，收入可能不稳定。推托可能是因为现金流暂时紧张。应共情引导 + 主动推展期，而非直接施压。

**策略参数**：
```json
{
  "primary_approach": "empathy",
  "tone": "neutral",
  "push_intensity": 2,
  "extension_priority": 0.8,
  "max_turns": 10,
  "avoid_topics": ["legal_threat"],
  "fallback_approach": "urgency"
}
```

**规则引擎行为变化**：

| 状态 | 原行为 | 策略路由后 |
|------|--------|-----------|
| IDENTITY_VERIFY | 标准确认 | tone=neutral，不过分热情 |
| PURPOSE | 告知账单 | 语气中性，不强调严重性 |
| ASK_TIME | 问还款时间 | 如果用户推托，extension_priority=0.8 → 主动提"有展期选项可以减轻压力" |
| PUSH_FOR_TIME | 追问具体时间 | push_intensity=2 → 追问2轮无果就转展期，不持续施压 |
| 展期同意后 | 确认展期 | primary_approach=empathy → 确认语气温暖"我们理解您的情况" |

**推演结果**：resistant 客户的抗拒在 H2 阶段通常是临时性的（资金周转、暂时不方便），共情+展期方案比直接施压更有效。策略路由通过识别"自由职业+第二笔借贷"选择了 empathy 路线而非 urgency。**预期改善**。

---

### 推演总结

| Case | 当前结果 | 策略路由后预期 | 关键变化 |
|------|:---:|:---:|---------|
| H2 silent | ❌ | ✅ 改善 | 降低回应门槛（是非题），温暖教育主线 |
| S0 excuse_master | ❌ | ✅ 改善 | 限制借口纠缠，利用违约历史施压 |
| H2 cooperative | ✅ | ✅ 保持 | 策略与当前行为一致，对话更简洁 |
| H2 resistant | ❌ | ✅ 改善 | 识别临时性困难，共情+推展期替代施压 |

**闭环验证**：4 个 case 的推演中，策略路由的逻辑链条完整——画像→LLM推理→策略参数→规则引擎行为变化→预期结果。每一步都有清晰的因果关系。LLM 给出的策略参数在 7 个维度上有明确的值和理由，规则引擎可以无歧义地执行。
