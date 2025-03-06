"""Main application module for Gmail Migrator."""

import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.app import create_app
from app.config import settings

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

# Only add file handler if not in testing mode
if "pytest" not in sys.modules:
    try:
        log_file = Path("app.log")
        # Create log directory if it doesn't exist
        log_file.parent.mkdir(exist_ok=True)
        # Add file handler
        file_handler = logging.FileHandler(log_file)
        logging.getLogger().addHandler(file_handler)
    except (OSError, PermissionError) as e:
        logging.warning(f"Could not set up file logging: {e}")

logger = logging.getLogger(__name__)

# Create FastAPI app
app = create_app()

# Set up templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """
    Home page route.

    Args:
        request: The incoming request

    Returns:
        HTML response with the home page
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Gmail Migrator",
            "gmail_client_id": settings.GMAIL_CLIENT_ID,
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        Dictionary with service status
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    # For local development only, use 127.0.0.1 instead of 0.0.0.0 for security
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.DEBUG,
        access_log=True,
    )
