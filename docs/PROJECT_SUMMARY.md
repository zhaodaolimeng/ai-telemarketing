# 智能催收对话系统 - 项目总结

## 已完成工作

### 1. 核心引擎 (src/core/)
- **对话机器人** (`src/core/chatbot.py`)
  - 11状态状态机
  - TTS集成
  - 变量替换系统
  - 时间检测
  - 成功/失败判定

- **客户模拟器** (`src/core/simulator.py`)
  - 7种客户类型：cooperative, busy, negotiating, resistant, silent, forgetful, excuse_master
  - 5级抗拒程度
  - 40+种拒绝借口
  - 基于真实对话数据分析

- **评测框架** (`src/core/evaluation.py`)
  - 多维度测试
  - 成功率统计
  - 自动生成报告

- **翻译引擎** (`src/core/translator.py`)
  - MarianMT本地翻译
  - 印尼文 ↔ 英文

### 2. 语音处理 (src/core/voice/)
- **VAD语音活动检测** (`src/core/voice/vad.py`)
  - 基于能量的检测器
  - 实时检测
  - 静音/语音状态跟踪

- **智能打断处理** (`src/core/voice/interruption.py`)
  - 短打断/长打断判断
  - 播放控制集成
  - 回调机制

- **TTS引擎抽象** (`src/core/voice/tts.py`)
  - Edge-TTS支持
  - Coqui-TTS支持
  - 多引擎切换

### 3. FastAPI 服务 (src/api/)
- **主API** (`src/api/main.py`)
  - 会话管理：开始、结束、获取信息
  - 对话交互：发送消息、接收响应
  - 测试场景：批量测试
  - 管理后台：统计、脚本管理

- **数据模型** (`src/api/schemas.py`)
  - 完整的Pydantic模型

- **数据库** (`src/api/database.py`)
  - SQLAlchemy ORM
  - 会话表、对话回合表
  - 脚本库表
  - 测试场景表
  - 指标日志表

### 4. 监控与管理
- **指标系统** (`src/core/metrics.py`)
  - 计数器
  - 计时器
  - 摘要统计
  - 系统指标API

### 5. 测试工具
- **API测试** (`src/tests/test_api.py`)
  - 完整API测试流程
  - 健康检查
  - 会话列表

- **批量生产测试** (`src/tests/run_small_scale_test.py`)
  - 1000通对话模拟
  - 并发测试
  - 详细报告

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 初始化数据库
```bash
python init_db.py
```

### 启动API服务
```bash
python start_demo.py
```

### 访问API文档
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 运行评测
```bash
python src/core/evaluation.py --num-tests 0
python src/tests/run_small_scale_test.py 50
```

## API 端点

### 对话API
- `GET /health` - 健康检查
- `POST /chat/start` - 开始对话
- `POST /chat/turn` - 对话回合
- `GET /chat/session/{session_id}` - 获取会话
- `POST /chat/session/{session_id}/close` - 关闭会话
- `GET /chat/sessions` - 会话列表
- `POST /test/scenario` - 运行测试场景

### 管理API
- `GET /admin/stats` - 系统统计
- `GET /admin/scripts` - 脚本列表
- `GET /admin/scripts/{id}` - 获取脚本
- `PUT /admin/scripts/{id}` - 更新脚本
- `GET /admin/metrics` - 系统指标
- `POST /admin/metrics/reset` - 重置指标

## 技术栈
- **后端框架**: FastAPI
- **数据库**: SQLite + SQLAlchemy
- **TTS**: Edge-TTS, Coqui-TTS
- **语音处理**: 自定义VAD
- **测试**: asyncio + 自定义框架

## 下一步
- 集成真实的ASR
- 完善Coqui-TTS印尼语模型
- 前端界面开发
- 真实电话线路集成
- A/B测试框架
