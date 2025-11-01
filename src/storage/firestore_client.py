"""
Firestore client wrapper.
"""
from dotenv import load_dotenv

load_dotenv()
import os
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore import AsyncClient

from core.exceptions import ConfigurationError


class FirestoreClient:
    """Wrapper for Firestore client with connection management."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        """
        Initialize Firestore client.

        Args:
            project_id: GCP project ID (defaults to env var FIRESTORE_PROJECT_ID)
            credentials_path: Path to service account credentials
                             (defaults to env var GOOGLE_APPLICATION_CREDENTIALS)
        """
        self.project_id = project_id or os.getenv("FIRESTORE_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not self.project_id:
            raise ConfigurationError(
                "Firestore project ID not provided. "
                "Set FIRESTORE_PROJECT_ID environment variable or pass project_id parameter."
            )

        self._client: Optional[AsyncClient] = None

    async def connect(self) -> AsyncClient:
        """
        Get or create Firestore async client.

        Returns:
            Firestore async client
        """
        if self._client is None:
            # Set credentials path if provided
            if self.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path

            self._client = firestore.AsyncClient(project=self.project_id)

        return self._client

    async def disconnect(self) -> None:
        """Close Firestore client connection."""
        if self._client:
            self._client.close()
            self._client = None

    @property
    def client(self) -> AsyncClient:
        """
        Get the Firestore client.
        Note: Call connect() first to ensure client is initialized.

        Returns:
            Firestore async client

        Raises:
            RuntimeError: If client not connected
        """
        if self._client is None:
            raise RuntimeError("Firestore client not connected. Call connect() first.")
        return self._client

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
