"""Tests for the application dependencies."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.dependencies import get_gmail_client, get_outlook_client


@pytest.mark.unit()
@pytest.mark.outlook()
class TestOutlookDependencies:
    """Test suite for Outlook-related dependencies."""

    @pytest.mark.asyncio()
    async def test_get_outlook_client_success(self):
        """Test successful Outlook client creation."""
        with patch("app.dependencies.OutlookClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await get_outlook_client(authorization="Bearer test_token")

            mock_client_class.assert_called_once_with("test_token")
            assert client == mock_client

    @pytest.mark.asyncio()
    async def test_get_outlook_client_no_auth_header(self):
        """Test Outlook client creation with missing auth header."""
        with pytest.raises(HTTPException) as excinfo:
            await get_outlook_client(authorization=None)

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header with Bearer token is required" in excinfo.value.detail
        assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio()
    async def test_get_outlook_client_invalid_auth_format(self):
        """Test Outlook client creation with invalid auth format."""
        with pytest.raises(HTTPException) as excinfo:
            await get_outlook_client(authorization="InvalidFormat token123")

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header with Bearer token is required" in excinfo.value.detail

    @pytest.mark.asyncio()
    async def test_get_outlook_client_exception(self):
        """Test exception handling in Outlook client creation."""
        with patch("app.dependencies.OutlookClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Client creation error")

            with pytest.raises(HTTPException) as excinfo:
                await get_outlook_client(authorization="Bearer test_token")

            assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or expired Microsoft Graph API credentials" in excinfo.value.detail


@pytest.mark.unit()
@pytest.mark.gmail()
class TestGmailDependencies:
    """Test suite for Gmail-related dependencies."""

    @pytest.mark.asyncio()
    async def test_get_gmail_client_success(self):
        """Test successful Gmail client creation."""
        with patch("app.dependencies.GmailClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            client = await get_gmail_client(authorization="Bearer test_token")

            mock_client_class.assert_called_once()
            assert client == mock_client

    @pytest.mark.asyncio()
    async def test_get_gmail_client_no_auth_header(self):
        """Test Gmail client creation with missing auth header."""
        with pytest.raises(HTTPException) as excinfo:
            await get_gmail_client(authorization=None)

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header with Bearer token is required" in excinfo.value.detail
        assert excinfo.value.headers == {"WWW-Authenticate": "Bearer"}

    @pytest.mark.asyncio()
    async def test_get_gmail_client_invalid_auth_format(self):
        """Test Gmail client creation with invalid auth format."""
        with pytest.raises(HTTPException) as excinfo:
            await get_gmail_client(authorization="InvalidFormat token123")

        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Authorization header with Bearer token is required" in excinfo.value.detail

    @pytest.mark.asyncio()
    async def test_get_gmail_client_exception(self):
        """Test exception handling in Gmail client creation."""
        with patch("app.dependencies.GmailClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Client creation error")

            with pytest.raises(HTTPException) as excinfo:
                await get_gmail_client(authorization="Bearer test_token")

            assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or expired credentials" in excinfo.value.detail
