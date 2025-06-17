"""
Communication Simulator Tests Package

This package contains individual test modules for the Zen MCP Communication Simulator.
Each test is in its own file for better organization and maintainability.
"""

from .base_test import BaseSimulatorTest
from .test_basic_conversation import BasicConversationTest
from .test_consensus_conversation import TestConsensusConversation
from .test_consensus_stance import TestConsensusStance
from .test_consensus_three_models import TestConsensusThreeModels
from .test_content_validation import ContentValidationTest
from .test_conversation_chain_validation import ConversationChainValidationTest
from .test_cross_tool_comprehensive import CrossToolComprehensiveTest
from .test_cross_tool_continuation import CrossToolContinuationTest
from .test_debug_validation import DebugValidationTest
from .test_line_number_validation import LineNumberValidationTest
from .test_logs_validation import LogsValidationTest
from .test_model_thinking_config import TestModelThinkingConfig
from .test_o3_model_selection import O3ModelSelectionTest
from .test_o3_pro_expensive import O3ProExpensiveTest
from .test_ollama_custom_url import OllamaCustomUrlTest
from .test_openrouter_fallback import OpenRouterFallbackTest
from .test_openrouter_models import OpenRouterModelsTest
from .test_per_tool_deduplication import PerToolDeduplicationTest
from .test_planner_continuation_history import PlannerContinuationHistoryTest
from .test_planner_validation import PlannerValidationTest
from .test_redis_validation import RedisValidationTest
from .test_refactor_validation import RefactorValidationTest
from .test_testgen_validation import TestGenValidationTest
from .test_token_allocation_validation import TokenAllocationValidationTest
from .test_vision_capability import VisionCapabilityTest
from .test_xai_models import XAIModelsTest

# Test registry for dynamic loading
TEST_REGISTRY = {
    "basic_conversation": BasicConversationTest,
    "content_validation": ContentValidationTest,
    "per_tool_deduplication": PerToolDeduplicationTest,
    "cross_tool_continuation": CrossToolContinuationTest,
    "cross_tool_comprehensive": CrossToolComprehensiveTest,
    "line_number_validation": LineNumberValidationTest,
    "logs_validation": LogsValidationTest,
    "redis_validation": RedisValidationTest,
    "model_thinking_config": TestModelThinkingConfig,
    "o3_model_selection": O3ModelSelectionTest,
    "ollama_custom_url": OllamaCustomUrlTest,
    "openrouter_fallback": OpenRouterFallbackTest,
    "openrouter_models": OpenRouterModelsTest,
    "planner_validation": PlannerValidationTest,
    "planner_continuation_history": PlannerContinuationHistoryTest,
    "token_allocation_validation": TokenAllocationValidationTest,
    "testgen_validation": TestGenValidationTest,
    "refactor_validation": RefactorValidationTest,
    "debug_validation": DebugValidationTest,
    "conversation_chain_validation": ConversationChainValidationTest,
    "vision_capability": VisionCapabilityTest,
    "xai_models": XAIModelsTest,
    "consensus_conversation": TestConsensusConversation,
    "consensus_stance": TestConsensusStance,
    "consensus_three_models": TestConsensusThreeModels,
    # "o3_pro_expensive": O3ProExpensiveTest,  # COMMENTED OUT - too expensive to run by default
}

__all__ = [
    "BaseSimulatorTest",
    "BasicConversationTest",
    "ContentValidationTest",
    "PerToolDeduplicationTest",
    "CrossToolContinuationTest",
    "CrossToolComprehensiveTest",
    "LineNumberValidationTest",
    "LogsValidationTest",
    "RedisValidationTest",
    "TestModelThinkingConfig",
    "O3ModelSelectionTest",
    "O3ProExpensiveTest",
    "OllamaCustomUrlTest",
    "OpenRouterFallbackTest",
    "OpenRouterModelsTest",
    "PlannerValidationTest",
    "PlannerContinuationHistoryTest",
    "TokenAllocationValidationTest",
    "TestGenValidationTest",
    "RefactorValidationTest",
    "DebugValidationTest",
    "ConversationChainValidationTest",
    "VisionCapabilityTest",
    "XAIModelsTest",
    "TestConsensusConversation",
    "TestConsensusStance",
    "TestConsensusThreeModels",
    "TEST_REGISTRY",
]
