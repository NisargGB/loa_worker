"""
Unit tests for core models.
"""
import pytest
from datetime import datetime
from src.core.models import Case, FieldValue, Message, EmailContent
from src.core.enums import CaseType, CaseStatus, SourceType, ProcessingStatus


def test_case_creation():
    """Test creating a basic case."""
    case = Case(
        id="test_case_1",
        client_name="John Doe",
        case_title="LoA for John Doe",
        case_type=CaseType.LOA,
        required_fields=["DOB", "NI number", "Plan number"],
    )

    assert case.id == "test_case_1"
    assert case.client_name == "John Doe"
    assert case.status == CaseStatus.OPEN
    assert len(case.required_fields) == 3
    assert len(case.received_fields) == 0


def test_case_completion_check():
    """Test case completion logic."""
    case = Case(
        id="test_case",
        client_name="Jane Smith",
        case_title="LoA Case",
        case_type=CaseType.LOA,
        required_fields=["DOB", "NI number"],
    )

    # Initially not complete
    assert not case.is_complete()
    assert case.get_completion_percentage() == 0.0

    # Add one field
    case.received_fields["DOB"] = FieldValue(
        field_name="DOB",
        value="01/01/1990",
        received_at=datetime.utcnow(),
        source_message_id="msg1",
    )

    assert not case.is_complete()
    assert case.get_completion_percentage() == 50.0

    # Add second field
    case.received_fields["NI number"] = FieldValue(
        field_name="NI number",
        value="AB123456C",
        received_at=datetime.utcnow(),
        source_message_id="msg2",
    )

    assert case.is_complete()
    assert case.get_completion_percentage() == 100.0


def test_case_missing_fields():
    """Test getting missing fields."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        required_fields=["DOB", "NI number", "Plan number"],
    )

    missing = case.get_missing_fields()
    assert set(missing) == {"DOB", "NI number", "Plan number"}

    # Add a field
    case.received_fields["DOB"] = FieldValue(
        field_name="DOB",
        value="01/01/1990",
        received_at=datetime.utcnow(),
        source_message_id="msg1",
    )

    missing = case.get_missing_fields()
    assert set(missing) == {"NI number", "Plan number"}


def test_message_text_extraction():
    """Test extracting text from different message types."""
    # Email message
    email_msg = Message(
        id="email_1",
        timestamp=datetime.utcnow(),
        source_type=SourceType.EMAIL,
        content=EmailContent(
            from_address="sender@example.com",
            to_address="receiver@example.com",
            subject="Test Subject",
            body="Test body content",
        ),
    )

    text = email_msg.get_text_content()
    assert "Test Subject" in text
    assert "Test body content" in text


def test_general_case_completion():
    """Test that general cases don't check fields for completion."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="General Case",
        case_type=CaseType.GENERAL,
        status=CaseStatus.IN_PROGRESS,
        required_fields=[],  # No required fields
    )

    # Not complete even with no required fields
    assert not case.is_complete()

    # Only complete when explicitly set to COMPLETE status
    case.status = CaseStatus.COMPLETE
    assert case.is_complete()


def test_field_value():
    """Test field value model."""
    field = FieldValue(
        field_name="DOB",
        value="01/01/1990",
        received_at=datetime.utcnow(),
        source_message_id="msg123",
        confidence=0.95,
    )

    assert field.field_name == "DOB"
    assert field.value == "01/01/1990"
    assert field.confidence == 0.95
    assert field.source_message_id == "msg123"


def test_case_with_no_required_fields():
    """Test LoA case with no required fields is always complete."""
    case = Case(
        id="test_case",
        client_name="Test Client",
        case_title="Test Case",
        case_type=CaseType.LOA,
        required_fields=[],
    )

    assert case.is_complete()
    assert case.get_completion_percentage() == 100.0
    assert case.get_missing_fields() == []
