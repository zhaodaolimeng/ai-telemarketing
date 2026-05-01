# experiments/__init__.py
# Backward compatibility: re-export from core/ so old import paths still work.
# New code should import directly from core.*.

from core.chatbot import (
    CollectionChatBot,
    ChatState,
    ChatTurn,
    ConversationLog,
    TextToSpeech,
    TimeDetector,
    VariableReplacer,
    get_stage_from_state,
)

from core.simulator import (
    RealCustomerSimulatorV2,
    GOLDEN_TEST_CASES_V2,
)

from core.evaluation import (
    EvaluationFrameworkV2,
    EvaluationResult,
)

from core.metrics import (
    collector,
    ConversationMetrics,
    PerformanceMetrics,
    get_system_metrics,
)

from core.translator import translate_text
