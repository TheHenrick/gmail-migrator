"""Router for email migration API endpoints."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import get_gmail_client, get_outlook_client
from app.services.gmail.client import GmailClient
from app.services.migration.gmail_to_outlook import GmailToOutlookMigrationService
from app.services.outlook.client import OutlookClient

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/migration", tags=["migration"])


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


class LabelMigrationRequest(BaseModel):
    """Request model for migrating emails by label."""

    label_id: str = Field(..., description="Gmail label ID")
    max_emails: int = Field(
        100, description="Maximum number of emails to migrate", ge=1, le=1000
    )


class FullMigrationRequest(BaseModel):
    """Request model for full migration."""

    max_emails_per_label: int = Field(
        100,
        description="Maximum number of emails to migrate per label",
        ge=1,
        le=1000,
    )


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


@router.post("/gmail-to-outlook/labels", response_model=dict[str, str])
async def migrate_labels_to_folders(
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
) -> dict[str, str]:
    """
    Migrate Gmail labels to Outlook folders.

    Args:
        gmail_client: Gmail client instance
        outlook_client: Outlook client instance

    Returns:
        Dict mapping Gmail label IDs to Outlook folder IDs
    """
    try:
        migration_service = GmailToOutlookMigrationService(gmail_client, outlook_client)
        return await migration_service.migrate_labels_to_folders()
    except Exception as e:
        logger.exception("Error migrating labels to folders")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error migrating labels to folders: {str(e)}",
        ) from e


@router.post("/gmail-to-outlook/by-label", response_model=MigrationResultsResponse)
async def migrate_emails_by_label(
    request: LabelMigrationRequest,
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
) -> dict[str, Any]:
    """
    Migrate emails from a specific Gmail label to the corresponding Outlook folder.

    Args:
        request: Migration request parameters
        gmail_client: Gmail client instance
        outlook_client: Outlook client instance

    Returns:
        Migration results
    """
    try:
        migration_service = GmailToOutlookMigrationService(gmail_client, outlook_client)
        results = await migration_service.migrate_emails_by_label(
            request.label_id, request.max_emails
        )

        # Handle error case
        if not results.get("success", True):
            error_msg = results.get("error", "Unknown error during migration")
            _raise_bad_request(error_msg)

        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error migrating emails by label")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error migrating emails by label: {str(e)}",
        ) from e


@router.post("/gmail-to-outlook/all", response_model=dict[str, Any])
async def migrate_all_emails(
    request: FullMigrationRequest,
    gmail_client: Annotated[GmailClient, Depends(get_gmail_client)],
    outlook_client: Annotated[OutlookClient, Depends(get_outlook_client)],
) -> dict[str, Any]:
    """
    Migrate all emails from Gmail to Outlook, preserving label structure.

    Args:
        request: Migration request parameters
        gmail_client: Gmail client instance
        outlook_client: Outlook client instance

    Returns:
        Migration results
    """
    try:
        migration_service = GmailToOutlookMigrationService(gmail_client, outlook_client)
        return await migration_service.migrate_all_emails(request.max_emails_per_label)
    except Exception as e:
        logger.exception("Error migrating all emails")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error migrating all emails: {str(e)}",
        ) from e
