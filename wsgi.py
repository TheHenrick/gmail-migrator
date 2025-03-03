"""WSGI entry point for the application."""

import uvicorn

from app.config import settings

if __name__ == "__main__":
    """Run the FastAPI application using uvicorn."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0" if settings.DEBUG else "127.0.0.1",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
