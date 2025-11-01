"""
Field completion tracking for LoA cases.
"""
from datetime import datetime
from typing import Dict, List, Set

from core.models import Case, FieldValue


class FieldTracker:
    """Tracks required vs received fields for LoA cases."""

    @staticmethod
    def get_missing_fields(case: Case) -> List[str]:
        """
        Get list of fields still missing from a case.

        Args:
            case: The case to check

        Returns:
            List of missing field names
        """
        return case.get_missing_fields()

    @staticmethod
    def get_received_fields(case: Case) -> List[str]:
        """
        Get list of fields that have been received.

        Args:
            case: The case to check

        Returns:
            List of received field names
        """
        return list(case.received_fields.keys())

    @staticmethod
    def calculate_completion_percentage(case: Case) -> float:
        """
        Calculate percentage of required fields received.

        Args:
            case: The case to check

        Returns:
            Completion percentage (0-100)
        """
        return case.get_completion_percentage()

    @staticmethod
    def is_field_received(case: Case, field_name: str) -> bool:
        """
        Check if a specific field has been received.

        Args:
            case: The case to check
            field_name: Name of the field

        Returns:
            True if field received
        """
        return field_name in case.received_fields

    @staticmethod
    def add_field_value(
        case: Case,
        field_name: str,
        value: str,
        source_message_id: str,
        confidence: float = 1.0,
    ) -> Case:
        """
        Add a field value to a case.

        Args:
            case: The case to update
            field_name: Name of the field
            value: Field value
            source_message_id: ID of message that provided this value
            confidence: Confidence score (0-1)

        Returns:
            Updated case
        """
        field_value = FieldValue(
            field_name=field_name,
            value=value,
            received_at=datetime.utcnow(),
            source_message_id=source_message_id,
            confidence=confidence,
        )

        case.received_fields[field_name] = field_value
        case.updated_at = datetime.utcnow()

        return case

    @staticmethod
    def get_field_sources(case: Case) -> Dict[str, str]:
        """
        Get a mapping of field names to their source message IDs.

        Args:
            case: The case to check

        Returns:
            Dictionary mapping field names to message IDs
        """
        return {
            field_name: field_value.source_message_id
            for field_name, field_value in case.received_fields.items()
        }

    @staticmethod
    def get_low_confidence_fields(
        case: Case,
        threshold: float = 0.7,
    ) -> List[str]:
        """
        Get fields with confidence below threshold.

        Args:
            case: The case to check
            threshold: Confidence threshold

        Returns:
            List of field names with low confidence
        """
        return [
            field_name
            for field_name, field_value in case.received_fields.items()
            if field_value.confidence < threshold
        ]

    @staticmethod
    def categorize_fields(case: Case) -> Dict[str, Set[str]]:
        """
        Categorize fields into received, missing, and extra.

        Args:
            case: The case to analyze

        Returns:
            Dictionary with 'received', 'missing', and 'extra' field sets
        """
        required = set(case.required_fields)
        received = set(case.received_fields.keys())

        return {
            "received": required & received,  # Required and received
            "missing": required - received,    # Required but not received
            "extra": received - required,      # Received but not required
        }

    @staticmethod
    def suggest_next_action(case: Case) -> str:
        """
        Suggest next action based on field completion status.

        Args:
            case: The case to analyze

        Returns:
            Suggested action as string
        """
        missing = FieldTracker.get_missing_fields(case)

        if not missing:
            return "All required fields received. Case can be completed."

        if len(missing) == 1:
            return f"Chase provider for: {missing[0]}"

        if len(missing) <= 3:
            fields_str = ", ".join(missing)
            return f"Chase provider for: {fields_str}"

        return f"Chase provider for {len(missing)} missing fields"
