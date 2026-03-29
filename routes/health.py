"""
routes/health.py
Health check endpoint — Render uses this to verify the app is running
GET /api/health
"""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "JuristLens API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }
