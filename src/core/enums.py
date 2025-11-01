"""
Enums for the LoA Worker system.
"""
from enum import Enum


class SourceType(str, Enum):
    """Message source types."""
    EMAIL = "email"
    TEAMS = "teams"
    TRANSCRIPT = "transcript"
    DOCUMENT = "document"
    UNKNOWN = "unknown"


class MessageCategory(str, Enum):
    """Classification categories for messages."""
    CLIENT_TASK = "CLIENT_TASK"
    LOA_CHASE = "LOA_CHASE"
    LOA_MISSING_INFO = "LOA_MISSING_INFO"
    LOA_RESPONSE = "LOA_RESPONSE"
    ADMIN = "ADMIN"
    IRRELEVANT = "IRRELEVANT"

    def get_description(self) -> str:
        """Human-friendly description for prompting and UI."""
        descriptions = {
            MessageCategory.CLIENT_TASK: (
                "Client or advisor asking us to create/open a case or perform an action "
                "(e.g., start an LoA, open a case, create/complete a task). Not a provider's response."
            ),
            MessageCategory.LOA_CHASE: (
                "Follow-up or status check regarding an LoA (e.g., chasing a provider for updates, "
                "asking when information will arrive)."
            ),
            MessageCategory.LOA_MISSING_INFO: (
                "Provider indicates they cannot proceed and asks for specific missing information "
                "required to process the LoA (e.g., DOB, NI number, plan/policy number)."
            ),
            MessageCategory.LOA_RESPONSE: (
                "Provider supplies requested information or confirms progress relevant to the LoA; "
                "often includes structured details (policy/plan numbers, DOB, provider references) or attachments."
            ),
            MessageCategory.ADMIN: (
                "Administrative/logistical content not requiring case actions (e.g., meeting invites, out-of-office, "
                "newsletters, billing/invoice notices)."
            ),
            MessageCategory.IRRELEVANT: (
                "Spam or content unrelated to clients, cases, or LoA processing."
            ),
        }
        return descriptions.get(self, "Uncategorized message type.")

class ActionType(str, Enum):
    """Types of actions that can be triggered."""
    CREATE_CASE = "CREATE_CASE"
    UPDATE_CASE = "UPDATE_CASE"
    COMPLETE_CASE = "COMPLETE_CASE"
    CANCEL_CASE = "CANCEL_CASE"
    CREATE_TASK = "CREATE_TASK"
    COMPLETE_TASK = "COMPLETE_TASK"
    DRAFT_FOLLOWUP_EMAIL = "DRAFT_FOLLOWUP_EMAIL"
    INITIATE_LOA_CHASE = "INITIATE_LOA_CHASE"
    IGNORE = "IGNORE"


class CaseType(str, Enum):
    """Types of cases."""
    LOA = "loa"
    GENERAL = "general"
    ANNUAL_REVIEW = "annual_review"


class CaseStatus(str, Enum):
    """Case status in the state machine."""
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_INFO = "AWAITING_INFO"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class ProcessingStatus(str, Enum):
    """Status of message processing."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class LLMName(str, Enum):
    """Names of LLMs."""
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
