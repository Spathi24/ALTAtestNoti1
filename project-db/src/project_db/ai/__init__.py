"""AI assistant layer — canned reports + text-to-SQL + RAG (modes 1/2/3)."""
from project_db.ai.context import ProjectContext, assemble_project_context
from project_db.ai.financials import (
    FINANCIAL_PROMPT_VERSION,
    FinancialExtractionBatch,
    extract_financials_for_project,
)
from project_db.ai.proposals import (
    ProposalBatch,
    SCOPE_PROMPT_VERSION,
    TIMELINE_PROMPT_VERSION,
    accept_proposal,
    generate_scope_proposals,
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
    get_fast_provider,
)
from project_db.ai.query import AiAssistant, AiResponse, extract_project_ref
from project_db.ai.views import REPORT_REGISTRY

__all__ = [
    "AiAssistant",
    "AiResponse",
    "AnthropicProvider",
    "FINANCIAL_PROMPT_VERSION",
    "FinancialExtractionBatch",
    "LLMMessage",
    "LLMProvider",
    "LLMProviderError",
    "LLMResponse",
    "MockLLMProvider",
    "OpenAICompatibleProvider",
    "ProjectContext",
    "ProposalBatch",
    "REPORT_REGISTRY",
    "SCOPE_PROMPT_VERSION",
    "TIMELINE_PROMPT_VERSION",
    "accept_proposal",
    "assemble_project_context",
    "extract_financials_for_project",
    "extract_project_ref",
    "generate_scope_proposals",
    "generate_timeline_proposals",
    "get_default_provider",
    "get_fast_provider",
    "get_proposal_detail",
    "list_proposals",
    "reject_proposal",
]
