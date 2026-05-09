# experiments/__init__.py
# Backward compatibility: re-export from core/ so old import paths still work.
# New code should import directly from core.*.

import sys
from pathlib import Path

# 确保 src/ 在 sys.path 中（兼容 python -m src.experiments.xxx 调用方式）
_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

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
