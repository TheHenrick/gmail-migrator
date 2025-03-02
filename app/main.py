"""
Main application module for Gmail Migrator.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import settings

# Set up logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Gmail Migrator",
    description="API for migrating emails from Gmail to other email services",
    version="0.1.0",
)

# Set up templates
templates_path = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_path))

# Mount static files
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Home page route.
    """
    return templates.TemplateResponse(
        "index.html", {"request": request, "title": "Gmail Migrator"}
    )


@app.get("/health")
async def health():
    """
    Health check endpoint.
    """
    return {"status": "healthy"}


# Include routers here
# from app.api.routers import gmail_router, outlook_router, yahoo_router
# app.include_router(gmail_router)
# app.include_router(outlook_router)
# app.include_router(yahoo_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 