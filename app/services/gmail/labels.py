"""Service for managing Gmail labels and folders."""

import logging
from typing import Any, Protocol

from googleapiclient.discovery import Resource

logger = logging.getLogger(__name__)


class GmailClientProtocol(Protocol):
    """Protocol for GmailClient to avoid circular imports."""

    service: Resource | None


class GmailLabelsService:
    """Service for handling Gmail labels (folders)."""

    def __init__(self, gmail_client: GmailClientProtocol) -> None:
        """
        Initialize the labels service.

        Args:
            gmail_client: Gmail client instance with API service
        """
        self.gmail_client = gmail_client
        self.service = gmail_client.service
        self._all_labels_cache = None

    def _ensure_service(self) -> None:
        """Ensure the service is available and up-to-date."""
        if not self.service:
            self.service = self.gmail_client.service

    def get_all_labels(self) -> list[dict[str, Any]]:
        """
        Get all available labels from Gmail.

        Returns:
            List of label objects with id, name, and type
        """
        if self._all_labels_cache:
            return self._all_labels_cache

        self._ensure_service()
        if not self.service:
            logger.error("Gmail service not available")
            return []

        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels = response.get("labels", [])

            # Transform into a simpler format
            transformed_labels = []
            for label in labels:
                label_type = "system"
                if label["type"] == "user":
                    label_type = "custom"

                transformed_labels.append(
                    {
                        "id": label["id"],
                        "name": label["name"],
                        "type": label_type,
                    }
                )

            # Cache results for future use
            self._all_labels_cache = transformed_labels

            return transformed_labels
        except Exception:
            logger.exception("Error fetching Gmail labels")
            return []

    def get_label_details(self, label_id: str) -> dict[str, Any] | None:
        """
        Get details of a specific label.

        Args:
            label_id: Gmail label ID

        Returns:
            Label details or None if not found
        """
        self._ensure_service()
        if not self.service:
            logger.error("Gmail service not available")
            return None

        try:
            return self.service.users().labels().get(userId="me", id=label_id).execute()
        except Exception:
            logger.exception(f"Error fetching label details for {label_id}")
            return None

    def create_label_map(self) -> dict[str, str]:
        """
        Create a mapping of label names to IDs.

        Returns:
            Dictionary mapping label names to IDs
        """
        labels = self.get_all_labels()
        return {label["name"]: label["id"] for label in labels}

    def get_nested_labels(self) -> dict[str, Any]:
        """
        Create a nested structure of labels based on their paths.

        Returns:
            Nested dictionary structure representing the label hierarchy
        """
        labels = self.get_all_labels()
        nested = {"": {"children": {}, "type": "folder"}}

        for label in labels:
            # Skip system labels for nesting
            if label["type"] == "system":
                continue

            name = label["name"]
            # Skip labels without path separators
            if "/" not in name:
                nested[""]["children"][name] = {
                    "id": label["id"],
                    "type": "label",
                    "children": {},
                }
                continue

            # Process nested path
            parts = name.split("/")
            parent_path = ""

            for i, part in enumerate(parts):
                # Use ternary operator for path construction
                parent_path = part if i == 0 else f"{parent_path}/{part}"

                if i < len(parts) - 1:
                    # This is a folder in the path
                    current = nested
                    path_parts = parent_path.split("/")

                    # Navigate to the correct place in the nested dict
                    for pp in path_parts:
                        if pp == "":
                            continue

                        if pp not in current["children"]:
                            current["children"][pp] = {
                                "children": {},
                                "type": "folder",
                            }

                        current = current["children"][pp]
                else:
                    # This is the final label
                    current = nested
                    path_parts = parent_path.split("/")

                    # Navigate to the parent folder
                    for j, pp in enumerate(path_parts):
                        if pp == "":
                            continue

                        if j == len(path_parts) - 1:
                            # Last part is the label itself
                            current["children"][pp] = {
                                "id": label["id"],
                                "type": "label",
                                "children": {},
                            }
                        else:
                            if pp not in current["children"]:
                                current["children"][pp] = {
                                    "children": {},
                                    "type": "folder",
                                }

                            current = current["children"][pp]

        return nested
