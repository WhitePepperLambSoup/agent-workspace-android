"""The user's knowledge base: their own documents, indexed for search from every conversation."""

from .store import (
    DEFAULT_COLLECTION,
    MAX_DOCUMENTS,
    MAX_FILE_BYTES,
    SUPPORTED_SUFFIXES,
    KnowledgeError,
    KnowledgeStore,
    OcrPages,
    error_code,
    knowledge_root,
    knowledge_store,
)
from .tools import KnowledgeAddTool, KnowledgeSearchTool, KnowledgeUseTool, knowledge_tools

__all__ = [
    "DEFAULT_COLLECTION",
    "MAX_DOCUMENTS",
    "MAX_FILE_BYTES",
    "SUPPORTED_SUFFIXES",
    "KnowledgeAddTool",
    "KnowledgeError",
    "KnowledgeSearchTool",
    "KnowledgeStore",
    "KnowledgeUseTool",
    "OcrPages",
    "error_code",
    "knowledge_root",
    "knowledge_store",
    "knowledge_tools",
]
