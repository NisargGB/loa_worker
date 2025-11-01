"""
Pipeline orchestrator for message processing.
"""
import time
from typing import List, Optional

from rich.progress import Progress

from actions.router import ActionRouter
from core.enums import MessageCategory, ProcessingStatus
from core.models import (BatchProcessingResult, Classification, Message,
                         ProcessingResult)
from llm.service import LLMService
from pipeline.pre_filter import PreFilter
from storage.audit_repository import AuditRepository
from storage.case_repository import CaseRepository


class PipelineOrchestrator:
    """
    Orchestrates the entire message processing pipeline.

    Pipeline flow:
    1. Pre-filter (fast rejection of spam)
    2. Classify message (LLM)
    3. Extract entities (LLM)
    4. Match/find existing case
    5. Determine action (LLM)
    6. Execute action
    7. Log and audit
    """

    def __init__(
        self,
        llm_service: LLMService,
        case_repo: CaseRepository,
        audit_repo: AuditRepository,
        pre_filter: Optional[PreFilter] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            llm_service: LLM service for classification and extraction
            case_repo: Case repository
            audit_repo: Audit repository
            pre_filter: Optional pre-filter for fast message filtering
        """
        self.llm_service = llm_service
        self.case_repo = case_repo
        self.audit_repo = audit_repo
        self.pre_filter = pre_filter or PreFilter()
        self.action_router = ActionRouter(case_repo, audit_repo, llm_service)

    async def process_message(self, message: Message) -> ProcessingResult:
        """
        Process a single message through the pipeline.

        Args:
            message: Message to process

        Returns:
            Processing result
        """
        start_time = time.time()

        try:
            # Step 1: Pre-filter
            if not self.pre_filter.should_process(message):
                return ProcessingResult(
                    message_id=message.id,
                    success=True,
                    classification=Classification(
                        category=MessageCategory.IRRELEVANT,
                        confidence=1.0,
                        reasoning="Filtered out by pre-filter (spam/marketing)",
                        is_relevant=False,
                    ),
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Step 2: Classify
            classification = await self.llm_service.classify_message(message)

            if not classification.should_process:
                return ProcessingResult(
                    message_id=message.id,
                    success=True,
                    classification=classification,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Step 3: Extract entities
            entities = await self.llm_service.extract_entities(message, classification)

            # Step 4: Find existing case if referenced
            existing_case = None
            if entities.client_name:
                existing_case = await self.case_repo.find_case_by_client_and_title(
                    client_name=entities.client_name,
                    case_title=entities.case_title,
                )

            # Step 5: Determine action
            action = await self.llm_service.determine_action(
                message=message,
                classification=classification,
                entities=entities,
                existing_case=existing_case,
            )

            # If we found an existing case, associate action with it
            if existing_case and not action.case_id:
                action.case_id = existing_case.id

            # Step 6: Execute action
            actions_taken = []
            if action.type.value != "IGNORE":
                success = await self.action_router.route_action(action)
                action.success = success
                actions_taken.append(action)

            # Step 7: Update message status
            message.processing_status = ProcessingStatus.PROCESSED

            return ProcessingResult(
                message_id=message.id,
                success=True,
                classification=classification,
                extracted_entities=entities,
                actions_taken=actions_taken,
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            # Log error
            print(f"Error processing message {message.id}: {e}")

            message.processing_status = ProcessingStatus.FAILED

            return ProcessingResult(
                message_id=message.id,
                success=False,
                error_message=str(e),
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    async def process_batch(self, messages: List[Message]) -> BatchProcessingResult:
        """
        Process a batch of messages.

        Args:
            messages: List of messages to process

        Returns:
            Batch processing result with statistics
        """
        start_time = time.time()

        results = []
        processed_count = 0
        failed_count = 0
        skipped_count = 0

        with Progress() as progress:
            task = progress.add_task("[cyan]Processing messages...", total=len(messages))
            for message in messages:
                result = await self.process_message(message)
                results.append(result)
                progress.update(task, completed=len(results))

                if result.success:
                    if result.classification and result.classification.should_process:
                        processed_count += 1
                    else:
                        skipped_count += 1
                else:
                    failed_count += 1

        total_time_ms = (time.time() - start_time) * 1000

        return BatchProcessingResult(
            total_messages=len(messages),
            processed=processed_count,
            failed=failed_count,
            skipped=skipped_count,
            results=results,
            total_time_ms=total_time_ms,
        )

    async def validate_result(self, message: Message, result: ProcessingResult) -> dict:
        """
        Validate processing result against expected values (for testing).

        Args:
            message: Original message with expected values in metadata
            result: Processing result

        Returns:
            Dictionary with validation results
        """
        validation = {
            "message_id": message.id,
            "passed": True,
            "errors": [],
        }

        metadata = message.metadata

        # Validate classification
        if expected_category := metadata.get("expected_category"):
            if result.classification and result.classification.category.value != expected_category:
                validation["passed"] = False
                validation["errors"].append(
                    f"Category mismatch: expected {expected_category}, "
                    f"got {result.classification.category.value}"
                )

        # Validate action
        if expected_action := metadata.get("expected_action"):
            if result.actions_taken:
                actual_action = result.actions_taken[0].type.value
                if actual_action != expected_action:
                    validation["passed"] = False
                    validation["errors"].append(
                        f"Action mismatch: expected {expected_action}, got {actual_action}"
                    )
            else:
                validation["passed"] = False
                validation["errors"].append(
                    f"No action taken, expected {expected_action}"
                )

        # Validate client name
        if expected_client := metadata.get("expected_client_name"):
            if result.extracted_entities:
                actual_client = result.extracted_entities.client_name
                if actual_client != expected_client:
                    validation["passed"] = False
                    validation["errors"].append(
                        f"Client name mismatch: expected {expected_client}, got {actual_client}"
                    )

        return validation
