"""
Base channel abstraction for message ingestion.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from ..core.models import Message


class BaseChannel(ABC):
    """Abstract base class for all message channels."""

    def __init__(self, name: str):
        """
        Initialize the channel.

        Args:
            name: Unique name for this channel instance
        """
        self.name = name

    @abstractmethod
    async def connect(self) -> None:
        """
        Connect to the message source.
        Establish any necessary connections or authentication.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the message source.
        Clean up any resources.
        """
        pass

    @abstractmethod
    async def fetch_messages(
        self,
        limit: Optional[int] = None,
        since: Optional[str] = None,
    ) -> AsyncIterator[Message]:
        """
        Fetch messages from the channel.

        Args:
            limit: Maximum number of messages to fetch
            since: Fetch messages since this identifier (implementation-specific)

        Yields:
            Message objects
        """
        pass

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
