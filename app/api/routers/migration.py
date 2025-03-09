"""Router for email migration API endpoints."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.services.gmail.client import GmailClient
from app.services.migration.gmail_to_outlook import GmailToOutlookMigrationService
from app.services.outlook.client import OutlookClient

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/migration", tags=["migration"])

# Global migration state for real-time updates
migration_state = {
    "status": "idle",  # idle, running, completed, failed
    "total_emails": 0,
    "processed_emails": 0,
    "successful_emails": 0,
    "failed_emails": 0,
    "current_label": "",
    "total_labels": 0,
    "processed_labels": 0,
    "logs": [],
}

# Queue for migration updates
migration_updates_queue = asyncio.Queue()

# List of connected clients for SSE
connected_clients = []


# Function to update migration state
async def update_migration_state(update: dict) -> None:
    """
    Update the migration state and send updates to clients.

    Args:
        update: Dictionary with state updates
    """
    logger.info(f"Received migration state update: {update}")

    # Update logs if provided
    if "logs" in update:
        log_entry = update["logs"]

        # Add timestamp if not present
        if not log_entry.startswith("["):
            timestamp = datetime.now(tz=UTC).strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {log_entry}"

        migration_state["logs"].append(log_entry)

        # Keep only the last 100 log entries
        if len(migration_state["logs"]) > 100:
            migration_state["logs"] = migration_state["logs"][-100:]

    # Update other state fields
    for key, value in update.items():
        if key != "logs":
            migration_state[key] = value

    # Notify all connected clients
    for queue in connected_clients:
        await queue.put(json.dumps(migration_state))


class LabelMappingResponse(BaseModel):
    """Response model for label to folder mapping."""

    gmail_label_id: str
    outlook_folder_id: str
    gmail_label_name: str
    outlook_folder_name: str


class MigrationResultsResponse(BaseModel):
    """Response model for migration results."""

    total: int = Field(..., description="Total number of emails processed")
    successful: int = Field(..., description="Number of emails successfully migrated")
    failed: int = Field(..., description="Number of emails that failed to migrate")
    failed_ids: list[str] = Field(
        default_factory=list, description="IDs of emails that failed to migrate"
    )


class CredentialsModel(BaseModel):
    """Model for credentials."""

    token: str
    user_info: dict | None = None
    client_id: str = ""
    client_secret: str = ""
    refresh_token: str = ""
    token_uri: str = "https://oauth2.googleapis.com/token"


class DestinationCredentialsModel(BaseModel):
    """Model for destination credentials."""

    token: str
    provider: str


class CredentialsRequest(BaseModel):
    """Request model for credentials."""

    gmail: CredentialsModel
    destination: DestinationCredentialsModel


class LabelMigrationRequest(BaseModel):
    """Request model for migrating emails by label."""

    label_id: str | None = Field(None, description="Gmail label ID")
    max_emails: int = Field(
        100, description="Maximum number of emails to migrate", ge=1, le=1000
    )
    credentials: CredentialsRequest | None = None


class FullMigrationRequest(BaseModel):
    """Request model for full migration."""

    max_emails_per_label: int = Field(
        100,
        description="Maximum number of emails to migrate per label",
        ge=1,
        le=1000,
    )
    credentials: CredentialsRequest | None = None


def _raise_bad_request(error_msg: str) -> None:
    """
    Raise a bad request HTTP exception.

    Args:
        error_msg: Error message to include in the exception
    """
    logger.error(f"Migration error: {error_msg}")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_msg,
    )


def _validate_credentials(credentials: CredentialsRequest | None) -> None:
    """Validate that credentials are provided and contain required fields."""
    if not credentials:
        logger.error("Credentials are required but none were provided")
        _raise_bad_request("Credentials are required")

    # Validate Gmail credentials
    if not credentials.gmail or not credentials.gmail.token:
        logger.error("Gmail credentials are missing or invalid")
        _raise_bad_request("Gmail credentials are required")

    # Validate destination credentials
    if not credentials.destination or not credentials.destination.token:
        logger.error("Destination credentials are missing or invalid")
        _raise_bad_request("Destination credentials are required")

    # Validate destination provider
    if credentials.destination.provider not in ["outlook", "yahoo"]:
        logger.error(
            f"Unsupported destination provider: {credentials.destination.provider}"
        )
        _raise_bad_request(
            f"Unsupported destination provider: {credentials.destination.provider}"
        )


@router.get("/status/stream")
async def stream_migration_status() -> EventSourceResponse:
    """
    Stream migration status updates using Server-Sent Events (SSE).

    Returns:
        EventSourceResponse: A streaming response for SSE
    """
    queue = asyncio.Queue()
    connected_clients.append(queue)

    logger.info("New SSE connection established for migration status")

    async def event_generator() -> AsyncGenerator[str, None]:
        # Send the current state immediately
        logger.info(f"Sending initial migration state: {json.dumps(migration_state)}")
        yield json.dumps(migration_state)

        try:
            while True:
                data = await queue.get()
                if data is None:
                    break
                yield data
        except asyncio.CancelledError:
            logger.info("SSE connection closed by client")
            connected_clients.remove(queue)
            raise
        finally:
            if queue in connected_clients:
                connected_clients.remove(queue)
                logger.info("SSE connection closed and removed from connected clients")

    return EventSourceResponse(event_generator())


@router.get("/status")
async def get_migration_status() -> dict:
    """
    Get the current migration status.

    Returns:
        dict: The current migration state
    """
    return migration_state


@router.post("/gmail-to-outlook/labels", response_model=dict[str, str])
async def migrate_labels_to_folders(
    request: LabelMigrationRequest,
) -> dict[str, str]:
    """
    Migrate Gmail labels to Outlook folders.

    Args:
        request: The migration request containing credentials.

    Returns:
        A dictionary mapping Gmail label IDs to Outlook folder IDs.
    """
    try:
        # Validate credentials
        _validate_credentials(request.credentials)

        # Extract credentials
        gmail_creds = request.credentials.gmail
        outlook_creds = request.credentials.destination

        # Create clients
        gmail_client = GmailClient(
            credentials={
                "token": gmail_creds.token,
                "refresh_token": gmail_creds.refresh_token,
                "client_id": gmail_creds.client_id,
                "client_secret": gmail_creds.client_secret,
                "token_uri": gmail_creds.token_uri,
            }
        )

        outlook_client = OutlookClient(access_token=outlook_creds.token)

        # Create migration service
        migration_service = GmailToOutlookMigrationService(
            gmail_client=gmail_client, outlook_client=outlook_client
        )

        # Set the update status callback
        migration_service.update_status_callback = update_migration_state

        # Update initial migration state
        await update_migration_state(
            {
                "status": "running",
                "logs": "Migrating Gmail labels to Outlook folders...",
            }
        )

        # Migrate labels to folders
        folder_mapping = await migration_service.migrate_labels_to_folders()

        # Update final migration state
        await update_migration_state(
            {"logs": f"Successfully migrated {len(folder_mapping)} labels to folders"}
        )

        return folder_mapping

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Migration error")
        _raise_bad_request(f"Failed to migrate labels: {str(e)}")


@router.post("/gmail-to-outlook/by-label", response_model=MigrationResultsResponse)
async def migrate_emails_by_label(
    request: LabelMigrationRequest,
) -> dict[str, Any]:
    """
    Migrate emails from a specific Gmail label to the corresponding Outlook folder.

    Args:
        request: Migration request parameters

    Returns:
        Migration results
    """
    try:
        if not request.credentials:
            _raise_bad_request("Credentials are required")

        # Create clients with the provided credentials
        gmail_client = GmailClient(credentials=request.credentials.gmail.dict())
        outlook_client = OutlookClient(request.credentials.destination.token)

        # Create migration service
        migration_service = GmailToOutlookMigrationService(
            gmail_client=gmail_client, outlook_client=outlook_client
        )

        # Set the update status callback
        migration_service.update_status_callback = update_migration_state

        # Update initial migration state
        await update_migration_state(
            {
                "status": "running",
                "total_emails": 0,
                "processed_emails": 0,
                "successful_emails": 0,
                "failed_emails": 0,
                "current_label": request.label_id or "",
                "total_labels": 1,
                "processed_labels": 0,
                "logs": f"Starting migration for label: {request.label_id}",
            }
        )

        # Migrate emails
        migration_result = await migration_service.migrate_emails_by_label(
            label_id=request.label_id, max_emails=request.max_emails
        )

        # Update final migration state
        await update_migration_state(
            {
                "status": "completed",
                "processed_labels": 1,
                "logs": (
                    f"Migration completed: {migration_result.get('successful', 0)} of "
                    f"{migration_result.get('total', 0)} emails migrated successfully"
                ),
            }
        )

        return migration_result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Migration error")
        _raise_bad_request(f"Failed to migrate emails: {str(e)}")


@router.post("/gmail-to-outlook/all", response_model=dict)
async def migrate_all_emails(
    request: FullMigrationRequest,
) -> dict:
    """
    Migrate all emails from Gmail to Outlook.

    Args:
        request: Migration request with credentials and options

    Returns:
        Dict with migration results
    """
    try:
        # Validate credentials
        _validate_credentials(request.credentials)

        # Extract credentials and options
        gmail_creds = request.credentials.gmail
        outlook_creds = request.credentials.destination
        max_emails = request.max_emails_per_label

        # Create clients
        gmail_client = GmailClient(
            credentials={
                "token": gmail_creds.token,
                "refresh_token": gmail_creds.refresh_token,
                "client_id": gmail_creds.client_id,
                "client_secret": gmail_creds.client_secret,
                "token_uri": gmail_creds.token_uri,
            }
        )

        outlook_client = OutlookClient(access_token=outlook_creds.token)

        # Migrate emails
        migration_service = GmailToOutlookMigrationService(
            gmail_client=gmail_client, outlook_client=outlook_client
        )

        # Set the update status callback
        migration_service.update_status_callback = update_migration_state

        # Update initial migration state
        await update_migration_state(
            {
                "status": "running",
                "total_emails": 0,
                "processed_emails": 0,
                "successful_emails": 0,
                "failed_emails": 0,
                "current_label": "",
                "total_labels": 0,
                "processed_labels": 0,
                "logs": "Starting migration process...",
            }
        )

        migration_result = await migration_service.migrate_all_emails(
            max_emails_per_label=max_emails
        )

        # Update final migration state
        await update_migration_state(
            {
                "status": "completed",
                "logs": (
                    f"Migration completed: {migration_result.get('successful', 0)} of "
                    f"{migration_result.get('total', 0)} emails migrated successfully"
                ),
            }
        )

        return migration_result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.exception("Migration error")
        _raise_bad_request(f"Failed to migrate emails: {str(e)}")


@router.post("/gmail-to-outlook/import-all", response_model=dict)
async def import_all_emails(
    request: FullMigrationRequest,
) -> dict:
    """
    Import all emails from Gmail to Outlook using the import API.

    This preserves all email headers including to, from, bcc, replyto, date, etc.

    Args:
        request: Migration request with credentials and options

    Returns:
        Dict with import results
    """
    try:
        # Reset migration state
        # Using global here to update the shared state across requests
        global migration_state
        migration_state = {
            "status": "initializing",
            "total_emails": 0,
            "processed_emails": 0,
            "successful_emails": 0,
            "failed_emails": 0,
            "current_label": "",
            "total_labels": 0,
            "processed_labels": 0,
            "logs": ["Initializing email import..."],
        }

        # Validate credentials
        _validate_credentials(request.credentials)

        # Get Gmail client
        gmail_credentials = request.credentials.gmail.dict()
        gmail_client = GmailClient(credentials=gmail_credentials)

        # Get Outlook client
        outlook_token = request.credentials.destination.token
        outlook_client = OutlookClient(access_token=outlook_token)

        # Create migration service
        migration_service = GmailToOutlookMigrationService(
            gmail_client=gmail_client, outlook_client=outlook_client
        )

        # Set up status update callback
        migration_service.update_status_callback = update_migration_state

        # Start the import process
        await update_migration_state(
            {"status": "running", "logs": "Starting import..."}
        )

        # Run the import
        results = await migration_service.import_all_emails(
            max_emails_per_batch=request.max_emails_per_label
        )

        # Update final status
        await update_migration_state(
            {
                "status": "completed",
                "logs": f"Import completed. Total: {results['total']}, "
                f"Successful: {results['successful']}, Failed: {results['failed']}",
            }
        )

        return {
            "status": "completed",
            "results": results,
        }

    except Exception as e:
        logger.exception("Error during email import")
        await update_migration_state(
            {"status": "failed", "logs": f"Import failed: {str(e)}"}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}",
        ) from e
