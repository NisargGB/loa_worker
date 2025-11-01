"""
Abstract LLM service interface.
"""
import dotenv

dotenv.load_dotenv()
import json
import os
import re
from abc import ABC
from textwrap import dedent
from typing import Any, Dict, Optional

from core.enums import ActionType, CaseType, LLMName, MessageCategory
from core.models import (Action, Case, Classification, ExtractedEntities,
                         Message)
from llm.llm_client import LLMClient


class LLMService(ABC):
    """LLM service with concrete default implementations using the configured provider."""

    async def classify_message(self, message: Message) -> Classification:
        """
        Classify a message to determine its category and relevance.

        Args:
            message: The message to classify

        Returns:
            Classification result with category, confidence, and reasoning
        """
        text = message.get_text_content().strip()
        if not text:
            return Classification(
                category=MessageCategory.IRRELEVANT,
                confidence=1.0,
                reasoning="Empty message content",
                is_relevant=False,
            )

        llm_client = await LLMClient.from_llm_name(LLMName.GEMINI_2_5_FLASH)
        system_message = dedent("""
            You classify inbound communications for a case processing system handling Letters of Authority (LoA) and related admin.
            Return only strict JSON following this schema and constraints:
            {{
              "category": one of {category_values},
              "confidence": number between 0 and 1 inclusive,
              "reasoning": short string (<= 200 chars),
              "is_relevant": boolean (false when category is IRRELEVANT or ADMIN)
            }}
            Do not include code fences, preambles, or extra text. Ensure keys are exactly as specified.

            More information about the categories:
            {category_descriptions}
            """
        ).strip().format(
            category_values='[' + ', '.join([f'"{value}"' for value in MessageCategory.get_all_values()]) + ']',
            category_descriptions='\n'.join([f"- {e.value}: {e.get_description()}" for e in MessageCategory.get_all_enums()])
        )

        user_prompt = dedent("""
            Classify the following message. Consider LoA workflows, provider responses, missing information requests, and general admin.

            Message:
            ---
            {text}
            ---

            Output strict JSON as specified.
            """
        ).strip().format(text=text)

        messages = [
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm_client.generate_text(
                system_message=system_message, messages=messages, max_tries=3, timeout=60
            )
        except Exception as e:
            return self._heuristic_classification(text, fallback_reason=f"LLM error: {e}")

        if response:
            parsed = self._parse_first_json_object(response)
            if isinstance(parsed, dict):
                cat_val = (parsed.get("category") or "").upper().replace("-", "_").replace(" ", "_")
                category = self._safe_category(cat_val)
                confidence = self._clamp_float(parsed.get("confidence"), default=0.6)
                reasoning = str(parsed.get("reasoning") or "No reasoning provided").strip()[:200]
                is_relevant = bool(parsed.get("is_relevant"))

                if category is not None:
                    # Normalize relevance consistent with category
                    if category in (MessageCategory.IRRELEVANT, MessageCategory.ADMIN):
                        is_relevant = False
                    return Classification(
                        category=category,
                        confidence=confidence,
                        reasoning=reasoning,
                        is_relevant=is_relevant,
                    )

        return self._heuristic_classification(text, fallback_reason="Unable to parse LLM response")

    async def extract_entities(
        self,
        message: Message,
        classification: Classification,
    ) -> ExtractedEntities:
        """
        Extract structured entities from a message.

        Args:
            message: The message to extract from
            classification: The classification result for context

        Returns:
            Extracted entities including client name, case info, field updates
        """
        text = message.get_text_content().strip()
        if not text:
            return ExtractedEntities()

        llm_client = await LLMClient.from_llm_name(LLMName.GEMINI_2_5_FLASH)
        system_message = dedent("""
            You extract structured entities for case processing in the LoA domain.
            Return only strict JSON following this schema:
            {{
              "client_name": string|null,
              "case_title": string|null,
              "field_updates": {"<field_name>": "<value>"},
              "missing_fields": [string],
              "confidence": number between 0 and 1,
              "additional_context": {"notes": string}
            }}
            Field naming rules:
              - Use lower_snake_case for keys in field_updates
              - Canonical keys when applicable: date_of_birth, national_insurance_number, plan_number, provider_name, address
            Only include fields that are explicitly inferable from the message.
            """
        ).strip()

        user_prompt = dedent("""
            Message classification category: {classification_category}
            Message classification description: {classification_description}

            Extract entities from this message:
            ---
            {text}
            ---

            Output strict JSON as specified.
            """
        ).strip().format(classification_category=classification.category.value, classification_description=classification.category.get_description(), text=text)

        messages = [
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await llm_client.generate_text(
                system_message=system_message, messages=messages, max_tries=3, timeout=90
            )
        except Exception:
            return ExtractedEntities()

        parsed = self._parse_first_json_object(response or "")
        if not isinstance(parsed, dict):
            return ExtractedEntities()

        client_name = self._as_optional_str(parsed.get("client_name"))
        case_title = self._as_optional_str(parsed.get("case_title"))

        field_updates = parsed.get("field_updates") or {}
        if not isinstance(field_updates, dict):
            field_updates = {}
        field_updates = self._canonicalize_field_updates(field_updates)

        missing_fields = parsed.get("missing_fields") or []
        if not isinstance(missing_fields, list):
            missing_fields = []
        missing_fields = [self._to_snake(str(x)) for x in missing_fields if isinstance(x, (str, int, float))]

        confidence = self._clamp_float(parsed.get("confidence"), default=0.7)

        additional_context = parsed.get("additional_context") or {}
        if not isinstance(additional_context, dict):
            additional_context = {}

        return ExtractedEntities(
            client_name=client_name,
            case_id=None,
            case_title=case_title,
            field_updates=field_updates,
            missing_fields=missing_fields,
            confidence=confidence,
            additional_context=additional_context,
        )

    async def determine_action(
        self,
        message: Message,
        classification: Classification,
        entities: ExtractedEntities,
        existing_case: Optional[Case] = None,
    ) -> Action:
        """
        Determine what action to take based on message analysis.

        Args:
            message: The original message
            classification: Classification result
            entities: Extracted entities
            existing_case: Existing case if found, None otherwise

        Returns:
            Action to be executed
        """
        category = classification.category

        if category in (MessageCategory.IRRELEVANT, MessageCategory.ADMIN):
            return Action(
                type=ActionType.IGNORE,
                case_id=existing_case.id if existing_case else None,
                parameters={},
                triggered_by=message.id,
            )

        field_updates = dict(entities.field_updates or {})
        missing_fields = list(entities.missing_fields or [])

        # Decide case_type
        is_loa_related = category in (
            MessageCategory.LOA_CHASE,
            MessageCategory.LOA_MISSING_INFO,
            MessageCategory.LOA_RESPONSE,
        )
        case_type = CaseType.LOA if is_loa_related else CaseType.GENERAL

        # Determine action type with case awareness
        if existing_case:
            if category == MessageCategory.LOA_RESPONSE and field_updates:
                action_type = ActionType.UPDATE_CASE
            elif category == MessageCategory.LOA_MISSING_INFO:
                # Use case's missing fields if not provided
                if not missing_fields:
                    try:
                        missing_fields = existing_case.get_missing_fields()
                    except Exception:
                        missing_fields = []
                action_type = ActionType.DRAFT_FOLLOWUP_EMAIL
            elif category == MessageCategory.CLIENT_TASK:
                action_type = ActionType.CREATE_TASK
            elif category == MessageCategory.LOA_CHASE:
                action_type = ActionType.INITIATE_LOA_CHASE
            else:
                # Default to update if we have any structured info
                action_type = ActionType.UPDATE_CASE if field_updates else ActionType.IGNORE
        else:
            if category in (MessageCategory.CLIENT_TASK, MessageCategory.LOA_RESPONSE, MessageCategory.LOA_MISSING_INFO):
                action_type = ActionType.CREATE_CASE
            elif category == MessageCategory.LOA_CHASE:
                # No case yet → create one to track the chase context
                action_type = ActionType.CREATE_CASE
            else:
                action_type = ActionType.IGNORE

        parameters: Dict[str, Any] = {
            "client_name": entities.client_name,
            "case_title": entities.case_title,
            "field_updates": field_updates,
            "missing_fields": missing_fields,
        }

        if action_type == ActionType.CREATE_CASE:
            # Provide reasonable defaults for a new case
            parameters["case_type"] = case_type.value
            # Hints to required fields for LoA; downstream can override
            if case_type == CaseType.LOA:
                parameters.setdefault(
                    "required_fields",
                    [
                        "date_of_birth",
                        "national_insurance_number",
                        "plan_number",
                        "provider_name",
                    ],
                )

        if action_type in (ActionType.CREATE_TASK, ActionType.COMPLETE_TASK):
            parameters.setdefault("task_title", entities.case_title or "Client task")
            parameters.setdefault("task_description", message.get_text_content()[:500])

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
        Generate a follow-up email requesting missing information.

        Args:
            case: The case requiring follow-up
            missing_fields: List of fields that are missing

        Returns:
            Generated email content
        """
        fields_list = "\n".join(f"- {f}" for f in missing_fields)
        llm_client = await LLMClient.from_llm_name(LLMName.GEMINI_2_5_FLASH)
        system_message = dedent("""
            You draft clear, professional, concise emails to financial providers.
            Return plain text only, no greetings beyond the email body, no signatures unless asked.
            Keep tone polite and direct. UK English. 120-200 words. Include list formatting for missing fields.
            """
        ).strip()

        user_prompt = dedent("""
            Draft a follow-up email to the provider about an LoA case.

            Client name: {client_name}
            Case title: {case_title}
            Missing fields (bullet list):
            {fields_list}

            Constraints:
            - Ask for the specific missing information above
            - Reference the case succinctly
            - Thank the recipient and request a response
            - Return plain text only
            """
        ).strip().format(client_name=case.client_name, case_title=case.case_title, fields_list=fields_list)

        messages = [
            {"role": "user", "content": user_prompt},
        ]

        try:
            email = await llm_client.generate_text(
                system_message=system_message, messages=messages, max_tries=2, timeout=45
            )
            email = (email or "").strip()
            if email:
                return email
        except Exception:
            pass

        # Fallback template
        return (
            f"Dear Provider,\n\n"
            f"We are following up on the Letter of Authority for {case.client_name} (Case: {case.case_title}).\n\n"
            f"We are still awaiting the following information:\n"
            f"{fields_list}\n\n"
            f"Please provide these details at your earliest convenience to complete our records.\n\n"
            f"Kind regards,\n"
            f"LoA Team"
        )

    async def health_check(self) -> bool:
        """
        Check if the LLM service is available and healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            llm_client = await LLMClient.from_llm_name(LLMName.GEMINI_2_5_FLASH)
            resp = await llm_client.generate_text(
                system_message="You answer with a single word: pong.",
                messages=[{"role": "user", "content": "ping"}],
                timeout=10,
                max_tries=1,
            )
            return bool((resp or "").strip())
        except Exception:
            return False

    def _parse_first_json_object(self, text: str) -> Any:
        """Extract and parse the first top-level JSON object in a string."""
        if not text:
            return None
        s = text.strip()
        # Strip code fences if present
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", s).strip()
        # Quick attempt
        try:
            return json.loads(s)
        except Exception:
            pass
        # Find first balanced JSON object
        start = s.find("{")
        if start == -1:
            return None
        brace = 0
        in_string = False
        escape = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    brace += 1
                elif ch == "}":
                    brace -= 1
                    if brace == 0:
                        try:
                            return json.loads(s[start : i + 1])
                        except Exception:
                            return None
        return None

    def _clamp_float(self, value: Any, default: float = 0.5) -> float:
        try:
            f = float(value)
        except Exception:
            return default
        if f < 0.0:
            return 0.0
        if f > 1.0:
            return 1.0
        return f

    def _safe_category(self, value: str) -> Optional[MessageCategory]:
        mapping = {
            "CLIENT_TASK": MessageCategory.CLIENT_TASK,
            "LOA_CHASE": MessageCategory.LOA_CHASE,
            "LOA_MISSING_INFO": MessageCategory.LOA_MISSING_INFO,
            "LOA_RESPONSE": MessageCategory.LOA_RESPONSE,
            "ADMIN": MessageCategory.ADMIN,
            "IRRELEVANT": MessageCategory.IRRELEVANT,
        }
        # Common synonyms
        value = value.upper().replace("-", "_").replace(" ", "_")
        synonyms = {
            "MISSING_INFO": "LOA_MISSING_INFO",
            "CHASE": "LOA_CHASE",
            "RESPONSE": "LOA_RESPONSE",
        }
        value = synonyms.get(value, value)
        return mapping.get(value)

    def _heuristic_classification(self, text: str, fallback_reason: str) -> Classification:
        lower = text.lower()
        category = MessageCategory.IRRELEVANT
        is_relevant = False
        if any(k in lower for k in ["unsubscribe", "out of office", "newsletter", "meeting", "invoice", "billing"]):
            category = MessageCategory.ADMIN
            is_relevant = False
        elif any(k in lower for k in ["missing", "provide", "required", "need more", "can't process", "insufficient"]):
            category = MessageCategory.LOA_MISSING_INFO
            is_relevant = True
        elif any(k in lower for k in ["attached", "signed loa", "authorised", "policy", "plan number", "dob", "ni number", "national insurance"]):
            category = MessageCategory.LOA_RESPONSE
            is_relevant = True
        elif any(k in lower for k in ["follow up", "chase", "status", "update on", "when can", "awaiting"]):
            category = MessageCategory.LOA_CHASE
            is_relevant = True
        elif any(k in lower for k in ["open a case", "create case", "start loa", "onboard", "annual review", "task"]):
            category = MessageCategory.CLIENT_TASK
            is_relevant = True
        return Classification(
            category=category,
            confidence=0.6 if is_relevant else 0.5,
            reasoning=fallback_reason,
            is_relevant=is_relevant,
        )

    def _to_snake(self, s: str) -> str:
        s = re.sub(r"[^0-9A-Za-z]+", "_", s.strip())
        s = re.sub(r"_+", "_", s)
        return s.strip("_").lower()

    def _canonicalize_field_updates(self, updates: Dict[str, Any]) -> Dict[str, str]:
        canonical: Dict[str, str] = {}
        for k, v in updates.items():
            key = self._to_snake(str(k))
            val = "" if v is None else str(v).strip()
            if key in {"dob", "dateofbirth"}:
                key = "date_of_birth"
            if key in {"ni", "ni_number", "nationalinsurancenumber", "national_insurance"}:
                key = "national_insurance_number"
            if key in {"policy_number", "policynumber", "plan", "plannumber"}:
                key = "plan_number"
            if key in {"provider", "providername"}:
                key = "provider_name"
            canonical[key] = val
        return canonical

    def _as_optional_str(self, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


def get_llm_service() -> LLMService:
    from llm.mock_service import MockLLMService
    if os.getenv("MOCK_LLM_SERVICE") in ["true", "1", "yes", "y"]:
        return MockLLMService()
    return LLMService()
