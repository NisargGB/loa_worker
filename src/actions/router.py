"""
Action router for dispatching actions to appropriate handlers.
"""
from typing import Dict, Type, Optional
from .base import ActionHandler
from .case_actions import CaseActionHandler
from .task_actions import TaskActionHandler
from .followup_actions import FollowupActionHandler
from ..core.models import Action
from ..core.enums import ActionType
from ..core.exceptions import ActionExecutionError
from ..storage.case_repository import CaseRepository
from ..storage.audit_repository import AuditRepository
from ..llm.service import LLMService


class ActionRouter:
    """Routes actions to appropriate handlers."""

    # Map action types to handler classes
    ACTION_TYPE_TO_HANDLER: Dict[ActionType, Type[ActionHandler]] = {
        ActionType.CREATE_CASE: CaseActionHandler,
        ActionType.UPDATE_CASE: CaseActionHandler,
        ActionType.COMPLETE_CASE: CaseActionHandler,
        ActionType.CANCEL_CASE: CaseActionHandler,
        ActionType.CREATE_TASK: TaskActionHandler,
        ActionType.COMPLETE_TASK: TaskActionHandler,
        ActionType.DRAFT_FOLLOWUP_EMAIL: FollowupActionHandler,
        ActionType.INITIATE_LOA_CHASE: FollowupActionHandler,
    }

    def __init__(
        self,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
        llm_service: Optional[LLMService] = None,
    ):
        """
        Initialize the router.

        Args:
            case_repo: Case repository
            audit_repo: Audit repository
            llm_service: Optional LLM service
        """
        self.case_repo = case_repo
        self.audit_repo = audit_repo
        self.llm_service = llm_service

        # Initialize handler instances
        self.handlers: Dict[Type[ActionHandler], ActionHandler] = {
            CaseActionHandler: CaseActionHandler(case_repo, audit_repo),
            TaskActionHandler: TaskActionHandler(case_repo, audit_repo),
            FollowupActionHandler: FollowupActionHandler(case_repo, audit_repo, llm_service),
        }

    async def route_action(self, action: Action) -> bool:
        """
        Route an action to the appropriate handler.

        Args:
            action: Action to execute

        Returns:
            True if successful

        Raises:
            ActionExecutionError: If action type unsupported or execution fails
        """
        # Handle IGNORE action
        if action.type == ActionType.IGNORE:
            return True  # No-op

        # Get handler class for this action type
        handler_class = self.ACTION_TYPE_TO_HANDLER.get(action.type)

        if not handler_class:
            raise ActionExecutionError(f"No handler for action type: {action.type}")

        # Get handler instance
        handler = self.handlers.get(handler_class)

        if not handler:
            raise ActionExecutionError(f"Handler not initialized: {handler_class}")

        # Execute action
        return await handler.execute(action)

    async def route_actions(self, actions: list[Action]) -> Dict[str, bool]:
        """
        Route multiple actions.

        Args:
            actions: List of actions to execute

        Returns:
            Dictionary mapping action IDs to success status
        """
        results = {}

        for action in actions:
            try:
                success = await self.route_action(action)
                results[action.id] = success
            except Exception as e:
                print(f"Error executing action {action.id}: {e}")
                results[action.id] = False

        return results
