"""AI assistant layer — canned reports + text-to-SQL + RAG (modes 1/2/3)."""
from project_db.ai.query import AiAssistant, AiResponse, extract_project_ref
from project_db.ai.views import REPORT_REGISTRY

__all__ = ["AiAssistant", "AiResponse", "REPORT_REGISTRY", "extract_project_ref"]
