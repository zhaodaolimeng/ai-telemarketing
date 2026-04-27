# 智能催收对话系统 API

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
# 方式1: 使用Python直接运行
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 方式2: 如果main.py有__main__
python api/main.py
```

服务将在 `http://localhost:8000` 启动

### 访问API文档

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## API 接口说明

### 1. 健康检查

```http
GET /health
```

响应示例:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-04-26T14:00:00"
}
```

### 2. 开始对话

```http
POST /chat/start
Content-Type: application/json

{
  "chat_group": "H2",
  "customer_name": "Pak Budi"
}
```

响应示例:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_response": "Halo?",
  "current_state": "greeting",
  "commit_time": null,
  "conversation_length": 1,
  "is_finished": false,
  "is_successful": false,
  "audio_file": null,
  "latency_ms": 150.5
}
```

### 3. 对话轮次

```http
POST /chat/turn
Content-Type: application/json

{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "customer_input": "Halo, selamat pagi"
}
```

响应示例:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_response": "Halo, selamat pagi Pak Budi. Saya dari aplikasi Extra.",
  "current_state": "identity",
  "commit_time": null,
  "conversation_length": 3,
  "is_finished": false,
  "is_successful": false,
  "audio_file": null,
  "latency_ms": 200.3
}
```

### 4. 获取会话信息

```http
GET /chat/session/{session_id}
```

响应示例:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_group": "H2",
  "customer_name": "Pak Budi",
  "is_finished": false,
  "is_successful": false,
  "commit_time": null,
  "conversation_length": 5,
  "conversation_log": [
    {
      "role": "agent",
      "text": "Halo?",
      "timestamp": "2026-04-26T14:00:00"
    },
    {
      "role": "customer",
      "text": "Halo",
      "timestamp": "2026-04-26T14:00:01"
    }
  ],
  "start_time": "2026-04-26T14:00:00",
  "end_time": null,
  "created_at": "2026-04-26T14:00:00"
}
```

### 5. 关闭会话

```http
POST /chat/session/{session_id}/close
```

响应示例:
```json
{
  "message": "会话已关闭",
  "success": true
}
```

### 6. 运行测试场景

```http
POST /test/scenario
Content-Type: application/json

{
  "chat_group": "H2",
  "persona": "cooperative",
  "num_tests": 10
}
```

响应示例:
```json
{
  "total_tests": 10,
  "success_count": 9,
  "failed_count": 1,
  "success_rate": 90.0,
  "results": [
    {
      "session_id": "...",
      "success": true,
      "commit_time": "jam 5",
      "conversation_length": 13
    }
  ]
}
```

---

## 完整对话示例

### 使用curl

```bash
# 1. 开始对话
START_RESPONSE=$(curl -s -X POST http://localhost:8000/chat/start \
  -H "Content-Type: application/json" \
  -d '{"chat_group": "H2", "customer_name": "Pak Budi"}')

SESSION_ID=$(echo $START_RESPONSE | grep -o '"session_id": "[^"]*"' | cut -d'"' -f4)
echo "Session ID: $SESSION_ID"

# 2. 继续对话
curl -X POST http://localhost:8000/chat/turn \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"customer_input\": \"Halo\"}"

# 3. 获取会话信息
curl http://localhost:8000/chat/session/$SESSION_ID

# 4. 关闭会话
curl -X POST http://localhost:8000/chat/session/$SESSION_ID/close
```

### 使用Python

```python
import requests

BASE_URL = "http://localhost:8000"

# 开始对话
response = requests.post(f"{BASE_URL}/chat/start", json={
    "chat_group": "H2",
    "customer_name": "Pak Budi"
})
data = response.json()
session_id = data["session_id"]
print(f"Agent: {data['agent_response']}")

# 对话循环
while not data["is_finished"]:
    customer_input = input("Customer: ")

    response = requests.post(f"{BASE_URL}/chat/turn", json={
        "session_id": session_id,
        "customer_input": customer_input
    })
    data = response.json()
    print(f"Agent: {data['agent_response']}")

print("Conversation ended!")
print(f"Success: {data['is_successful']}")
print(f"Commit time: {data['commit_time']}")
```

---

## 催收环节说明

| 环节 | 说明 | 建议成功率目标 |
|-----|------|-------------|
| H2 | 早期逾期 | ≥85% |
| H1 | 中期逾期 | ≥75% |
| S0 | 晚期逾期 | ≥60% |

---

## 客户类型说明

| 类型 | 说明 | 特点 |
|-----|------|------|
| cooperative | 合作型 | 直接给出时间承诺 |
| busy | 忙碌型 | 先推脱，稍后给出 |
| negotiating | 协商型 | 要商量，给出选项 |
| forgetful | 健忘型 | 先忘，后想起来 |
| resistant | 抗拒型 | 拒绝，需多次追问 |
| excuse_master | 借口大师 | 各种借口，最后可能松口 |
| silent | 沉默型 | 不说话，最难处理 |

---

## 错误码说明

| HTTP码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 会话不存在 |
| 500 | 服务器内部错误 |
