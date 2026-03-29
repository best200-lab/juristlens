"""
services/claude_service.py
All Claude API calls live here.
Uses claude-sonnet-4-6 — best model for legal document analysis
Token optimizations:
  - Reduced max_tokens (800 for single, 2000 for multi)
  - Uses get_optimized_text_for_claude() — smart chunking
  - Token usage tracking on every request
  - Streaming support for better UX
"""

import json
import anthropic
from typing import Dict, List, Generator
from config import get_settings
from services.document_service import get_optimized_text_for_claude

settings = get_settings()

# Initialize Anthropic client once
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ─────────────────────────────────────────────
# Token Usage Tracker
# ─────────────────────────────────────────────
def log_token_usage(message, operation: str = "review") -> None:
    """
    Log token usage and estimated cost after every Claude call.
    claude-sonnet-4-6 pricing: $3 input / $15 output per 1M tokens
    """
    try:
        input_tokens  = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        total_tokens  = input_tokens + output_tokens

        input_cost  = (input_tokens  * 3)  / 1_000_000
        output_cost = (output_tokens * 15) / 1_000_000
        total_cost  = input_cost + output_cost

        print(
            f"[JuristLens] [{operation}] Tokens → "
            f"input: {input_tokens:,} | output: {output_tokens:,} | "
            f"total: {total_tokens:,} | cost: ${total_cost:.4f}"
        )
    except Exception:
        pass  # Don't break the request if logging fails


# ─────────────────────────────────────────────
# System Prompt — Claude's Legal Persona
# ─────────────────────────────────────────────
JURISTLENS_SYSTEM_PROMPT = """You are JuristLens, an expert AI legal document analyst 
built for African lawyers. You have deep knowledge of contract law, commercial agreements, 
and legal documents commonly used in Nigeria, Rwanda, Kenya, Uganda, and Tanzania.

When analyzing documents:
1. Read carefully and identify the most relevant clauses
2. Give a clear, precise answer to the lawyer's question
3. Always identify the EXACT clause or sentence that supports your answer
4. Always identify the PAGE NUMBER where the clause is found using the [PAGE X] markers
5. Be concise but thorough — lawyers need accuracy above all

You must ALWAYS respond with valid JSON in this exact format:
{
  "answer": "Your clear answer to the question here",
  "clause": "The exact verbatim clause text from the document that supports your answer",
  "page": 5,
  "confidence": "high | medium | low"
}

If no relevant clause is found, respond:
{
  "answer": "No relevant information found for this question in the document.",
  "clause": null,
  "page": null,
  "confidence": "low"
}

Do not include any text outside the JSON. Do not use markdown. Only return the JSON object."""


MULTI_DOCUMENT_SYSTEM_PROMPT = """You are JuristLens, an expert AI legal document analyst 
built for African lawyers. You are analyzing MULTIPLE legal documents simultaneously.

For each document provided, answer the lawyer's question by finding the most relevant clause.

You must ALWAYS respond with valid JSON in this exact format:
{
  "results": [
    {
      "document_name": "filename.pdf",
      "answer": "Answer for this specific document",
      "clause": "Exact verbatim clause from this document",
      "page": 3,
      "confidence": "high | medium | low"
    },
    {
      "document_name": "filename2.pdf",
      "answer": "Answer for this document or No relevant clause found",
      "clause": null,
      "page": null,
      "confidence": "low"
    }
  ]
}

Analyze EVERY document in the list. Do not skip any.
Do not include any text outside the JSON. Only return the JSON object."""


# ─────────────────────────────────────────────
# Single Document Review
# ─────────────────────────────────────────────
def review_single_document(document_content: Dict, question: str) -> Dict:
    """
    Send single document to Claude for analysis.
    Uses smart chunking to reduce tokens by 60-80%.
    Returns structured answer with clause and page number.
    """

    # ── Token saving: use optimized text, not full_text ──
    optimized_text = get_optimized_text_for_claude(document_content, question)

    prompt = f"""Here is the legal document to analyze:

Document Name: {document_content['document_name']}
Total Pages: {document_content['page_count']}

--- DOCUMENT CONTENT ---
{optimized_text}
--- END OF DOCUMENT ---

Lawyer's Question: {question}

Analyze the document and answer the question in the required JSON format."""

    try:
        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=800,                        # ← reduced from 1500, saves tokens
            system=JURISTLENS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        # Log token usage and cost
        log_token_usage(message, operation="single-review")

        # Parse Claude's JSON response
        response_text = message.content[0].text.strip()

        # Strip markdown code fences if Claude wraps in ```json
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        return result

    except json.JSONDecodeError:
        # Graceful fallback if JSON parsing fails
        return {
            "answer": message.content[0].text,
            "clause": None,
            "page": None,
            "confidence": "medium"
        }
    except anthropic.APIError as e:
        raise Exception(f"Claude API error: {str(e)}")


# ─────────────────────────────────────────────
# Multiple Documents Review
# ─────────────────────────────────────────────
def review_multiple_documents(documents_content: List[Dict], question: str) -> Dict:
    """
    Send multiple documents to Claude simultaneously.
    Uses smart chunking per document to manage tokens.
    Claude reads all documents and returns per-document answers.
    """

    # ── Token saving: use optimized text per document ──
    all_documents_text = ""
    for i, doc in enumerate(documents_content, 1):
        optimized_text = get_optimized_text_for_claude(doc, question)
        all_documents_text += f"""
=== DOCUMENT {i}: {doc['document_name']} ===
Total Pages: {doc['page_count']}
{optimized_text}
=== END OF DOCUMENT {i} ===

"""

    prompt = f"""Here are {len(documents_content)} legal documents to analyze:

{all_documents_text}

Lawyer's Question: {question}

Analyze EVERY document above and answer the question for each one.
Return results in the required JSON format with a result for every document."""

    try:
        message = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2000,                       # Multi needs more tokens
            system=MULTI_DOCUMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        # Log token usage and cost
        log_token_usage(message, operation="multi-review")

        response_text = message.content[0].text.strip()

        # Strip markdown code fences
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        return result

    except json.JSONDecodeError:
        raise Exception("Failed to parse Claude response for multiple documents")
    except anthropic.APIError as e:
        raise Exception(f"Claude API error: {str(e)}")


# ─────────────────────────────────────────────
# Streaming — Single Document
# Makes response feel instant like ChatGPT
# ─────────────────────────────────────────────
def stream_single_document_review(
    document_content: Dict,
    question: str
) -> Generator[str, None, None]:
    """
    Streaming version — Claude types response word by word.
    Frontend receives chunks in real-time via SSE.
    """

    # ── Token saving: use optimized text ──
    optimized_text = get_optimized_text_for_claude(document_content, question)

    prompt = f"""Here is the legal document to analyze:

Document Name: {document_content['document_name']}
Total Pages: {document_content['page_count']}

--- DOCUMENT CONTENT ---
{optimized_text}
--- END OF DOCUMENT ---

Lawyer's Question: {question}

Provide a clear answer. Then identify the exact supporting clause and page number."""

    with client.messages.stream(
        model=settings.CLAUDE_MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for text_chunk in stream.text_stream:
            yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

    yield f"data: {json.dumps({'done': True})}\n\n"


# ─────────────────────────────────────────────
# Generate Export Summary
# ─────────────────────────────────────────────
def generate_export_summary(session_messages: List[Dict]) -> str:
    """
    Ask Claude to generate a clean professional summary
    of the entire review session for PDF/DOCX export.
    """
    messages_text = ""
    for msg in session_messages:
        messages_text += f"""
Q: {msg['question']}
A: {msg['answer']}
Source Clause: {msg.get('clause', 'N/A')}
Page: {msg.get('page_number', 'N/A')}
---"""

    prompt = f"""Based on this legal document review session, write a clean professional 
legal analysis report. Format it with clear sections:
1. Executive Summary
2. Key Findings (one per question asked)
3. Notable Clauses
4. Recommendations

Here are the Q&A results:
{messages_text}

Write in formal legal English suitable for a barrister's report.
Be concise — aim for 300-400 words maximum."""

    message = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=600,                            # ← reduced, export summary doesn't need more
        messages=[{"role": "user", "content": prompt}]
    )

    # Log token usage
    log_token_usage(message, operation="export-summary")

    return message.content[0].text