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
