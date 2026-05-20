"""AI assistant layer — canned reports + text-to-SQL + RAG (modes 1/2/3)."""
from project_db.ai.context import ProjectContext, assemble_project_context
from project_db.ai.proposals import (
    ProposalBatch,
    TIMELINE_PROMPT_VERSION,
    generate_timeline_proposals,
    get_proposal_detail,
    list_proposals,
    reject_proposal,
)
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
    "ProposalBatch",
    "REPORT_REGISTRY",
    "TIMELINE_PROMPT_VERSION",
    "assemble_project_context",
    "extract_project_ref",
    "generate_timeline_proposals",
    "get_default_provider",
    "get_proposal_detail",
    "list_proposals",
    "reject_proposal",
]
