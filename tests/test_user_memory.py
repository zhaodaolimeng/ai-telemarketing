"""P15-D01: 跨会话用户记忆单元测试"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.user_memory import UserMemory, UserMemoryStore


# ── UserMemory 属性测试 ──────────────────────────────────────────────

def test_has_previous_sessions():
    assert UserMemory(phone="0812", total_sessions=0).has_previous_sessions is False
    assert UserMemory(phone="0812", total_sessions=3).has_previous_sessions is True


def test_previously_promised_but_failed_true():
    mem = UserMemory(
        phone="0812",
        last_session_result="failed",
        last_commit_time="kemarin jam 3",
    )
    assert mem.previously_promised_but_failed is True


def test_previously_promised_but_failed_success():
    mem = UserMemory(
        phone="0812",
        last_session_result="success",
        last_commit_time="kemarin jam 3",
    )
    assert mem.previously_promised_but_failed is False


def test_previously_promised_but_failed_no_commit_time():
    mem = UserMemory(
        phone="0812",
        last_session_result="failed",
        last_commit_time=None,
    )
    assert mem.previously_promised_but_failed is False


def test_previously_promised_but_failed_abandoned():
    mem = UserMemory(
        phone="0812",
        last_session_result="abandoned",
        last_commit_time="jam 5",
    )
    assert mem.previously_promised_but_failed is False


def test_is_low_trust_true():
    mem = UserMemory(phone="0812", total_sessions=4, successful_sessions=1)
    assert mem.is_low_trust is True


def test_is_low_trust_false_insufficient_sessions():
    mem = UserMemory(phone="0812", total_sessions=1, successful_sessions=0)
    assert mem.is_low_trust is False


def test_is_low_trust_false_high_rate():
    mem = UserMemory(phone="0812", total_sessions=5, successful_sessions=4)
    assert mem.is_low_trust is False


def test_promise_fulfillment_rate():
    assert UserMemory(phone="0812", total_sessions=4, successful_sessions=3).promise_fulfillment_rate == 0.75
    assert UserMemory(phone="0812", total_sessions=0).promise_fulfillment_rate == 0.0


# ── UserMemoryStore 测试（内存 SQLite）───────────────────────────────

@pytest.fixture
def db_session():
    """创建内存 SQLite 测试数据库"""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from api.database import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_store_load_empty(db_session):
    store = UserMemoryStore(db_session)
    assert store.load("0812-not-exist") is None


def test_store_load_with_history(db_session):
    from api.database import ChatSession as DBChatSession

    s1 = DBChatSession(
        session_id="s1", customer_phone="08123456789",
        chat_group="H2", is_finished=True, is_successful=True,
        commit_time="15:00", conversation_length=5,
    )
    s2 = DBChatSession(
        session_id="s2", customer_phone="08123456789",
        chat_group="S0", is_finished=True, is_successful=False,
        commit_time="16:00", conversation_length=8,
    )
    s3 = DBChatSession(
        session_id="s3", customer_phone="08123456789",
        chat_group="H1", is_finished=False, is_successful=False,
        commit_time=None, conversation_length=3,
    )
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    store = UserMemoryStore(db_session)
    mem = store.load("08123456789")

    assert mem is not None
    assert mem.phone == "08123456789"
    assert mem.total_sessions == 3
    assert mem.successful_sessions == 1
    assert mem.failed_sessions == 1  # s2 is finished+failed, s3 is unfinished
    assert mem.promise_fulfillment_rate == pytest.approx(1 / 3)
    assert mem.last_session_result == "abandoned"  # s3 is newest, unfinished
    assert mem.last_commit_time is None  # s3 has no commit_time
    assert mem.avg_turns_per_session == pytest.approx((5 + 8 + 3) / 3)


def test_store_load_single_session(db_session):
    from api.database import ChatSession as DBChatSession

    s = DBChatSession(
        session_id="s1", customer_phone="0812-single",
        chat_group="H2", is_finished=True, is_successful=True,
        commit_time="14:00", conversation_length=4,
    )
    db_session.add(s)
    db_session.commit()

    store = UserMemoryStore(db_session)
    mem = store.load("0812-single")

    assert mem is not None
    assert mem.total_sessions == 1
    assert mem.promise_fulfillment_rate == 1.0
    assert mem.last_session_result == "success"
    assert mem.last_commit_time == "14:00"


def test_store_different_phones_isolated(db_session):
    from api.database import ChatSession as DBChatSession

    db_session.add(DBChatSession(
        session_id="sa", customer_phone="0812-A",
        chat_group="H2", is_finished=True, is_successful=True,
    ))
    db_session.add(DBChatSession(
        session_id="sb", customer_phone="0812-B",
        chat_group="S0", is_finished=True, is_successful=False,
    ))
    db_session.commit()

    store = UserMemoryStore(db_session)
    assert store.load("0812-A").total_sessions == 1
    assert store.load("0812-B").total_sessions == 1
    assert store.load("0812-C") is None


# ── CollectionChatBot 集成测试 ────────────────────────────────────────

def test_bot_with_user_memory_new_customer():
    """首次来电：_is_returning_customer=False"""
    from core.chatbot import CollectionChatBot

    bot = CollectionChatBot(chat_group="H2")
    assert bot._is_returning_customer is False
    assert bot.customer_phone is None
    assert bot.user_memory is None


def test_bot_with_user_memory_returning_customer():
    """回头客：_is_returning_customer=True，策略升级"""
    from core.chatbot import CollectionChatBot

    mem = UserMemory(
        phone="0812", total_sessions=3, successful_sessions=1,
        last_session_result="failed", last_commit_time="kemarin jam 3",
    )
    bot = CollectionChatBot(chat_group="S0", user_memory=mem)

    assert bot._is_returning_customer is True
    assert bot.customer_phone == "0812"
    # 上次承诺违约 → push_intensity 应 +1
    assert bot.strategy.push_intensity >= 4  # nf=0_S0 基准 push=3 + 违约升级
    # 低信任 → max_push_rounds 应 +1
    assert bot.strategy.max_push_rounds == 4  # nf=0_S0 基准 3 + 低信任升级


def test_bot_with_user_memory_successful_history():
    """履约良好的回头客：不升级策略"""
    from core.chatbot import CollectionChatBot
    from core.strategy_profile import get_strategy_profile

    base = get_strategy_profile(0, "H2")
    mem = UserMemory(
        phone="0812", total_sessions=5, successful_sessions=5,
        last_session_result="success", last_commit_time="kemarin",
    )
    bot = CollectionChatBot(chat_group="H2", user_memory=mem)

    assert bot._is_returning_customer is True
    # 履约好，不升级
    assert bot.strategy.push_intensity == base.push_intensity


def test_bot_without_memory_is_new_customer():
    """无 user_memory 参数：默认为新客"""
    from core.chatbot import CollectionChatBot

    bot = CollectionChatBot(chat_group="H2")
    assert bot._is_returning_customer is False
    assert bot.user_memory is None
