"""Service for migrating emails from Gmail to Outlook."""

import logging

# Type checking imports
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


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
        self.update_status_callback: Callable[[dict], Awaitable[None]] | None = None

    async def _update_status(self, update: dict) -> None:
        """
        Update the migration status.

        Args:
            update: The status update
        """
        logger.info(f"Updating migration status with: {update}")
        if self.update_status_callback:
            logger.info("Calling update_status_callback")
            await self.update_status_callback(update)
            logger.info("update_status_callback completed")
        else:
            logger.warning("No update_status_callback set, status update not sent")

    async def migrate_labels_to_folders(self) -> dict[str, str]:
        """
        Migrate Gmail labels to Outlook folders.

        Returns:
            Dict mapping Gmail label IDs to Outlook folder IDs
        """
        # Get all Gmail labels
        gmail_labels = self.labels_service.get_all_labels()
        logger.info(f"Retrieved {len(gmail_labels)} labels from Gmail")

        # Count system and user labels
        system_labels = [
            label for label in gmail_labels if label.get("type") == "system"
        ]
        user_labels = [label for label in gmail_labels if label.get("type") == "user"]
        logger.info(
            f"Found {len(system_labels)} system labels and "
            f"{len(user_labels)} user labels"
        )

        # Get existing Outlook folders to avoid duplicates
        outlook_folders = self.outlook_client.get_folders()
        existing_folder_names = {folder["displayName"] for folder in outlook_folders}
        logger.info(f"Retrieved {len(outlook_folders)} folders from Outlook")

        # Create a mapping of Gmail label IDs to Outlook folder IDs
        folder_mapping: dict[str, str] = {}

        # Process system labels first
        for label in system_labels:
            # Map Gmail system labels to Outlook system folders
            gmail_name = label.get("name", "")
            gmail_id = label.get("id", "")
            logger.info(f"Processing system label: {gmail_id} - {gmail_name}")

            outlook_folder_id = self._map_system_label_to_folder(
                gmail_name, outlook_folders
            )
            if outlook_folder_id:
                folder_mapping[gmail_id] = outlook_folder_id
                logger.info(
                    f"Mapped system label {gmail_name} to Outlook folder ID "
                    f"{outlook_folder_id}"
                )
            else:
                logger.warning(
                    f"Could not map system label {gmail_name} to any Outlook folder"
                )

        # Process user labels (create folders for them)
        for label in user_labels:
            gmail_name = label.get("name", "")
            gmail_id = label.get("id", "")
            logger.info(f"Processing user label: {gmail_id} - {gmail_name}")

            # Skip if folder already exists
            if gmail_name in existing_folder_names:
                # Find the folder ID
                for folder in outlook_folders:
                    if folder["displayName"] == gmail_name:
                        folder_mapping[gmail_id] = folder["id"]
                        logger.info(
                            f"Found existing Outlook folder for {gmail_name}: "
                            f"{folder['id']}"
                        )
                        break
                continue

            # Create new folder
            try:
                logger.info(f"Creating new Outlook folder for label: {gmail_name}")
                new_folder = self.outlook_client.create_folder(name=gmail_name)
                folder_mapping[gmail_id] = new_folder["id"]
                existing_folder_names.add(gmail_name)
                logger.info(
                    f"Created new Outlook folder for {gmail_name}: {new_folder['id']}"
                )
            except Exception:
                logger.exception(f"Failed to create folder for label {gmail_name}")

        logger.info(f"Final folder mapping contains {len(folder_mapping)} entries")
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
        Migrate emails with a specific label from Gmail to Outlook.

        Args:
            label_id: Gmail label ID
            max_emails: Maximum number of emails to migrate

        Returns:
            Migration results
        """
        try:
            # Get the corresponding Outlook folder ID
            outlook_folder_id = self.folder_mapping.get(label_id)

            if not outlook_folder_id:
                # Try to migrate labels first
                logger.warning(
                    f"No Outlook folder found for Gmail label {label_id}. "
                    f"Migrating labels first."
                )
                await self.migrate_labels_to_folders()
                outlook_folder_id = self.folder_mapping.get(label_id)

                if not outlook_folder_id:
                    logger.error(
                        f"Failed to find or create Outlook folder for Gmail label "
                        f"{label_id}"
                    )
                    return {"total": 0, "successful": 0, "failed": 0, "failed_ids": []}

            # Get emails with this label
            try:
                logger.info(f"Getting emails with label {label_id}")
                emails = self.gmail_client.get_emails_with_labels(
                    label_ids=[label_id], max_results=max_emails
                )

                if not emails:
                    logger.info(f"No emails found with label {label_id}")
                    return {"total": 0, "successful": 0, "failed": 0, "failed_ids": []}

                logger.info(f"Found {len(emails)} emails with label {label_id}")

                # Get label name for logging
                label_name = "Unknown"
                try:
                    labels = await self.gmail_client.list_labels()
                    for label in labels:
                        if label.get("id") == label_id:
                            label_name = label.get("name")
                            break
                except Exception as e:
                    logger.warning(f"Could not get label name for {label_id}: {str(e)}")

                # Update status with label info
                if self.update_status_callback:
                    await self.update_status_callback(
                        {
                            "current_label": label_name,
                            "total_emails": len(emails),
                            "logs": (
                                f"Processing label: {label_name} "
                                f"({len(emails)} emails)"
                            ),
                        }
                    )

            except Exception:
                logger.exception("Error in migrate_emails_by_label")
                return {"total": 0, "successful": 0, "failed": 0, "failed_ids": []}

            # Migrate each email
            successful = 0
            failed = 0
            failed_ids = []

            for i, email in enumerate(emails):
                email_id = email.get("id")
                logger.info(f"Processing email {i+1}/{len(emails)} (ID: {email_id})")

                # Update status
                if self.update_status_callback:
                    await self.update_status_callback(
                        {
                            "processed_emails": i,
                            "logs": (
                                f"Processing email {i+1}/{len(emails)} "
                                f"(ID: {email_id})"
                            ),
                        }
                    )

                try:
                    logger.info(
                        f"Migrating email {i+1}/{len(emails)} to Outlook folder"
                    )
                    self.outlook_client.migrate_email(
                        email, email.get("attachments", []), outlook_folder_id
                    )
                    successful += 1
                    logger.info(f"Successfully migrated email {i+1}/{len(emails)}")

                    # Update status with progress
                    if self.update_status_callback:
                        percent = round((i + 1) / len(emails) * 100, 1)
                        await self.update_status_callback(
                            {
                                "processed_emails": i + 1,
                                "successful_emails": successful,
                                "failed_emails": failed,
                                "logs": (
                                    f"Label {label_name} progress: {percent}% "
                                    f"({i+1}/{len(emails)} emails processed)"
                                ),
                            }
                        )

                except Exception as e:
                    logger.exception(f"Failed to migrate email {email_id}")
                    failed += 1
                    failed_ids.append(email_id)

                    # Update status with failure
                    if self.update_status_callback:
                        await self.update_status_callback(
                            {
                                "processed_emails": i + 1,
                                "successful_emails": successful,
                                "failed_emails": failed,
                                "logs": (
                                    f"Failed to migrate email {i+1}/{len(emails)}: "
                                    f"{str(e)}"
                                ),
                            }
                        )

            # Return results
            return {
                "total": len(emails),
                "successful": successful,
                "failed": failed,
                "failed_ids": failed_ids,
            }

        except Exception:
            logger.exception("Error in migrate_emails_by_label")
            return {"total": 0, "successful": 0, "failed": 0, "failed_ids": []}

    async def migrate_all_emails(
        self, max_emails_per_label: int = 100
    ) -> dict[str, Any]:
        """
        Migrate all emails from Gmail to Outlook.

        Args:
            max_emails_per_label: Maximum number of emails to migrate per label

        Returns:
            Migration results
        """
        # Get all Gmail labels
        gmail_labels = self.labels_service.get_all_labels()

        # Update status with total labels
        await self._update_status(
            {"total_labels": len(gmail_labels), "processed_labels": 0}
        )

        # First, ensure we have a mapping of Gmail labels to Outlook folders
        if not self.folder_mapping:
            logger.info("No folder mapping found, creating it first")
            await self._update_status({"logs": "Creating folder mapping..."})
            self.folder_mapping = await self.migrate_labels_to_folders()

        logger.info(f"Final folder mapping contains {len(self.folder_mapping)} entries")

        # Migrate emails for each label
        results = {
            "total": 0,
            "successful": 0,
            "failed": 0,
            "failed_ids": [],
            "label_results": {},
        }

        # Process each label
        for i, label in enumerate(gmail_labels):
            label_id = label.get("id")
            label_name = label.get("name", "Unknown")

            if not label_id:
                logger.warning(f"Label {label_name} has no ID, skipping")
                continue

            logger.info(
                f"Processing label {i+1}/{len(gmail_labels)}: {label_name} "
                f"(ID: {label_id})"
            )

            # Update status
            await self._update_status(
                {
                    "current_label": label_name,
                    "processed_labels": i,
                    "logs": (
                        f"Processing label {i+1}/{len(gmail_labels)}: " f"{label_name}"
                    ),
                }
            )

            # Migrate emails for this label
            label_results = await self.migrate_emails_by_label(
                label_id, max_emails_per_label
            )

            # Update overall results
            results["total"] += label_results.get("total", 0)
            results["successful"] += label_results.get("successful", 0)
            results["failed"] += label_results.get("failed", 0)
            results["failed_ids"].extend(label_results.get("failed_ids", []))
            results["label_results"][label_id] = label_results

            # Update status with progress
            progress_percent = (i + 1) / len(gmail_labels) * 100
            logger.info(
                f"Migration progress: {progress_percent:.1f}% "
                f"({i+1}/{len(gmail_labels)} labels processed)"
            )

            await self._update_status(
                {
                    "processed_labels": i + 1,
                    "total_emails": results["total"],
                    "successful_emails": results["successful"],
                    "failed_emails": results["failed"],
                    "logs": (
                        f"Migration progress: {progress_percent:.1f}% "
                        f"({i+1}/{len(gmail_labels)} labels processed)"
                    ),
                }
            )

        logger.info(
            f"Email migration completed. Results: {results['successful']}/"
            f"{results['total']} emails migrated successfully across "
            f"{len(gmail_labels)} labels"
        )

        # Final status update
        await self._update_status(
            {
                "processed_labels": len(gmail_labels),
                "logs": (
                    f"Email migration completed. Results: {results['successful']}/"
                    f"{results['total']} emails migrated successfully across "
                    f"{len(gmail_labels)} labels"
                ),
            }
        )

        return results
