"""
schemas.py — All Request & Response Models
Pydantic ensures data is validated before processing
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from enum import Enum


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────
class ReviewMode(str, Enum):
    single = "single"
    multi = "multi"


class ExportFormat(str, Enum):
    pdf = "pdf"
    docx = "docx"


class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


# ─────────────────────────────────────────────
# Document Item (used in multi-review)
# ─────────────────────────────────────────────
class DocumentItem(BaseModel):
    document_url: str          # Supabase public storage URL
    document_name: str         # Original filename e.g. "contract.pdf"


# ─────────────────────────────────────────────
# Review Request — what frontend sends to Render
# ─────────────────────────────────────────────
class ReviewRequest(BaseModel):
    mode: ReviewMode
    question: str
    session_id: str
    lawyer_id: str

    # Single mode — one document
    document_url: Optional[str] = None
    document_name: Optional[str] = None

    # Multi mode — array of documents
    documents: Optional[List[DocumentItem]] = None


# ─────────────────────────────────────────────
# Single Document Result
# ─────────────────────────────────────────────
class DocumentResult(BaseModel):
    document_name: str
    answer: str
    clause: Optional[str] = None        # The exact source clause text
    page: Optional[int] = None          # Page number where clause was found
    confidence: Optional[Confidence] = None


# ─────────────────────────────────────────────
# Review Response — what Render sends back
# ─────────────────────────────────────────────
class ReviewResponse(BaseModel):
    session_id: str
    mode: ReviewMode
    # Single mode response
    answer: Optional[str] = None
    clause: Optional[str] = None
    page: Optional[int] = None
    document_name: Optional[str] = None
    confidence: Optional[str] = None
    # Multi mode response
    results: Optional[List[DocumentResult]] = None


# ─────────────────────────────────────────────
# Export Request
# ─────────────────────────────────────────────
class ExportRequest(BaseModel):
    session_id: str
    lawyer_id: str
    format: ExportFormat               # "pdf" or "docx"