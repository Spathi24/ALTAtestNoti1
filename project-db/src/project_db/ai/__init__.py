"""AI assistant layer — canned reports + text-to-SQL + RAG (modes 1/2/3)."""
from project_db.ai.context import ProjectContext, assemble_project_context
from project_db.ai.providers import (
    AnthropicProvider,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    MockLLMProvider,
    OpenAICompatibleProvider,
    get_default_provider,
)
from project_db.ai.query import AiAssistant, AiResponse, extract_project_ref
from project_db.ai.views import REPORT_REGISTRY

__all__ = [
    "AiAssistant",
    "AiResponse",
    "AnthropicProvider",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "ProjectContext",
    "REPORT_REGISTRY",
    "assemble_project_context",
    "extract_project_ref",
    "get_default_provider",
]
