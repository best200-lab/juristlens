"""
JuristLens - Legal Document Intelligence Backend
Built for Jurist Mind | Powered by Claude claude-sonnet-4-6
Deploy on Render at: https://juristmind.onrender.com
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import uvicorn

from routes.review import router as review_router
from routes.export import router as export_router
from routes.health import router as health_router

# ─────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────
app = FastAPI(
    title="JuristLens API",
    description="Legal Document Intelligence for Jurist Mind",
    version="1.0.0"
)

# ─────────────────────────────────────────────
# CORS — Allow Supabase frontend to communicate
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://chat.juristmind.com",   # Production frontend
        "http://localhost:3000",          # Local development
        "http://localhost:5173",          # Vite dev server
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Register Routes
# ─────────────────────────────────────────────
app.include_router(health_router, prefix="/api")
app.include_router(review_router, prefix="/api/juristlens")
app.include_router(export_router, prefix="/api/juristlens")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)