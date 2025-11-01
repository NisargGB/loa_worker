"""
Action handlers for case-related actions.
"""
from datetime import datetime
from typing import Optional
from .base import ActionHandler
from ..core.models import Action, Case, FieldValue
from ..core.enums import ActionType, CaseType, CaseStatus
from ..core.exceptions import ActionExecutionError
from ..state.case_state import CaseStateMachine
from ..state.field_tracker import FieldTracker


class CaseActionHandler(ActionHandler):
    """Handles case-related actions (CREATE, UPDATE, COMPLETE, CANCEL)."""

    async def execute(self, action: Action) -> bool:
        """
        Execute case action.

        Args:
            action: Action to execute

        Returns:
            True if successful

        Raises:
            ActionExecutionError: If execution fails
        """
        if action.type == ActionType.CREATE_CASE:
            return await self._create_case(action)
        elif action.type == ActionType.UPDATE_CASE:
            return await self._update_case(action)
        elif action.type == ActionType.COMPLETE_CASE:
            return await self._complete_case(action)
        elif action.type == ActionType.CANCEL_CASE:
            return await self._cancel_case(action)
        else:
            raise ActionExecutionError(f"Unsupported action type: {action.type}")

    async def _create_case(self, action: Action) -> bool:
        """Create a new case."""
        try:
            params = action.parameters

            # Generate case ID
            case_id = f"case_{datetime.utcnow().timestamp()}_{params.get('client_name', 'unknown').replace(' ', '_')}"

            # Determine case type
            case_type_str = params.get("case_type", "general")
            case_type = CaseType(case_type_str) if case_type_str else CaseType.GENERAL

            # Create case
            case = Case(
                id=case_id,
                client_name=params.get("client_name", "Unknown"),
                case_title=params.get("case_title", f"Case: {params.get('client_name', 'Unknown')}"),
                case_type=case_type,
                status=CaseStatus.OPEN,
                required_fields=params.get("required_fields", []),
                notes=params.get("notes", ""),
            )

            # Save to repository
            created_case = await self.case_repo.create_case(case)

            # Update action
            action.case_id = created_case.id
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state={},
                after_state=created_case.model_dump(),
            )

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to create case: {e}")

    async def _update_case(self, action: Action) -> bool:
        """Update an existing case with new field values."""
        try:
            if not action.case_id:
                raise ActionExecutionError("Case ID required for UPDATE_CASE action")

            # Get existing case
            case = await self.case_repo.get_case(action.case_id)
            before_state = case.model_dump()

            # Extract field updates
            field_updates = action.parameters.get("field_updates", {})

            # Add each field
            for field_name, field_value in field_updates.items():
                FieldTracker.add_field_value(
                    case=case,
                    field_name=field_name,
                    value=field_value,
                    source_message_id=action.triggered_by,
                    confidence=1.0,
                )

            # Check if case should auto-transition state
            new_status = CaseStateMachine.should_auto_transition(case)
            if new_status:
                CaseStateMachine.transition(case, new_status)

            # Update case
            updated_case = await self.case_repo.update_case(case)

            # Update action
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state=before_state,
                after_state=updated_case.model_dump(),
            )

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to update case: {e}")

    async def _complete_case(self, action: Action) -> bool:
        """Mark a case as complete."""
        try:
            if not action.case_id:
                raise ActionExecutionError("Case ID required for COMPLETE_CASE action")

            # Get existing case
            case = await self.case_repo.get_case(action.case_id)
            before_state = case.model_dump()

            # Transition through intermediate states if needed
            if case.status == CaseStatus.OPEN:
                CaseStateMachine.transition(case, CaseStatus.IN_PROGRESS)

            if case.status == CaseStatus.AWAITING_INFO:
                CaseStateMachine.transition(case, CaseStatus.IN_PROGRESS)

            # Transition to COMPLETE
            CaseStateMachine.transition(case, CaseStatus.COMPLETE)

            # Update case
            updated_case = await self.case_repo.update_case(case)

            # Update action
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state=before_state,
                after_state=updated_case.model_dump(),
            )

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to complete case: {e}")

    async def _cancel_case(self, action: Action) -> bool:
        """Cancel a case."""
        try:
            if not action.case_id:
                raise ActionExecutionError("Case ID required for CANCEL_CASE action")

            # Get existing case
            case = await self.case_repo.get_case(action.case_id)
            before_state = case.model_dump()

            # Transition to CANCELLED
            CaseStateMachine.transition(case, CaseStatus.CANCELLED)

            # Update case
            updated_case = await self.case_repo.update_case(case)

            # Update action
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state=before_state,
                after_state=updated_case.model_dump(),
            )

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to cancel case: {e}")
