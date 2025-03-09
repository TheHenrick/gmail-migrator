"""Main application factory for the FastAPI app."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.api.routers import gmail, migration, outlook
from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def create_app(testing: bool = False) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        testing: Whether the app is being created for testing

    Returns:
        FastAPI: Configured FastAPI application
    """
    app = FastAPI(
        title="Gmail Migrator API",
        description="API for migrating emails between email providers",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict this to specific domains
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(gmail.router)
    app.include_router(outlook.router)
    app.include_router(migration.router)

    # For testing compatibility
    if testing:
        # Add test_client method for pytest compatibility with Flask-style tests
        app.test_client = lambda: app.test_client_class(app)

        # Simple TestClient class for Flask-style tests
        class TestClientClass:
            def __init__(self, app: FastAPI) -> None:
                self.app = app

            def __call__(self, _app: FastAPI) -> "TestClientClass":  # noqa: ARG002
                return self

            # Ignoring return type and kwargs type annotation per project's ruff config
            def get(self, path: str, **kwargs):  # noqa: ANN003, ANN202
                with TestClient(self.app) as client:
                    return client.get(path, **kwargs)

        app.test_client_class = TestClientClass

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
