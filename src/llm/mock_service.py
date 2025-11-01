"""
Mock LLM service for testing and development.
"""
from typing import Optional
from .service import LLMService
from ..core.models import Message, Classification, ExtractedEntities, Action, Case
from ..core.enums import MessageCategory, ActionType


class MockLLMService(LLMService):
    """
    Mock LLM service that uses expected values from metadata.
    Useful for testing and demonstrating the system without real LLM calls.
    """

    async def classify_message(self, message: Message) -> Classification:
        """
        Classify message using expected_category from metadata.

        Args:
            message: The message to classify

        Returns:
            Classification based on metadata expectations
        """
        expected_category = message.metadata.get("expected_category")

        if expected_category:
            category = MessageCategory(expected_category)
            is_relevant = category != MessageCategory.IRRELEVANT
            reasoning = f"Mock classification: Message categorized as {category.value}"

            return Classification(
                category=category,
                confidence=1.0,
                reasoning=reasoning,
                is_relevant=is_relevant,
            )
        else:
            # Default fallback
            return Classification(
                category=MessageCategory.IRRELEVANT,
                confidence=0.5,
                reasoning="Mock classification: No expected category in metadata",
                is_relevant=False,
            )

    async def extract_entities(
        self,
        message: Message,
        classification: Classification,
    ) -> ExtractedEntities:
        """
        Extract entities using expected values from metadata.

        Args:
            message: The message to extract from
            classification: Classification for context

        Returns:
            Extracted entities based on metadata expectations
        """
        metadata = message.metadata

        # Extract field updates from the message
        field_updates = {}
        if updated_fields := metadata.get("expected_updated_contains"):
            # In real implementation, LLM would extract actual values
            # Here we just mark that these fields were updated
            text = message.get_text_content().lower()
            for field in updated_fields:
                # Simulate extraction by finding field mentions in text
                if field.lower() in text:
                    field_updates[field] = f"[extracted from message {message.id}]"

        # Extract missing fields
        missing_fields = metadata.get("expected_missing_contains") or []

        return ExtractedEntities(
            client_name=metadata.get("expected_client_name"),
            case_id=None,  # Will be resolved by case matching logic
            case_title=metadata.get("expected_case_title"),
            field_updates=field_updates,
            missing_fields=missing_fields,
            confidence=1.0,
        )

    async def determine_action(
        self,
        message: Message,
        classification: Classification,
        entities: ExtractedEntities,
        existing_case: Optional[Case] = None,
    ) -> Action:
        """
        Determine action using expected_action from metadata.

        Args:
            message: The original message
            classification: Classification result
            entities: Extracted entities
            existing_case: Existing case if found

        Returns:
            Action to execute based on metadata expectations
        """
        expected_action = message.metadata.get("expected_action")

        if expected_action:
            # Handle legacy action names from test data
            action_mapping = {
                "UPDATE_LOA_CASE": "UPDATE_CASE",
            }
            expected_action = action_mapping.get(expected_action, expected_action)
            action_type = ActionType(expected_action)
        else:
            # Default action based on classification
            action_type = self._infer_action_from_classification(classification)

        # Build action parameters
        parameters = {
            "client_name": entities.client_name,
            "case_title": entities.case_title,
            "field_updates": entities.field_updates,
            "missing_fields": entities.missing_fields,
        }

        # Add case-type specific parameters
        if action_type == ActionType.CREATE_CASE:
            parameters["case_type"] = message.metadata.get("expected_case_type", "general")
            parameters["required_fields"] = message.metadata.get("expected_required_fields", [])

        if action_type in [ActionType.CREATE_TASK, ActionType.COMPLETE_TASK]:
            parameters["task_title"] = message.metadata.get("expected_task_title")
            parameters["task_description"] = message.metadata.get("expected_task_description")

        return Action(
            type=action_type,
            case_id=existing_case.id if existing_case else None,
            parameters=parameters,
            triggered_by=message.id,
        )

    async def generate_followup_email(
        self,
        case: Case,
        missing_fields: list[str],
    ) -> str:
        """
        Generate a mock follow-up email.

        Args:
            case: The case requiring follow-up
            missing_fields: List of missing fields

        Returns:
            Generated email content
        """
        fields_list = ", ".join(missing_fields)

        email = f"""Dear Provider,

We are following up on the Letter of Authority for {case.client_name} (Case: {case.case_title}).

We are still awaiting the following information:
{chr(10).join(f'- {field}' for field in missing_fields)}

Please provide these details at your earliest convenience to complete our records.

Thank you for your assistance.

Best regards,
[Mock Email Generator]
"""
        return email

    async def health_check(self) -> bool:
        """
        Mock health check always returns True.

        Returns:
            True
        """
        return True

    @staticmethod
    def _infer_action_from_classification(classification: Classification) -> ActionType:
        """
        Infer action type from classification category.

        Args:
            classification: The classification result

        Returns:
            Inferred action type
        """
        category_to_action = {
            MessageCategory.CLIENT_TASK: ActionType.CREATE_CASE,
            MessageCategory.LOA_RESPONSE: ActionType.UPDATE_CASE,
            MessageCategory.LOA_MISSING_INFO: ActionType.DRAFT_FOLLOWUP_EMAIL,
            MessageCategory.LOA_CHASE: ActionType.INITIATE_LOA_CHASE,
            MessageCategory.IRRELEVANT: ActionType.IGNORE,
        }
        return category_to_action.get(classification.category, ActionType.IGNORE)
