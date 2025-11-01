"""
Dummy channel that reads from JSON dataset for testing.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional

from channels.base import BaseChannel
from core.enums import ProcessingStatus, SourceType
from core.models import (DocumentContent, EmailContent, Message,
                         TeamsChatMessage, TeamsContent, TranscriptContent,
                         TranscriptTurn)


class DummyChannel(BaseChannel):
    """Channel that reads messages from a JSON file."""

    def __init__(self, file_path: str, name: str = "dummy"):
        """
        Initialize the dummy channel.

        Args:
            file_path: Path to JSON file containing test messages
            name: Channel name
        """
        super().__init__(name)
        self.file_path = Path(file_path)
        self.messages: List[Dict[str, Any]] = []
        self._connected = False

    async def connect(self) -> None:
        """Load messages from JSON file."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.file_path}")

        with open(self.file_path, 'r') as f:
            self.messages = json.load(f)

        self._connected = True

    async def disconnect(self) -> None:
        """Clean up resources."""
        self.messages = []
        self._connected = False

    async def fetch_messages(
        self,
        limit: Optional[int] = None,
        since: Optional[str] = None,
        day: Optional[int] = None,
    ) -> AsyncIterator[Message]:
        """
        Fetch messages from the loaded dataset.

        Args:
            limit: Maximum number of messages to fetch
            since: Fetch messages with ID greater than this
            day: Filter messages by day number

        Yields:
            Normalized Message objects
        """
        if not self._connected:
            raise RuntimeError("Channel not connected. Call connect() first.")

        count = 0
        start_yielding = since is None

        for raw_msg in self.messages:
            # Filter by day if specified
            if day is not None and raw_msg.get("day") != day:
                continue

            # Skip until we reach the 'since' message
            if not start_yielding:
                if raw_msg["id"] == since:
                    start_yielding = True
                continue

            # Check limit
            if limit is not None and count >= limit:
                break

            # Convert to normalized Message
            message = self._parse_message(raw_msg)
            yield message

            count += 1

    def _parse_message(self, raw_msg: Dict[str, Any]) -> Message:
        """
        Parse raw JSON message into normalized Message model.

        Args:
            raw_msg: Raw message dictionary from JSON

        Returns:
            Normalized Message object
        """
        msg_id = raw_msg["id"]
        source_type = SourceType(raw_msg["source_type"])

        # Parse timestamp
        timestamp = self._parse_timestamp(
            raw_msg.get("day", 1),
            raw_msg.get("time", "00:00")
        )

        # Parse content based on source type
        if source_type == SourceType.EMAIL:
            content = EmailContent(
                from_address=raw_msg.get("from_address", ""),
                to_address=raw_msg.get("to_address", ""),
                subject=raw_msg.get("subject", ""),
                body=raw_msg.get("body", ""),
            )
        elif source_type == SourceType.TEAMS:
            chat_msgs = [
                TeamsChatMessage(author=msg["author"], text=msg["text"])
                for msg in raw_msg.get("chat_messages", [])
            ]
            content = TeamsContent(chat_messages=chat_msgs)
        elif source_type == SourceType.TRANSCRIPT:
            turns = [
                TranscriptTurn(speaker=turn["speaker"], text=turn["text"])
                for turn in raw_msg.get("transcript_turns", [])
            ]
            content = TranscriptContent(transcript_turns=turns)
        elif source_type == SourceType.DOCUMENT:
            content = DocumentContent(
                document_title=raw_msg.get("document_title", ""),
                document_text=raw_msg.get("document_text", ""),
            )
        else:
            raise ValueError(f"Unknown source type: {source_type}")

        # Store expected values in metadata for testing/validation
        metadata = {
            "description": raw_msg.get("description", ""),
            "expected_category": raw_msg.get("expected_category"),
            "expected_action": raw_msg.get("expected_action"),
            "expected_client_name": raw_msg.get("expected_client_name"),
            "expected_case_title": raw_msg.get("expected_case_title"),
            "expected_case_type": raw_msg.get("expected_case_type"),
            "expected_required_fields": raw_msg.get("expected_required_fields"),
            "expected_updated_contains": raw_msg.get("expected_updated_contains"),
            "expected_missing_contains": raw_msg.get("expected_missing_contains"),
            "expected_task_title": raw_msg.get("expected_task_title"),
            "expected_task_description": raw_msg.get("expected_task_description"),
        }

        return Message(
            id=msg_id,
            timestamp=timestamp,
            source_type=source_type,
            content=content,
            metadata=metadata,
            processing_status=ProcessingStatus.PENDING,
        )

    @staticmethod
    def _parse_timestamp(day: int, time_str: str) -> datetime:
        """
        Convert day number and time string to datetime.

        Args:
            day: Day number (1, 2, 3, etc.)
            time_str: Time string in HH:MM format

        Returns:
            datetime object
        """
        # Use a base date and add days
        base_date = datetime(2024, 1, 1)
        hour, minute = map(int, time_str.split(":"))

        return datetime(
            year=base_date.year,
            month=base_date.month,
            day=base_date.day + (day - 1),
            hour=hour,
            minute=minute,
        )
