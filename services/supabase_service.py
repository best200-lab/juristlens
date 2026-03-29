"""
services/supabase_service.py
Handles all Supabase database operations
Saves sessions, messages, and retrieves history
"""

from supabase import create_client, Client
from typing import Dict, List, Optional
from config import get_settings
import json

settings = get_settings()

# Initialize Supabase client once
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY        # Use service key on backend (not anon key)
)


# ─────────────────────────────────────────────
# Save Review Message to Database
# ─────────────────────────────────────────────
def save_message(
    session_id: str,
    question: str,
    answer: str,
    clause: Optional[str],
    page_number: Optional[int],
    document_name: Optional[str],
    confidence: Optional[str]
) -> Dict:
    """
    Save each Q&A exchange to juristlens_messages table.
    This allows lawyers to view history and enables export.
    """
    try:
        data = {
            "session_id": session_id,
            "question": question,
            "answer": answer,
            "clause": clause,
            "page_number": page_number,
            "document_name": document_name,
            "confidence": confidence
        }

        result = supabase.table("juristlens_messages").insert(data).execute()
        return result.data[0] if result.data else {}

    except Exception as e:
        # Don't fail the whole request if DB save fails
        print(f"Warning: Failed to save message to Supabase: {str(e)}")
        return {}


# ─────────────────────────────────────────────
# Save Multi-Review Results
# ─────────────────────────────────────────────
def save_multi_results(
    session_id: str,
    question: str,
    results: List[Dict]
) -> None:
    """
    Save each document's result separately for multi-review.
    Each document result becomes its own row.
    """
    for result in results:
        save_message(
            session_id=session_id,
            question=question,
            answer=result.get("answer", ""),
            clause=result.get("clause"),
            page_number=result.get("page"),
            document_name=result.get("document_name"),
            confidence=result.get("confidence")
        )


# ─────────────────────────────────────────────
# Get All Messages for a Session
# Used for export
# ─────────────────────────────────────────────
def get_session_messages(session_id: str) -> List[Dict]:
    """
    Retrieve all Q&A messages for a session.
    Used when lawyer requests PDF/DOCX export.
    """
    try:
        result = (
            supabase.table("juristlens_messages")
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        return result.data or []

    except Exception as e:
        raise Exception(f"Failed to retrieve session messages: {str(e)}")


# ─────────────────────────────────────────────
# Get Session Details
# ─────────────────────────────────────────────
def get_session(session_id: str) -> Optional[Dict]:
    """
    Retrieve session details including document URLs.
    Used to re-fetch documents for export.
    """
    try:
        result = (
            supabase.table("juristlens_sessions")
            .select("*")
            .eq("session_id", session_id)
            .single()
            .execute()
        )
        return result.data

    except Exception as e:
        raise Exception(f"Failed to retrieve session: {str(e)}")


# ─────────────────────────────────────────────
# Verify Lawyer Owns Session (Security Check)
# ─────────────────────────────────────────────
def verify_session_ownership(session_id: str, lawyer_id: str) -> bool:
    """
    Security check — ensure lawyer can only access their own sessions.
    Always call this before processing export requests.
    """
    try:
        result = (
            supabase.table("juristlens_sessions")
            .select("lawyer_id")
            .eq("session_id", session_id)
            .eq("lawyer_id", lawyer_id)
            .execute()
        )
        return len(result.data) > 0

    except Exception:
        return False