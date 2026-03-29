# ─────────────────────────────────────────────
# JuristLens — Dockerfile
# Python 3.11.9 slim — bypasses Render's default runtime
# ─────────────────────────────────────────────

FROM python:3.11.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by PyMuPDF (fitz) and reportlab
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    libfreetype6-dev \
    libharfbuzz-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    gcc \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (Render injects $PORT at runtime)
EXPOSE 8000

# Start the app
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}