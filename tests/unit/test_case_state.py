"""
Unit tests for case state machine.
"""
import pytest
from datetime import datetime
from src.core.models import Case
from src.core.enums import CaseType, CaseStatus
from src.state.case_state import CaseStateMachine
from src.core.exceptions import InvalidStateTransitionError


def test_valid_transitions():
    """Test valid state transitions."""
    assert CaseStateMachine.can_transition(CaseStatus.OPEN, CaseStatus.IN_PROGRESS)
    assert CaseStateMachine.can_transition(CaseStatus.IN_PROGRESS, CaseStatus.AWAITING_INFO)
    assert CaseStateMachine.can_transition(CaseStatus.AWAITING_INFO, CaseStatus.IN_PROGRESS)
    assert CaseStateMachine.can_transition(CaseStatus.IN_PROGRESS, CaseStatus.COMPLETE)


def test_invalid_transitions():
    """Test invalid state transitions."""
    assert not CaseStateMachine.can_transition(CaseStatus.COMPLETE, CaseStatus.OPEN)
    assert not CaseStateMachine.can_transition(CaseStatus.CANCELLED, CaseStatus.IN_PROGRESS)
    assert not CaseStateMachine.can_transition(CaseStatus.OPEN, CaseStatus.COMPLETE)


def test_same_state_transition():
    """Test same-state transitions are allowed."""
    assert CaseStateMachine.can_transition(CaseStatus.OPEN, CaseStatus.OPEN)
    assert CaseStateMachine.can_transition(CaseStatus.COMPLETE, CaseStatus.COMPLETE)


def test_transition_with_validation():
    """Test transition with validation."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        status=CaseStatus.OPEN,
    )

    # Valid transition
    updated_case = CaseStateMachine.transition(case, CaseStatus.IN_PROGRESS)
    assert updated_case.status == CaseStatus.IN_PROGRESS

    # Invalid transition should raise exception
    with pytest.raises(InvalidStateTransitionError):
        CaseStateMachine.transition(updated_case, CaseStatus.COMPLETE)


def test_transition_without_validation():
    """Test transition without validation."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        status=CaseStatus.OPEN,
    )

    # Force invalid transition without validation
    updated_case = CaseStateMachine.transition(
        case,
        CaseStatus.COMPLETE,
        validate=False
    )
    assert updated_case.status == CaseStatus.COMPLETE


def test_completion_timestamp():
    """Test that completion timestamp is set."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        status=CaseStatus.IN_PROGRESS,
    )

    assert case.completed_at is None

    updated_case = CaseStateMachine.transition(case, CaseStatus.COMPLETE)
    assert updated_case.completed_at is not None
    assert isinstance(updated_case.completed_at, datetime)


def test_auto_transition_loa_complete():
    """Test auto-transition for completed LoA case."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        status=CaseStatus.IN_PROGRESS,
        required_fields=["DOB", "NI number"],
    )

    # Add all required fields
    from src.core.models import FieldValue
    case.received_fields["DOB"] = FieldValue(
        field_name="DOB",
        value="01/01/1980",
        received_at=datetime.utcnow(),
        source_message_id="msg1",
    )
    case.received_fields["NI number"] = FieldValue(
        field_name="NI number",
        value="AB123456C",
        received_at=datetime.utcnow(),
        source_message_id="msg2",
    )

    # Should suggest transition to COMPLETE
    suggested_status = CaseStateMachine.should_auto_transition(case)
    assert suggested_status == CaseStatus.COMPLETE


def test_auto_transition_awaiting_info():
    """Test auto-transition to AWAITING_INFO when fields missing."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        status=CaseStatus.IN_PROGRESS,
        required_fields=["DOB", "NI number", "Plan number"],
    )

    # Add only one field
    from src.core.models import FieldValue
    case.received_fields["DOB"] = FieldValue(
        field_name="DOB",
        value="01/01/1980",
        received_at=datetime.utcnow(),
        source_message_id="msg1",
    )

    # Should suggest transition to AWAITING_INFO
    suggested_status = CaseStateMachine.should_auto_transition(case)
    assert suggested_status == CaseStatus.AWAITING_INFO


def test_terminal_states():
    """Test terminal state detection."""
    assert CaseStateMachine.is_terminal_state(CaseStatus.COMPLETE)
    assert CaseStateMachine.is_terminal_state(CaseStatus.CANCELLED)
    assert not CaseStateMachine.is_terminal_state(CaseStatus.OPEN)
    assert not CaseStateMachine.is_terminal_state(CaseStatus.IN_PROGRESS)


def test_get_next_states():
    """Test getting valid next states."""
    next_states = CaseStateMachine.get_next_states(CaseStatus.OPEN)
    assert CaseStatus.IN_PROGRESS in next_states
    assert CaseStatus.CANCELLED in next_states
    assert CaseStatus.COMPLETE not in next_states

    next_states = CaseStateMachine.get_next_states(CaseStatus.COMPLETE)
    assert len(next_states) == 0  # Terminal state
