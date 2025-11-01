"""
Case state machine for managing state transitions.
"""
from typing import Dict, Optional, Set

from core.enums import CaseStatus, CaseType
from core.exceptions import InvalidStateTransitionError
from core.models import Case


class CaseStateMachine:
    """
    Manages valid state transitions for cases.

    State diagram:
    OPEN → IN_PROGRESS → AWAITING_INFO ⟷ IN_PROGRESS → COMPLETE
                                        ↘ CANCELLED
    """

    # Define valid transitions
    VALID_TRANSITIONS: Dict[CaseStatus, Set[CaseStatus]] = {
        CaseStatus.OPEN: {
            CaseStatus.IN_PROGRESS,
            CaseStatus.CANCELLED,
        },
        CaseStatus.IN_PROGRESS: {
            CaseStatus.AWAITING_INFO,
            CaseStatus.COMPLETE,
            CaseStatus.CANCELLED,
        },
        CaseStatus.AWAITING_INFO: {
            CaseStatus.IN_PROGRESS,
            CaseStatus.COMPLETE,
            CaseStatus.CANCELLED,
        },
        CaseStatus.COMPLETE: set(),  # Terminal state
        CaseStatus.CANCELLED: set(),  # Terminal state
    }

    @classmethod
    def can_transition(
        cls,
        from_status: CaseStatus,
        to_status: CaseStatus,
    ) -> bool:
        """
        Check if a state transition is valid.

        Args:
            from_status: Current status
            to_status: Target status

        Returns:
            True if transition is valid
        """
        # Allow same-state transitions (no-op)
        if from_status == to_status:
            return True

        return to_status in cls.VALID_TRANSITIONS.get(from_status, set())

    @classmethod
    def validate_transition(
        cls,
        case: Case,
        new_status: CaseStatus,
    ) -> None:
        """
        Validate a state transition for a case.

        Args:
            case: The case to transition
            new_status: Target status

        Raises:
            InvalidStateTransitionError: If transition is invalid
        """
        if not cls.can_transition(case.status, new_status):
            raise InvalidStateTransitionError(
                f"Invalid state transition for case {case.id}: "
                f"{case.status.value} → {new_status.value}"
            )

    @classmethod
    def transition(
        cls,
        case: Case,
        new_status: CaseStatus,
        validate: bool = True,
    ) -> Case:
        """
        Transition a case to a new status.

        Args:
            case: The case to transition
            new_status: Target status
            validate: Whether to validate the transition

        Returns:
            Case with updated status

        Raises:
            InvalidStateTransitionError: If validation enabled and transition invalid
        """
        if validate:
            cls.validate_transition(case, new_status)

        # Update status
        old_status = case.status
        case.status = new_status

        # Handle status-specific logic
        if new_status == CaseStatus.COMPLETE:
            from datetime import datetime
            case.completed_at = datetime.utcnow()

        return case

    @classmethod
    def should_auto_transition(cls, case: Case) -> Optional[CaseStatus]:
        """
        Determine if case should automatically transition to a new state.

        Args:
            case: The case to check

        Returns:
            New status if auto-transition recommended, None otherwise
        """
        # If case type is LOA and all fields received, transition to COMPLETE
        if case.case_type == CaseType.LOA:
            if case.status in [CaseStatus.IN_PROGRESS, CaseStatus.AWAITING_INFO]:
                if case.is_complete():
                    return CaseStatus.COMPLETE
                elif case.get_missing_fields():
                    # If missing fields, should be in AWAITING_INFO
                    if case.status != CaseStatus.AWAITING_INFO:
                        return CaseStatus.AWAITING_INFO

        return None

    @classmethod
    def get_next_states(cls, current_status: CaseStatus) -> Set[CaseStatus]:
        """
        Get all valid next states from current status.

        Args:
            current_status: Current status

        Returns:
            Set of valid next states
        """
        return cls.VALID_TRANSITIONS.get(current_status, set()).copy()

    @classmethod
    def is_terminal_state(cls, status: CaseStatus) -> bool:
        """
        Check if a status is a terminal state.

        Args:
            status: Status to check

        Returns:
            True if terminal state
        """
        return len(cls.VALID_TRANSITIONS.get(status, set())) == 0
