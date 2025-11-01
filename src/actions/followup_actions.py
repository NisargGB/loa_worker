"""
Action handlers for follow-up actions.
"""
from datetime import datetime
from typing import Optional
from .base import ActionHandler
from ..core.models import Action
from ..core.enums import ActionType
from ..core.exceptions import ActionExecutionError
from ..llm.service import LLMService


class FollowupActionHandler(ActionHandler):
    """Handles follow-up actions (DRAFT_FOLLOWUP_EMAIL, INITIATE_LOA_CHASE)."""

    def __init__(
        self,
        case_repo,
        audit_repo,
        llm_service: Optional[LLMService] = None,
    ):
        """
        Initialize the handler.

        Args:
            case_repo: Case repository
            audit_repo: Audit repository
            llm_service: Optional LLM service for email generation
        """
        super().__init__(case_repo, audit_repo)
        self.llm_service = llm_service

    async def execute(self, action: Action) -> bool:
        """
        Execute follow-up action.

        Args:
            action: Action to execute

        Returns:
            True if successful

        Raises:
            ActionExecutionError: If execution fails
        """
        if action.type == ActionType.DRAFT_FOLLOWUP_EMAIL:
            return await self._draft_followup_email(action)
        elif action.type == ActionType.INITIATE_LOA_CHASE:
            return await self._initiate_loa_chase(action)
        else:
            raise ActionExecutionError(f"Unsupported action type: {action.type}")

    async def _draft_followup_email(self, action: Action) -> bool:
        """Draft a follow-up email for missing information."""
        try:
            if not action.case_id:
                raise ActionExecutionError("Case ID required for DRAFT_FOLLOWUP_EMAIL action")

            # Get case
            case = await self.case_repo.get_case(action.case_id)

            # Get missing fields
            missing_fields = action.parameters.get("missing_fields", case.get_missing_fields())

            if not missing_fields:
                # No missing fields, nothing to chase
                action.success = True
                action.executed_at = datetime.utcnow()
                action.parameters["email_content"] = "No missing fields to follow up on."

                await self.log_action(
                    action=action,
                    success=True,
                    before_state={},
                    after_state={"status": "no_action_needed"},
                )

                return True

            # Generate email content
            if self.llm_service:
                email_content = await self.llm_service.generate_followup_email(
                    case=case,
                    missing_fields=missing_fields,
                )
            else:
                # Fallback template
                email_content = self._generate_simple_followup(case, missing_fields)

            # Store in action parameters
            action.parameters["email_content"] = email_content
            action.parameters["missing_fields"] = missing_fields
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state={},
                after_state={
                    "email_drafted": True,
                    "missing_fields": missing_fields,
                },
            )

            # In a real system, this would send the email or queue it for review
            # For now, we just log it
            print(f"\n--- DRAFT EMAIL FOR CASE {case.case_title} ---")
            print(email_content)
            print("--- END DRAFT EMAIL ---\n")

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to draft follow-up email: {e}")

    async def _initiate_loa_chase(self, action: Action) -> bool:
        """Initiate a chase for LoA response."""
        try:
            if not action.case_id:
                raise ActionExecutionError("Case ID required for INITIATE_LOA_CHASE action")

            # Get case
            case = await self.case_repo.get_case(action.case_id)

            # Create a chase record (in real system, this might create a task or reminder)
            chase_info = {
                "case_id": case.id,
                "case_title": case.case_title,
                "client_name": case.client_name,
                "missing_fields": case.get_missing_fields(),
                "chase_initiated_at": datetime.utcnow().isoformat(),
            }

            action.parameters["chase_info"] = chase_info
            action.success = True
            action.executed_at = datetime.utcnow()

            # Log action
            await self.log_action(
                action=action,
                success=True,
                before_state={},
                after_state=chase_info,
            )

            print(f"\n--- LOA CHASE INITIATED FOR CASE {case.case_title} ---")
            print(f"Client: {case.client_name}")
            print(f"Missing fields: {', '.join(case.get_missing_fields())}")
            print("--- END LOA CHASE ---\n")

            return True

        except Exception as e:
            await self.log_action(
                action=action,
                success=False,
                before_state={},
                after_state={},
                error_message=str(e),
            )
            raise ActionExecutionError(f"Failed to initiate LOA chase: {e}")

    @staticmethod
    def _generate_simple_followup(case, missing_fields: list) -> str:
        """Generate simple follow-up email without LLM."""
        fields_list = "\n".join(f"- {field}" for field in missing_fields)

        return f"""Dear Provider,

We are following up on the Letter of Authority for {case.client_name}.

We are still awaiting the following information:
{fields_list}

Please provide these details at your earliest convenience.

Thank you for your assistance.

Best regards
"""
