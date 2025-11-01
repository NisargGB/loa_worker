"""
Action handlers for task-related actions.
"""
from datetime import datetime
from .base import ActionHandler
from ..core.models import Action, Task
from ..core.enums import ActionType, CaseStatus
from ..core.exceptions import ActionExecutionError


class TaskActionHandler(ActionHandler):
    """Handles task-related actions (CREATE, COMPLETE)."""

    async def execute(self, action: Action) -> bool:
        """
        Execute task action.

        Args:
            action: Action to execute

        Returns:
            True if successful

        Raises:
            ActionExecutionError: If execution fails
        """
        if action.type == ActionType.CREATE_TASK:
            return await self._create_task(action)
        elif action.type == ActionType.COMPLETE_TASK:
            return await self._complete_task(action)
        else:
            raise ActionExecutionError(f"Unsupported action type: {action.type}")

    async def _create_task(self, action: Action) -> bool:
        """Create a new task."""
        try:
            params = action.parameters

            # Generate task ID
            task_id = f"task_{datetime.utcnow().timestamp()}"

            # Create task
            task = Task(
                id=task_id,
                case_id=action.case_id,
                title=params.get("task_title", "Unnamed Task"),
                description=params.get("task_description", ""),
                status=CaseStatus.OPEN,
            )

            # Save to repository
            created_task = await self.case_repo.create_task(task)

            # Update action
            action.success = True
            action.executed_at = datetime.utcnow()
            action.parameters["task_id"] = created_task.id

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state={},
                after_state=created_task.model_dump(),
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
            raise ActionExecutionError(f"Failed to create task: {e}")

    async def _complete_task(self, action: Action) -> bool:
        """Complete a task."""
        try:
            params = action.parameters
            task_title = params.get("task_title")

            if not task_title:
                raise ActionExecutionError("Task title required for COMPLETE_TASK action")

            # Find task by title
            task = await self.case_repo.find_task_by_title(
                task_title=task_title,
                case_id=action.case_id,
            )

            if not task:
                raise ActionExecutionError(f"Task not found: {task_title}")

            before_state = task.model_dump()

            # Mark as complete
            task.status = CaseStatus.COMPLETE
            task.completed_at = datetime.utcnow()

            # Update task
            updated_task = await self.case_repo.update_task(task)

            # Update action
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state=before_state,
                after_state=updated_task.model_dump(),
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
            raise ActionExecutionError(f"Failed to complete task: {e}")
