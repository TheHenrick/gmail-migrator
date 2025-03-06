"""Tests for the main application module."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Mock the logging setup before importing the app
with patch("logging.FileHandler"), patch("logging.basicConfig"):
    from app.main import app

client = TestClient(app)


class TestMainApp:
    """Test cases for the main application."""

    @pytest.fixture()
    def client(self):
        """Create a test client for the app."""
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test the root endpoint returns the index page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

        # Check that the response contains expected HTML content
        html_content = response.text
        assert "<html" in html_content
        assert "<title>" in html_content
        assert "Gmail Migrator" in html_content

    def test_static_files_served(self, client):
        """Test that static files are properly served."""
        # This test assumes there's a CSS file in the static directory
        response = client.get("/static/css/styles.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_docs_endpoint(self, client):
        """Test the /docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "swagger" in response.text.lower()

    def test_main_function(self):
        """Test the main function that runs the application."""
        # We can't actually run the server in a test, but we can check that
        # the app object is properly configured
        assert app.title == "Gmail Migrator API"
        assert app.description is not None
        assert len(app.routes) > 0
