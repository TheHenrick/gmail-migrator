"""
Gmail labels service for fetching and managing Gmail labels (folders).
"""
import logging
from typing import List, Dict, Any, Optional

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailLabelsService:
    """Service for handling Gmail labels (folders)."""

    def __init__(self, gmail_client):
        """
        Initialize the labels service.
        
        Args:
            gmail_client: An authenticated Gmail client instance
        """
        self.gmail_client = gmail_client
        
    def get_all_labels(self) -> List[Dict[str, Any]]:
        """
        Fetch all labels from the user's Gmail account.
        
        Returns:
            A list of label objects
        """
        try:
            if not self.gmail_client.service:
                self.gmail_client._build_service()
                
            results = self.gmail_client.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            # Sort labels: system labels first, then user labels alphabetically
            system_labels = [label for label in labels if label.get('type') == 'system']
            user_labels = [label for label in labels if label.get('type') == 'user']
            
            # Sort system labels by name for consistency
            system_labels.sort(key=lambda x: x.get('name', ''))
            # Sort user labels alphabetically
            user_labels.sort(key=lambda x: x.get('name', ''))
            
            return system_labels + user_labels
        except HttpError as error:
            logger.error(f"Error fetching labels: {error}")
            return []
            
    def get_label_details(self, label_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific label.
        
        Args:
            label_id: The ID of the label to fetch
            
        Returns:
            Label details or None if not found
        """
        try:
            if not self.gmail_client.service:
                self.gmail_client._build_service()
                
            label = self.gmail_client.service.users().labels().get(userId='me', id=label_id).execute()
            return label
        except HttpError as error:
            logger.error(f"Error fetching label {label_id}: {error}")
            return None
            
    def create_label_map(self) -> Dict[str, str]:
        """
        Create a mapping of label names to IDs for easier reference.
        
        Returns:
            Dictionary mapping label names to their IDs
        """
        labels = self.get_all_labels()
        return {label.get('name'): label.get('id') for label in labels}
        
    def get_nested_labels(self) -> Dict[str, Any]:
        """
        Organize labels into a nested structure based on '/' delimiter in names.
        
        Returns:
            Nested dictionary representing the label hierarchy
        """
        labels = self.get_all_labels()
        root = {'children': {}, 'labels': []}
        
        # First add system labels at the root
        system_labels = [label for label in labels if label.get('type') == 'system']
        root['labels'].extend(system_labels)
        
        # Then organize user labels in a hierarchy
        user_labels = [label for label in labels if label.get('type') == 'user']
        
        for label in user_labels:
            name = label.get('name', '')
            parts = name.split('/')
            
            current = root
            # For nested labels (e.g., "Parent/Child")
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part (leaf node)
                    if part not in current['children']:
                        current['children'][part] = {'children': {}, 'labels': []}
                    current['children'][part]['labels'].append(label)
                else:  # Parent folders
                    if part not in current['children']:
                        current['children'][part] = {'children': {}, 'labels': []}
                    current = current['children'][part]
        
        return root 