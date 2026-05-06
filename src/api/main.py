from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import sys
from pathlib import Path
from datetime import datetime
import uuid
from typing import Optional, Dict, List
import asyncio
import json

sys.path.append(str(Path(__file__).parent.parent))

from api.schemas import (
    ChatTurnRequest,
    ChatTurnResponse,
    ChatSessionResponse,
    ChatLogEntry,
    ChatState,
    ChatGroup,
    CustomerPersona,
    TestScenarioRequest,
    TestResultResponse,
    MessageResponse,
    HealthResponse,
    StatsResponse,
    ScriptResponse,
    ScriptUpdateRequest,
    TranslateRequest,
    TranslateResponse,
    SimulateCustomerRequest,
    SimulateCustomerResponse,
)
from api.database import (
    get_db,
    init_db,
    ChatSession as DBChatSession,
    ChatTurn as DBChatTurn,
)
from core.chatbot import (
    CollectionChatBot,
    get_stage_from_state,
)
from core.simulator import (
    RealCustomerSimulatorV2,
)
from core.metrics import (
    collector,
    ConversationMetrics,
    PerformanceMetrics,
    get_system_metrics,
)

# 翻译服务
from core.translator import translate_text


def convert_bot_state_to_schema(bot_state):
    """将chatbot的状态转换为schema兼容的状态"""
    state_map = {
        'INIT': 'init',
        'GREETING': 'greeting',
        'IDENTITY_VERIFY': 'identify',
        'PURPOSE': 'purpose',
        'ASK_TIME': 'ask_time',
        'PUSH_FOR_TIME': 'push_for_time',
        'COMMIT_TIME': 'commit_time',
        'CONFIRM_EXTENSION': 'negotiate',
        'HANDLE_OBJECTION': 'negotiate',
        'HANDLE_BUSY': 'close',
        'HANDLE_WRONG_NUMBER': 'close',
        'CLOSE': 'close',
        'FAILED': 'failed'
    }

    # 获取状态名称
    if hasattr(bot_state, 'name'):
        state_name = bot_state.name
    else:
        state_name = str(bot_state).split('.')[-1]

    return state_map.get(state_name, 'init')


app = FastAPI(
    title="智能催收对话系统 API",
    description="基于状态机的印尼语催收对话系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
static_path = Path(__file__).parent.parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

active_sessions: Dict[str, CollectionChatBot] = {}
simulator = RealCustomerSimulatorV2()


@app.on_event("startup")
async def startup_event():
    init_db()
    print("Database initialized!")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
    )


def save_session_to_db(db: Session, bot: CollectionChatBot, chat_group: str):
    db_session = DBChatSession(
        session_id=bot.session_id,
        chat_group=chat_group,
        customer_name=bot.customer_name,
        is_finished=bot.is_finished(),
        is_successful=bot.is_successful(),
        commit_time=bot.commit_time,
        conversation_length=len(bot.conversation),
    )
    db.add(db_session)
    db.flush()

    for turn_num, turn in enumerate(bot.conversation, 1):
        db_turn = DBChatTurn(
            session_id=db_session.id,
            turn_number=turn_num,
            agent_text=turn.agent,
            customer_text=turn.customer,
            state=get_stage_from_state(bot.state),
            timestamp=turn.timestamp,
        )
        db.add(db_turn)

    db.commit()
    db.refresh(db_session)
    return db_session


@app.post("/chat/start", response_model=ChatTurnResponse)
async def start_chat(request: ChatTurnRequest, db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())

    bot = CollectionChatBot(
        chat_group=request.chat_group.value,
        customer_name=request.customer_name,
    )
    bot.session_id = session_id

    active_sessions[session_id] = bot

    start_time = datetime.now()
    agent_response, audio_file = await bot.process(use_tts=False)
    latency_ms = (datetime.now() - start_time).total_seconds() * 1000

    save_session_to_db(db, bot, request.chat_group.value)

    return ChatTurnResponse(
        session_id=session_id,
        agent_response=agent_response,
        current_state=ChatState(convert_bot_state_to_schema(bot.state)),
        commit_time=bot.commit_time,
        conversation_length=len(bot.conversation),
        is_finished=bot.is_finished(),
        is_successful=bot.is_successful(),
        audio_file=audio_file,
        latency_ms=round(latency_ms, 2),
    )


@app.post("/chat/turn", response_model=ChatTurnResponse)
async def chat_turn(request: ChatTurnRequest, db: Session = Depends(get_db)):
    session_id = request.session_id
    if not session_id or session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="会话不存在")

    bot = active_sessions[session_id]

    if bot.is_finished():
        raise HTTPException(status_code=400, detail="会话已结束")

    start_time = datetime.now()
    agent_response, audio_file = await bot.process(
        customer_input=request.customer_input,
        use_tts=False,
    )
    latency_ms = (datetime.now() - start_time).total_seconds() * 1000

    db_session = db.query(DBChatSession).filter(
        DBChatSession.session_id == session_id
    ).first()

    if db_session:
        db_session.is_finished = bot.is_finished()
        db_session.is_successful = bot.is_successful()
        db_session.commit_time = bot.commit_time
        db_session.conversation_length = len(bot.conversation)

        if bot.is_finished():
            db_session.end_time = datetime.now().isoformat()

        db.commit()

    return ChatTurnResponse(
        session_id=session_id,
        agent_response=agent_response,
        current_state=ChatState(convert_bot_state_to_schema(bot.state)),
        commit_time=bot.commit_time,
        conversation_length=len(bot.conversation),
        is_finished=bot.is_finished(),
        is_successful=bot.is_successful(),
        audio_file=audio_file,
        latency_ms=round(latency_ms, 2),
    )


@app.get("/chat/session/{session_id}", response_model=ChatSessionResponse)
async def get_session(session_id: str, db: Session = Depends(get_db)):
    if session_id in active_sessions:
        bot = active_sessions[session_id]
        log = bot.get_log()

        conversation_log = []
        for turn in bot.conversation:
            if turn.agent:
                conversation_log.append(ChatLogEntry(
                    role="agent",
                    text=turn.agent,
                    timestamp=turn.timestamp,
                ))
            if turn.customer:
                conversation_log.append(ChatLogEntry(
                    role="customer",
                    text=turn.customer,
                    timestamp=turn.timestamp,
                ))

        return ChatSessionResponse(
            session_id=log.session_id,
            chat_group=ChatGroup(log.chat_group),
            customer_name=bot.customer_name,
            is_finished=bot.is_finished(),
            is_successful=bot.is_successful(),
            commit_time=log.commit_time,
            conversation_length=len(conversation_log),
            conversation_log=conversation_log,
            start_time=log.start_time,
            end_time=log.end_time,
            created_at=log.start_time,
        )

    db_session = db.query(DBChatSession).filter(DBChatSession.session_id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db_turns = db.query(DBChatTurn).filter(DBChatTurn.session_id == db_session.id).order_by(DBChatTurn.turn_number).all()

    conversation_log = []
    for turn in db_turns:
        if turn.agent_text:
            conversation_log.append(ChatLogEntry(
                role="agent",
                text=turn.agent_text,
                timestamp=turn.timestamp,
            ))
        if turn.customer_text:
            conversation_log.append(ChatLogEntry(
                role="customer",
                text=turn.customer_text,
                timestamp=turn.timestamp,
            ))

    return ChatSessionResponse(
        session_id=db_session.session_id,
        chat_group=ChatGroup(db_session.chat_group),
        customer_name=db_session.customer_name,
        is_finished=db_session.is_finished,
        is_successful=db_session.is_successful,
        commit_time=db_session.commit_time,
        conversation_length=db_session.conversation_length,
        conversation_log=conversation_log,
        start_time=db_session.start_time,
        end_time=db_session.end_time,
        created_at=db_session.created_at,
    )


@app.post("/chat/session/{session_id}/close", response_model=MessageResponse)
async def close_session(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(DBChatSession).filter(DBChatSession.session_id == session_id).first()

    if session_id in active_sessions:
        bot = active_sessions[session_id]
        if db_session:
            db_session.is_finished = bot.is_finished()
            db_session.is_successful = bot.is_successful()
            db_session.end_time = datetime.now().isoformat()
            db.commit()
        del active_sessions[session_id]
        return MessageResponse(message="会话已关闭")

    if db_session:
        db_session.is_finished = True
        db_session.end_time = datetime.now().isoformat()
        db.commit()
        return MessageResponse(message="会话已关闭")

    raise HTTPException(status_code=404, detail="会话不存在")


@app.get("/chat/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(skip: int = 0, limit: int = 100, chat_group: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DBChatSession)
    if chat_group:
        query = query.filter(DBChatSession.chat_group == chat_group)
    db_sessions = query.order_by(DBChatSession.created_at.desc()).offset(skip).limit(limit).all()

    results = []
    for db_session in db_sessions:
        db_turns = db.query(DBChatTurn).filter(DBChatTurn.session_id == db_session.id).order_by(DBChatTurn.turn_number).all()

        conversation_log = []
        for turn in db_turns:
            if turn.agent_text:
                conversation_log.append(ChatLogEntry(
                    role="agent",
                    text=turn.agent_text,
                    timestamp=turn.timestamp,
                ))
            if turn.customer_text:
                conversation_log.append(ChatLogEntry(
                    role="customer",
                    text=turn.customer_text,
                    timestamp=turn.timestamp,
                ))

        results.append(ChatSessionResponse(
            session_id=db_session.session_id,
            chat_group=ChatGroup(db_session.chat_group),
            customer_name=db_session.customer_name,
            is_finished=db_session.is_finished,
            is_successful=db_session.is_successful,
            commit_time=db_session.commit_time,
            conversation_length=db_session.conversation_length,
            conversation_log=conversation_log,
            start_time=db_session.start_time,
            end_time=db_session.end_time,
            created_at=db_session.created_at,
        ))

    return results


@app.post("/test/scenario", response_model=TestResultResponse)
async def run_test_scenario(request: TestScenarioRequest):
    results = []
    success_count = 0

    for i in range(request.num_tests):
        session_id = str(uuid.uuid4())
        bot = CollectionChatBot(
            chat_group=request.chat_group.value,
        )
        bot.session_id = session_id

        agent_text, _ = await bot.process(use_tts=False)

        push_count = 0
        max_turns = 20

        for turn in range(max_turns):
            if bot.is_finished():
                break

            if "jam berapa" in agent_text.lower() or "kapan" in agent_text.lower():
                push_count += 1

            customer_text = simulator.generate_response(
                stage=get_stage_from_state(bot.state),
                chat_group=request.chat_group.value,
                persona=request.persona.value,
                push_count=push_count,
            )

            agent_text, _ = await bot.process(customer_text, use_tts=False)

        is_success = bot.is_successful()

        if is_success:
            success_count += 1

        results.append({
            "session_id": session_id,
            "success": is_success,
            "commit_time": bot.commit_time,
            "conversation_length": len(bot.conversation),
        })

    success_rate = success_count / request.num_tests if request.num_tests > 0 else 0

    return TestResultResponse(
        total_tests=request.num_tests,
        success_count=success_count,
        failed_count=request.num_tests - success_count,
        success_rate=round(success_rate * 100, 2),
        results=results,
    )


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    audio_path = Path("data/tts_output") / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频文件不存在")
    return FileResponse(audio_path, media_type="audio/mpeg")


@app.get("/")
async def root():
    index_path = Path(__file__).parent.parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return MessageResponse(message="欢迎使用智能催收对话系统 API")


# ============ 管理API ============

@app.get("/admin/stats", response_model=StatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """获取系统统计数据"""
    from sqlalchemy import func

    # 会话统计
    total_sessions = db.query(func.count(DBChatSession.id)).scalar() or 0
    successful_sessions = db.query(func.count(DBChatSession.id)).filter(
        DBChatSession.is_successful == True
    ).scalar() or 0
    success_rate = (successful_sessions / total_sessions * 100) if total_sessions > 0 else 0.0

    # 回合统计
    total_turns = db.query(func.count(DBChatTurn.id)).scalar() or 0
    avg_turns = (total_turns / total_sessions) if total_sessions > 0 else 0.0

    # 按组别统计
    chat_group_stats = {}
    groups = db.query(DBChatSession.chat_group, func.count(DBChatSession.id)).group_by(
        DBChatSession.chat_group
    ).all()

    for group, count in groups:
        successful = db.query(func.count(DBChatSession.id)).filter(
            DBChatSession.chat_group == group,
            DBChatSession.is_successful == True
        ).scalar() or 0
        chat_group_stats[group] = {
            "total": count,
            "successful": successful,
            "success_rate": round(successful / count * 100, 1) if count > 0 else 0.0
        }

    return StatsResponse(
        total_sessions=total_sessions,
        successful_sessions=successful_sessions,
        success_rate=round(success_rate, 1),
        total_turns=total_turns,
        avg_turns_per_session=round(avg_turns, 1),
        active_sessions=len(active_sessions),
        chat_group_stats=chat_group_stats
    )


@app.get("/admin/scripts", response_model=List[ScriptResponse])
async def list_scripts(
    chat_group: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """列出脚本库"""
    from api.database import ScriptLibrary

    query = db.query(ScriptLibrary)

    if chat_group:
        query = query.filter(ScriptLibrary.chat_group == chat_group)
    if category:
        query = query.filter(ScriptLibrary.category == category)

    scripts = query.order_by(ScriptLibrary.category, ScriptLibrary.script_key).all()

    return [
        ScriptResponse(
            id=s.id,
            category=s.category,
            chat_group=s.chat_group,
            script_key=s.script_key,
            script_text=s.script_text,
            variables=s.variables,
            is_active=s.is_active
        )
        for s in scripts
    ]


@app.get("/admin/scripts/{script_id}", response_model=ScriptResponse)
async def get_script(script_id: int, db: Session = Depends(get_db)):
    """获取单个脚本"""
    from api.database import ScriptLibrary

    script = db.query(ScriptLibrary).filter(ScriptLibrary.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    return ScriptResponse(
        id=script.id,
        category=script.category,
        chat_group=script.chat_group,
        script_key=script.script_key,
        script_text=script.script_text,
        variables=script.variables,
        is_active=script.is_active
    )


@app.put("/admin/scripts/{script_id}", response_model=ScriptResponse)
async def update_script(
    script_id: int,
    request: ScriptUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新脚本"""
    from api.database import ScriptLibrary

    script = db.query(ScriptLibrary).filter(ScriptLibrary.id == script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail="脚本不存在")

    if request.script_text is not None:
        script.script_text = request.script_text
    if request.is_active is not None:
        script.is_active = request.is_active
    if request.variables is not None:
        script.variables = request.variables

    script.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(script)

    return ScriptResponse(
        id=script.id,
        category=script.category,
        chat_group=script.chat_group,
        script_key=script.script_key,
        script_text=script.script_text,
        variables=script.variables,
        is_active=script.is_active
    )


@app.get("/admin/metrics")
async def get_metrics():
    """获取系统指标"""
    return get_system_metrics()


@app.post("/admin/metrics/reset")
async def reset_metrics():
    """重置指标"""
    collector.reset()
    return MessageResponse(message="指标已重置")


# ============ 翻译API ============

@app.post("/api/translate", response_model=TranslateResponse)
async def translate_endpoint(request: TranslateRequest):
    """翻译文本 - 印尼文<->英文"""
    text = request.text.strip()
    source = request.source
    target = request.target

    try:
        result = translate_text(text, source, target)
        return TranslateResponse(
            original_text=result.original_text,
            translated_text=result.translated_text,
            source=result.source_lang,
            target=result.target_lang,
            success=result.success
        )
    except Exception as e:
        print(f"Translation endpoint error: {e}")
        return TranslateResponse(
            original_text=text,
            translated_text=text,
            source=source,
            target=target,
            success=False
        )


# ============ 仿真客户API ============

@app.post("/api/simulate-customer", response_model=SimulateCustomerResponse)
async def simulate_customer(request: SimulateCustomerRequest, db: Session = Depends(get_db)):
    """仿真客户回复"""
    try:
        session_id = request.session_id
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="会话不存在")

        bot = active_sessions[session_id]

        # 获取当前状态对应的阶段
        current_stage = get_stage_from_state(bot.state)

        # 使用模拟器生成回复
        persona = request.persona.value

        # 计算push_count（简单计算）
        push_count = 0
        for turn in bot.conversation:
            if turn.customer:
                push_count += 1

        customer_response = simulator.generate_response(
            stage=current_stage,
            chat_group=bot.chat_group,
            persona=persona,
            push_count=push_count,
            resistance_level=request.resistance_level
        )

        return SimulateCustomerResponse(
            customer_response=customer_response,
            persona=persona,
            resistance_level=request.resistance_level,
            success=True
        )

    except Exception as e:
        return SimulateCustomerResponse(
            customer_response="",
            persona=request.persona.value,
            resistance_level=request.resistance_level,
            success=False
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
