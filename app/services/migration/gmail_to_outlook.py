"""Service for migrating emails from Gmail to Outlook."""

import logging
from typing import Any

from app.services.gmail.client import GmailClient
from app.services.gmail.labels import GmailLabelsService
from app.services.outlook.client import OutlookClient

logger = logging.getLogger(__name__)


class GmailToOutlookMigrationService:
    """Service for migrating emails from Gmail to Outlook."""

    def __init__(
        self, gmail_client: GmailClient, outlook_client: OutlookClient
    ) -> None:
        """
        Initialize the migration service.

        Args:
            gmail_client: Authenticated Gmail client
            outlook_client: Authenticated Outlook client
        """
        self.gmail_client = gmail_client
        self.outlook_client = outlook_client
        self.labels_service = GmailLabelsService(gmail_client)
        self.folder_mapping: dict[str, str] = {}  # Gmail label ID -> Outlook folder ID

    async def migrate_labels_to_folders(self) -> dict[str, str]:
        """
        Migrate Gmail labels to Outlook folders.

        Returns:
            Dict mapping Gmail label IDs to Outlook folder IDs
        """
        # Get all Gmail labels
        gmail_labels = self.labels_service.get_all_labels()

        # Get existing Outlook folders to avoid duplicates
        outlook_folders = self.outlook_client.get_folders()
        existing_folder_names = {folder["displayName"] for folder in outlook_folders}

        # Create a mapping of Gmail label IDs to Outlook folder IDs
        folder_mapping: dict[str, str] = {}

        # Process system labels first
        for label in gmail_labels:
            if label.get("type") == "system":
                # Map Gmail system labels to Outlook system folders
                gmail_name = label.get("name", "")
                outlook_folder_id = self._map_system_label_to_folder(
                    gmail_name, outlook_folders
                )
                if outlook_folder_id:
                    folder_mapping[label["id"]] = outlook_folder_id

        # Process user labels (create folders for them)
        for label in gmail_labels:
            if label.get("type") == "user":
                gmail_name = label.get("name", "")

                # Skip if folder already exists
                if gmail_name in existing_folder_names:
                    # Find the folder ID
                    for folder in outlook_folders:
                        if folder["displayName"] == gmail_name:
                            folder_mapping[label["id"]] = folder["id"]
                            break
                    continue

                # Create new folder
                try:
                    new_folder = self.outlook_client.create_folder(name=gmail_name)
                    folder_mapping[label["id"]] = new_folder["id"]
                    existing_folder_names.add(gmail_name)
                except Exception:
                    logger.exception(f"Failed to create folder for label {gmail_name}")

        self.folder_mapping = folder_mapping
        return folder_mapping

    def _map_system_label_to_folder(
        self, gmail_label: str, outlook_folders: list[dict[str, Any]]
    ) -> str | None:
        """
        Map Gmail system labels to Outlook system folders.

        Args:
            gmail_label: Gmail system label name
            outlook_folders: List of Outlook folders

        Returns:
            Outlook folder ID or None if no mapping found
        """
        # Define mapping of Gmail system labels to Outlook folder names
        system_mapping = {
            "INBOX": "Inbox",
            "SENT": "Sent Items",
            "DRAFT": "Drafts",
            "TRASH": "Deleted Items",
            "SPAM": "Junk Email",
            "IMPORTANT": "Important",
            "STARRED": "Favorites",
        }

        outlook_name = system_mapping.get(gmail_label)
        if not outlook_name:
            return None

        # Find the Outlook folder ID
        for folder in outlook_folders:
            if folder["displayName"] == outlook_name:
                return folder["id"]

        return None

    async def migrate_emails_by_label(
        self, label_id: str, max_emails: int = 100
    ) -> dict[str, Any]:
        """
        Migrate emails from a specific Gmail label to the corresponding Outlook folder.

        Args:
            label_id: Gmail label ID
            max_emails: Maximum number of emails to migrate

        Returns:
            Migration results
        """
        # Get the corresponding Outlook folder ID
        folder_id = self.folder_mapping.get(label_id)
        if not folder_id:
            # If folder mapping doesn't exist, create it
            await self.migrate_labels_to_folders()
            folder_id = self.folder_mapping.get(label_id)
            if not folder_id:
                logger.exception(f"No Outlook folder found for Gmail label {label_id}")
                return {
                    "success": False,
                    "error": f"No Outlook folder found for Gmail label {label_id}",
                }

        # Get emails with the specified label
        try:
            emails = self.gmail_client.get_emails_with_labels(
                label_ids=[label_id], max_results=max_emails
            )
        except Exception:
            logger.exception(f"Failed to get emails with label {label_id}")
            return {
                "success": False,
                "error": f"Failed to get emails with label {label_id}",
            }

        # Migrate each email
        results = {
            "total": len(emails),
            "successful": 0,
            "failed": 0,
            "failed_ids": [],
        }

        for email in emails:
            try:
                # Get full email content
                email_id = email.get("id")
                if not email_id:
                    results["failed"] += 1
                    continue

                gmail_email = self.gmail_client.get_email_content(email_id)

                # Get attachments
                attachments = []
                if gmail_email.get("has_attachments", False):
                    for attachment in gmail_email.get("attachments", []):
                        attachment_data = self.gmail_client.get_attachment(
                            email_id, attachment["id"]
                        )
                        if attachment_data:
                            attachments.append(
                                {
                                    "name": attachment.get(
                                        "filename", "attachment.dat"
                                    ),
                                    "content": attachment_data,
                                    "contentType": attachment.get("mime_type"),
                                }
                            )

                # Migrate to Outlook
                self.outlook_client.migrate_email(
                    gmail_message=gmail_email,
                    attachments=attachments,
                    folder_id=folder_id,
                )

                results["successful"] += 1

            except Exception:
                email_id = email.get("id", "unknown")
                logger.exception(f"Failed to migrate email {email_id}")
                results["failed"] += 1
                results["failed_ids"].append(email.get("id"))

        return results

    async def migrate_all_emails(
        self, max_emails_per_label: int = 100
    ) -> dict[str, Any]:
        """
        Migrate all emails from Gmail to Outlook, preserving label structure.

        Args:
            max_emails_per_label: Maximum number of emails to migrate per label

        Returns:
            Migration results
        """
        # First, migrate labels to folders
        await self.migrate_labels_to_folders()

        # Get all Gmail labels
        gmail_labels = self.labels_service.get_all_labels()

        # Migrate emails for each label
        overall_results = {
            "total_labels": len(gmail_labels),
            "processed_labels": 0,
            "total_emails": 0,
            "successful_emails": 0,
            "failed_emails": 0,
            "label_results": {},
        }

        for label in gmail_labels:
            label_id = label.get("id")
            label_name = label.get("name")

            if not label_id:
                continue

            # Migrate emails for this label
            label_results = await self.migrate_emails_by_label(
                label_id, max_emails=max_emails_per_label
            )

            # Update overall results
            overall_results["processed_labels"] += 1
            overall_results["total_emails"] += label_results.get("total", 0)
            overall_results["successful_emails"] += label_results.get("successful", 0)
            overall_results["failed_emails"] += label_results.get("failed", 0)
            overall_results["label_results"][label_name] = label_results

        return overall_results
