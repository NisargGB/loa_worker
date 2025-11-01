"""
Custom exceptions for the LoA Worker system.
"""


class LoAWorkerException(Exception):
    """Base exception for all LoA Worker errors."""
    pass


class MessageProcessingError(LoAWorkerException):
    """Error during message processing."""
    pass


class ClassificationError(MessageProcessingError):
    """Error during message classification."""
    pass


class ExtractionError(MessageProcessingError):
    """Error during entity extraction."""
    pass


class StorageError(LoAWorkerException):
    """Error during storage operations."""
    pass


class CaseNotFoundError(StorageError):
    """Case not found in storage."""
    pass


class InvalidStateTransitionError(LoAWorkerException):
    """Invalid case state transition."""
    pass


class ActionExecutionError(LoAWorkerException):
    """Error during action execution."""
    pass


class LLMServiceError(LoAWorkerException):
    """Error from LLM service."""
    pass


class ChannelError(LoAWorkerException):
    """Error from message channel."""
    pass


class ConfigurationError(LoAWorkerException):
    """Configuration error."""
    pass
