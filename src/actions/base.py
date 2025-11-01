"""
Base action handler interface.
"""
from abc import ABC, abstractmethod
from typing import Optional

from core.models import Action, AuditLog
from storage.audit_repository import AuditRepository
from storage.case_repository import CaseRepository


class ActionHandler(ABC):
    """Abstract base class for all action handlers."""

    def __init__(
        self,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
    ):
        """
        Initialize the action handler.

        Args:
            case_repo: Case repository
            audit_repo: Audit repository
        """
        self.case_repo = case_repo
        self.audit_repo = audit_repo

    @abstractmethod
    async def execute(self, action: Action) -> bool:
        """
        Execute the action.

        Args:
            action: Action to execute

        Returns:
            True if successful, False otherwise
        """
        pass

    async def log_action(
        self,
        action: Action,
        success: bool,
        before_state: dict,
        after_state: dict,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Log action to audit trail.

        Args:
            action: The action that was executed
            success: Whether action succeeded
            before_state: State before action
            after_state: State after action
            error_message: Error message if failed
        """
        audit_log = AuditLog(
            case_id=action.case_id or "unknown",
            action_type=action.type,
            before_state=before_state,
            after_state=after_state,
            triggered_by=action.triggered_by,
            success=success,
            error_message=error_message,
            metadata={"action_id": action.id},
        )

        await self.audit_repo.log_action(audit_log)
