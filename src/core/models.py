"""
Core data models for the LoA Worker system.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from core.enums import (ActionType, CaseStatus, CaseType, MessageCategory,
                        ProcessingStatus, SourceType)

# Message Content Models

class EmailContent(BaseModel):
    """Email message content."""
    from_address: str
    to_address: str
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: List[str] = Field(default_factory=list)


class TeamsChatMessage(BaseModel):
    """Single Teams chat message."""
    author: str
    text: str
    timestamp: Optional[datetime] = None


class TeamsContent(BaseModel):
    """Teams chat content."""
    chat_messages: List[TeamsChatMessage]
    thread_id: Optional[str] = None


class TranscriptTurn(BaseModel):
    """Single turn in a transcript."""
    speaker: str
    text: str
    timestamp: Optional[float] = None


class TranscriptContent(BaseModel):
    """Transcript content."""
    transcript_turns: List[TranscriptTurn]
    call_id: Optional[str] = None
    duration: Optional[int] = None


class DocumentContent(BaseModel):
    """Document content."""
    document_title: str
    document_text: str
    document_type: Optional[str] = None
    page_count: Optional[int] = None


MessageContent = Union[EmailContent, TeamsContent, TranscriptContent, DocumentContent]


# Core Message Model

class Message(BaseModel):
    """Normalized message from any channel."""
    id: str
    timestamp: datetime
    source_type: SourceType
    content: MessageContent
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_status: ProcessingStatus = ProcessingStatus.PENDING

    def get_text_content(self) -> str:
        """Extract text content from message."""
        if isinstance(self.content, EmailContent):
            return f"{self.content.subject}\n{self.content.body}"
        elif isinstance(self.content, TeamsContent):
            return "\n".join([f"{msg.author}: {msg.text}" for msg in self.content.chat_messages])
        elif isinstance(self.content, TranscriptContent):
            return "\n".join([f"{turn.speaker}: {turn.text}" for turn in self.content.transcript_turns])
        elif isinstance(self.content, DocumentContent):
            return f"{self.content.document_title}\n{self.content.document_text}"
        return ""


# Classification and Extraction Models

class Classification(BaseModel):
    """Result of message classification."""
    category: MessageCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    is_relevant: bool = True

    @property
    def should_process(self) -> bool:
        """Determine if message should be processed further."""
        return self.is_relevant and self.category != MessageCategory.IRRELEVANT


class ExtractedEntities(BaseModel):
    """Entities extracted from message."""
    client_name: Optional[str] = None
    case_id: Optional[str] = None
    case_title: Optional[str] = None
    field_updates: Dict[str, str] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    additional_context: Dict[str, Any] = Field(default_factory=dict)


# Action Models

class Action(BaseModel):
    """Action to be executed."""
    id: str = Field(default_factory=lambda: f"action_{datetime.utcnow().timestamp()}")
    type: ActionType
    case_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: str  # message_id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None


# Case Models

class FieldValue(BaseModel):
    """Individual field value within a case."""
    field_name: str
    value: str
    received_at: datetime
    source_message_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Case(BaseModel):
    """Represents a client case."""
    id: str
    client_name: str
    case_title: str
    case_type: CaseType
    status: CaseStatus = CaseStatus.OPEN
    required_fields: List[str] = Field(default_factory=list)
    received_fields: Dict[str, FieldValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    notes: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_complete(self) -> bool:
        """Check if case is complete based on required fields."""
        if self.case_type != CaseType.LOA:
            return self.status == CaseStatus.COMPLETE

        required = set(self.required_fields)
        received = set(self.received_fields.keys())
        return required.issubset(received)

    def get_missing_fields(self) -> List[str]:
        """Get list of missing required fields."""
        required = set(self.required_fields)
        received = set(self.received_fields.keys())
        return list(required - received)

    def get_completion_percentage(self) -> float:
        """Get percentage of required fields received."""
        if not self.required_fields:
            return 100.0
        received_count = len([f for f in self.required_fields if f in self.received_fields])
        return (received_count / len(self.required_fields)) * 100


class Task(BaseModel):
    """Individual task within a case or standalone."""
    id: str
    case_id: Optional[str] = None
    title: str
    description: str
    status: CaseStatus = CaseStatus.OPEN
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    due_date: Optional[datetime] = None


# Audit Models

class AuditLog(BaseModel):
    """Immutable audit trail entry."""
    id: str = Field(default_factory=lambda: f"audit_{datetime.utcnow().timestamp()}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    case_id: str
    action_type: ActionType
    before_state: Dict[str, Any] = Field(default_factory=dict)
    after_state: Dict[str, Any] = Field(default_factory=dict)
    triggered_by: str  # message_id or user_id
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Processing Result Models

class ProcessingResult(BaseModel):
    """Result of processing a single message."""
    message_id: str
    success: bool
    classification: Optional[Classification] = None
    extracted_entities: Optional[ExtractedEntities] = None
    actions_taken: List[Action] = Field(default_factory=list)
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None


class BatchProcessingResult(BaseModel):
    """Result of processing a batch of messages."""
    total_messages: int
    processed: int
    failed: int
    skipped: int
    results: List[ProcessingResult] = Field(default_factory=list)
    total_time_ms: float

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_messages == 0:
            return 0.0
        return (self.processed / self.total_messages) * 100


class LLMChunk(BaseModel):
    text: str = Field(default=None)
    thought_signature: str = Field(default=None)
    thought: str = Field(default=None)
    tool_call_id: str = Field(default=None)
    tool_call_name: str = Field(default=None)
    tool_call_args: str = Field(default=None)
    index: int = Field(default=None)


class LLMToolParam(BaseModel):
    name: str
    description: str
    type: Union[str, dict]
    required: bool = Field(default=True)


class LLMToolResponse(BaseModel):
    is_terminal: bool = Field(default=False)
    text: str = Field(default=None)


class LLMUsage(BaseModel):
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    cache_read_tokens: int = Field(default=0)
    cache_write_tokens: int = Field(default=0)
