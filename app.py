"""
AI Content API - Multi-LLM Content Generation.

REST API for generating content using OpenAI, Gemini, or Ollama.

Run:  python app.py
Open: http://localhost:8000
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger

from api import router as api_router
from config import settings
from database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, close on shutdown."""
    logger.info("Starting AI Content API...")
    await init_db()
    logger.info("Database initialized")
    yield
    await close_db()
    logger.info("Shutting down AI Content API")


app = FastAPI(
    title="AI Content API",
    description="Multi-LLM REST API for AI content generation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(api_router, prefix="/api")


@app.get("/", include_in_schema=False)
async def index():
    """Serve the web dashboard."""
    return FileResponse(Path(__file__).parent / "web" / "index.html")


if __name__ == "__main__":
    host = settings.host
    port = settings.port
    debug = settings.debug
    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run("app:app", host=host, port=port, reload=debug, log_level="info")
