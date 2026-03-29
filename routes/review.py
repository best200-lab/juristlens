"""
routes/review.py
Main review endpoint — the heart of JuristLens
POST /api/juristlens/review
Handles both single and multi document review
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from schemas import ReviewRequest, ReviewResponse, ReviewMode
from services.document_service import fetch_and_extract
from services.claude_service import (
    review_single_document,
    review_multiple_documents,
    stream_single_document_review
)
from services.supabase_service import save_message, save_multi_results
from config import get_settings
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter()
settings = get_settings()
executor = ThreadPoolExecutor(max_workers=10)


# ─────────────────────────────────────────────
# POST /api/juristlens/review
# Frontend sends document URL(s) + question here
# ─────────────────────────────────────────────
@router.post("/review", response_model=ReviewResponse)
async def review_documents(request: ReviewRequest):
    """
    Main review endpoint.

    Flow:
    1. Receive document URL(s) from frontend
    2. Fetch document(s) from Supabase Storage
    3. Extract text with page references
    4. Send to Claude for analysis
    5. Save results to Supabase
    6. Return structured response to frontend
    """

    # ── Single Document Review ─────────────────
    if request.mode == ReviewMode.single:

        # Validate required fields for single mode
        if not request.document_url or not request.document_name:
            raise HTTPException(
                status_code=400,
                detail="document_url and document_name are required for single review mode"
            )

        try:
            # Step 1: Fetch and extract document from Supabase URL
            # Render downloads the file using the URL Supabase provided
            print(f"[JuristLens] Fetching document: {request.document_name}")
            document_content = fetch_and_extract(
                document_url=request.document_url,
                document_name=request.document_name
            )
            print(f"[JuristLens] Extracted {document_content['page_count']} pages")

            # Step 2: Send extracted text + question to Claude
            print(f"[JuristLens] Sending to Claude: {request.question[:50]}...")
            claude_result = review_single_document(
                document_content=document_content,
                question=request.question
            )

            # Step 3: Save to Supabase for history and export
            save_message(
                session_id=request.session_id,
                question=request.question,
                answer=claude_result.get("answer", ""),
                clause=claude_result.get("clause"),
                page_number=claude_result.get("page"),
                document_name=request.document_name,
                confidence=claude_result.get("confidence")
            )

            # Step 4: Return to frontend
            return ReviewResponse(
                session_id=request.session_id,
                mode=ReviewMode.single,
                answer=claude_result.get("answer"),
                clause=claude_result.get("clause"),
                page=claude_result.get("page"),
                document_name=request.document_name,
                confidence=claude_result.get("confidence")
            )

        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"[JuristLens ERROR] Single review failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Document review failed: {str(e)}"
            )

    # ── Multi Document Review ──────────────────
    elif request.mode == ReviewMode.multi:

        # Validate required fields for multi mode
        if not request.documents or len(request.documents) == 0:
            raise HTTPException(
                status_code=400,
                detail="documents array is required for multi review mode"
            )

        if len(request.documents) > settings.MAX_DOCUMENTS_MULTI:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {settings.MAX_DOCUMENTS_MULTI} documents allowed per review"
            )

        try:
            # Step 1: Fetch and extract ALL documents from Supabase
            # Each document is fetched independently
            print(f"[JuristLens] Fetching {len(request.documents)} documents...")
            documents_content = []

            for doc in request.documents:
                print(f"[JuristLens] Fetching: {doc.document_name}")
                content = fetch_and_extract(
                    document_url=doc.document_url,
                    document_name=doc.document_name
                )
                documents_content.append(content)

            print(f"[JuristLens] All documents extracted. Sending to Claude...")

            # Step 2: Send ALL documents + question to Claude at once
            # Claude reads all documents and returns per-document answers
            claude_result = review_multiple_documents(
                documents_content=documents_content,
                question=request.question
            )

            # Step 3: Save all results to Supabase
            results_list = claude_result.get("results", [])
            save_multi_results(
                session_id=request.session_id,
                question=request.question,
                results=results_list
            )

            # Step 4: Return all results to frontend
            return ReviewResponse(
                session_id=request.session_id,
                mode=ReviewMode.multi,
                results=results_list
            )

        except Exception as e:
            print(f"[JuristLens ERROR] Multi review failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Multi-document review failed: {str(e)}"
            )


# ─────────────────────────────────────────────
# POST /api/juristlens/review/stream
# Streaming version — response types word by word
# Better UX for large documents
# ─────────────────────────────────────────────
@router.post("/review/stream")
async def review_stream(request: ReviewRequest):
    """
    Streaming version of single document review.
    Response streams back to frontend in real-time.
    Frontend should use EventSource or fetch with streaming.
    """
    if request.mode != ReviewMode.single:
        raise HTTPException(
            status_code=400,
            detail="Streaming is only available for single document review"
        )

    if not request.document_url or not request.document_name:
        raise HTTPException(status_code=400, detail="document_url and document_name required")

    try:
        # Fetch and extract document
        document_content = fetch_and_extract(
            document_url=request.document_url,
            document_name=request.document_name
        )

        # Return streaming response
        return StreamingResponse(
            stream_single_document_review(
                document_content=document_content,
                question=request.question
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"   # Important for Render streaming
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))