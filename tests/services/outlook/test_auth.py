"""Tests for the Outlook authentication module."""

from unittest.mock import MagicMock, mock_open, patch

import pytest
from fastapi import HTTPException

from app.services.outlook.auth import OutlookAuthManager, _raise_token_error


@pytest.fixture()
def auth_manager():
    """Fixture for an OutlookAuthManager with mock credentials."""
    patch("app.services.outlook.auth.msal.ConfidentialClientApplication").start()
    manager = OutlookAuthManager(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        redirect_uri="http://localhost:8000/mock-callback",
    )
    yield manager
    patch.stopall()


@pytest.mark.unit()
@pytest.mark.outlook()
@pytest.mark.auth()
class TestOutlookAuthManager:
    """Test suite for the OutlookAuthManager class."""

    def test_init(self, auth_manager):
        """Test initialization of the auth manager."""
        assert auth_manager.client_id == "mock_client_id"
        assert auth_manager.client_secret == "mock_client_secret"
        assert auth_manager.redirect_uri == "http://localhost:8000/mock-callback"
        assert auth_manager.scopes == [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.ReadWrite",
            "https://graph.microsoft.com/Mail.Send",
            "offline_access",
            "openid",
            "profile",
        ]
        assert auth_manager.app is not None

    @patch("app.services.outlook.auth.CACHE_PATH")
    @patch("app.services.outlook.auth.msal.SerializableTokenCache")
    def test_load_cache_file_exists(self, mock_token_cache, mock_cache_path):
        """Test loading token cache when file exists."""
        mock_cache = MagicMock()
        mock_token_cache.return_value = mock_cache
        mock_cache_path.exists.return_value = True

        # Mock the open function
        mock_file = mock_open(read_data='{"token": "cached_token"}')

        with (
            patch("app.services.outlook.auth.CACHE_PATH.open", mock_file),
            patch("app.services.outlook.auth.msal.ConfidentialClientApplication"),
        ):
            # Create the auth manager but use it in the test
            OutlookAuthManager()

            # The cache should be loaded from the file
            mock_cache.deserialize.assert_called_once_with('{"token": "cached_token"}')

    @patch("app.services.outlook.auth.CACHE_PATH")
    @patch("app.services.outlook.auth.msal.SerializableTokenCache")
    def test_load_cache_file_not_exists(self, mock_token_cache, mock_cache_path):
        """Test loading token cache when file doesn't exist."""
        mock_cache = MagicMock()
        mock_token_cache.return_value = mock_cache
        mock_cache_path.exists.return_value = False

        with patch("app.services.outlook.auth.msal.ConfidentialClientApplication"):
            # Create the auth manager but don't assign it to a variable
            OutlookAuthManager()

            # The cache should not be loaded
            mock_cache.deserialize.assert_not_called()

    def test_save_cache_changed(self, auth_manager):
        """Test saving token cache when it has changed."""
        auth_manager.app.token_cache.has_state_changed = True
        auth_manager.app.token_cache.serialize.return_value = '{"token": "new_token"}'

        mock_file = mock_open()
        with patch("pathlib.Path.open", mock_file):
            auth_manager._save_cache()

            # The cache should be saved to the file
            mock_file.assert_called_once_with("w")
            mock_file().write.assert_called_once_with('{"token": "new_token"}')

    def test_save_cache_not_changed(self, auth_manager):
        """Test saving token cache when it hasn't changed."""
        auth_manager.app.token_cache.has_state_changed = False

        mock_file = mock_open()
        with patch("pathlib.Path.open", mock_file):
            auth_manager._save_cache()

            # The cache should not be saved
            mock_file.assert_not_called()

    def test_get_auth_url(self, auth_manager):
        """Test generating an authorization URL."""
        auth_manager.app.get_authorization_request_url.return_value = "https://login.microsoftonline.com/auth"

        auth_url = auth_manager.get_auth_url()

        auth_manager.app.get_authorization_request_url.assert_called_once_with(
            auth_manager.scopes,
            redirect_uri=auth_manager.redirect_uri,
            prompt="select_account",
        )
        assert auth_url == "https://login.microsoftonline.com/auth"

    def test_get_token_from_code_success(self, auth_manager):
        """Test successful token acquisition from code."""
        mock_token = {"access_token": "mock_token", "refresh_token": "mock_refresh"}
        auth_manager.app.acquire_token_by_authorization_code.return_value = mock_token

        with patch.object(auth_manager, "_save_cache") as mock_save_cache:
            result = auth_manager.get_token_from_code("mock_code")

            auth_manager.app.acquire_token_by_authorization_code.assert_called_once_with(
                "mock_code",
                scopes=auth_manager.scopes,
                redirect_uri=auth_manager.redirect_uri,
            )
            mock_save_cache.assert_called_once()
            assert result == mock_token

    def test_get_token_from_code_error(self, auth_manager):
        """Test error handling in token acquisition from code."""
        error_response = {
            "error": "invalid_grant",
            "error_description": "Invalid authorization code",
        }
        auth_manager.app.acquire_token_by_authorization_code.return_value = error_response

        with patch.object(auth_manager, "_save_cache") as mock_save_cache:
            with pytest.raises(HTTPException) as excinfo:
                auth_manager.get_token_from_code("invalid_code")

            mock_save_cache.assert_called_once()
            assert excinfo.value.status_code == 500
            assert "Invalid authorization code" in str(excinfo.value.detail)

    def test_get_token_from_code_exception(self, auth_manager):
        """Test exception handling in token acquisition from code."""
        auth_manager.app.acquire_token_by_authorization_code.side_effect = Exception("Network error")

        with pytest.raises(HTTPException) as excinfo:
            auth_manager.get_token_from_code("mock_code")

        assert excinfo.value.status_code == 500
        assert "Network error" in str(excinfo.value.detail)

    def test_refresh_token_success(self, auth_manager):
        """Test successful token refresh."""
        mock_token = {"access_token": "new_token", "refresh_token": "new_refresh"}
        auth_manager.app.acquire_token_by_refresh_token.return_value = mock_token

        with patch.object(auth_manager, "_save_cache") as mock_save_cache:
            result = auth_manager.refresh_token("mock_refresh_token")

            auth_manager.app.acquire_token_by_refresh_token.assert_called_once_with(
                "mock_refresh_token", scopes=auth_manager.scopes
            )
            mock_save_cache.assert_called_once()
            assert result == mock_token

    def test_refresh_token_error(self, auth_manager):
        """Test error handling in token refresh."""
        error_response = {
            "error": "invalid_grant",
            "error_description": "Invalid refresh token",
        }
        auth_manager.app.acquire_token_by_refresh_token.return_value = error_response

        with patch.object(auth_manager, "_save_cache") as mock_save_cache:
            with pytest.raises(HTTPException) as excinfo:
                auth_manager.refresh_token("invalid_refresh_token")

            mock_save_cache.assert_called_once()
            assert excinfo.value.status_code == 500
            assert "Invalid refresh token" in str(excinfo.value.detail)

    def test_refresh_token_exception(self, auth_manager):
        """Test exception handling in token refresh."""
        auth_manager.app.acquire_token_by_refresh_token.side_effect = Exception("Network error")

        with pytest.raises(HTTPException) as excinfo:
            auth_manager.refresh_token("mock_refresh_token")

        assert excinfo.value.status_code == 500
        assert "Network error" in str(excinfo.value.detail)


@pytest.mark.unit()
@pytest.mark.outlook()
@pytest.mark.auth()
def test_raise_token_error():
    """Test the _raise_token_error helper function."""
    error_result = {
        "error": "invalid_grant",
        "error_description": "Token expired",
    }

    with pytest.raises(HTTPException) as excinfo:
        _raise_token_error(error_result, "refresh")

    assert excinfo.value.status_code == 400
    assert "Failed to refresh token: Token expired" in str(excinfo.value.detail)
