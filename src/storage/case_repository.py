"""
Repository for case management in Firestore.
"""
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from google.cloud.firestore import FieldFilter

from core.enums import CaseStatus, CaseType
from core.exceptions import CaseNotFoundError, StorageError
from core.models import Case, FieldValue, Task

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient


class CaseRepository:
    """Repository for managing cases in Firestore."""

    COLLECTION_NAME = "cases"
    TASKS_SUBCOLLECTION = "tasks"

    def __init__(self, firestore_client: "AsyncClient"):
        """
        Initialize the repository.

        Args:
            firestore_client: Firestore async client
        """
        self.db = firestore_client
        self.collection = self.db.collection(self.COLLECTION_NAME)

    async def create_case(self, case: Case) -> Case:
        """
        Create a new case.

        Args:
            case: Case to create

        Returns:
            Created case with ID

        Raises:
            StorageError: If creation fails
        """
        try:
            # Generate ID if not provided
            if not case.id:
                case.id = f"case_{datetime.utcnow().timestamp()}"

            # Convert to dictionary
            case_dict = case.model_dump()

            # Store in Firestore
            await self.collection.document(case.id).set(case_dict)

            return case

        except Exception as e:
            raise StorageError(f"Failed to create case: {e}")

    async def get_case(self, case_id: str) -> Case:
        """
        Retrieve a case by ID.

        Args:
            case_id: Case ID

        Returns:
            Case object

        Raises:
            CaseNotFoundError: If case doesn't exist
        """
        try:
            doc = await self.collection.document(case_id).get()

            if not doc.exists:
                raise CaseNotFoundError(f"Case not found: {case_id}")

            return Case(**doc.to_dict())

        except CaseNotFoundError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to get case: {e}")

    async def update_case(self, case: Case) -> Case:
        """
        Update an existing case.

        Args:
            case: Case with updated data

        Returns:
            Updated case

        Raises:
            CaseNotFoundError: If case doesn't exist
            StorageError: If update fails
        """
        try:
            # Verify case exists
            await self.get_case(case.id)

            # Update timestamp
            case.updated_at = datetime.utcnow()

            # Convert to dictionary
            case_dict = case.model_dump()

            # Update in Firestore
            await self.collection.document(case.id).set(case_dict)

            return case

        except Exception as e:
            raise StorageError(f"Failed to update case: {e}")

    async def delete_case(self, case_id: str) -> None:
        """
        Delete a case.

        Args:
            case_id: Case ID

        Raises:
            StorageError: If deletion fails
        """
        try:
            await self.collection.document(case_id).delete()
        except Exception as e:
            raise StorageError(f"Failed to delete case: {e}")

    async def find_case_by_client_and_title(
        self,
        client_name: str,
        case_title: Optional[str] = None,
    ) -> Optional[Case]:
        """
        Find a case by client name and optionally case title.

        Args:
            client_name: Client name
            case_title: Optional case title for more specific matching

        Returns:
            Case if found, None otherwise
        """
        try:
            query = self.collection.where(filter=FieldFilter("client_name", "==", client_name))

            if case_title:
                query = query.where(filter=FieldFilter("case_title", "==", case_title))

            # Get only open/in-progress cases
            query = query.where(filter=FieldFilter("status", "in", [
                CaseStatus.OPEN.value,
                CaseStatus.IN_PROGRESS.value,
                CaseStatus.AWAITING_INFO.value,
            ]))

            docs = query.limit(1).stream()

            async for doc in docs:
                return Case(**doc.to_dict())

            return None

        except Exception as e:
            raise StorageError(f"Failed to find case: {e}")

    async def list_cases(
        self,
        status: Optional[CaseStatus] = None,
        case_type: Optional[CaseType] = None,
        limit: int = 100,
    ) -> List[Case]:
        """
        List cases with optional filters.

        Args:
            status: Filter by status
            case_type: Filter by case type
            limit: Maximum number of cases to return

        Returns:
            List of cases
        """
        try:
            query = self.collection

            if status:
                query = query.where(filter=FieldFilter("status", "==", status.value))

            if case_type:
                query = query.where(filter=FieldFilter("case_type", "==", case_type.value))

            query = query.order_by("updated_at", direction="DESCENDING").limit(limit)

            cases = []
            async for doc in query.stream():
                cases.append(Case(**doc.to_dict()))

            return cases

        except Exception as e:
            raise StorageError(f"Failed to list cases: {e}")

    async def add_field_to_case(
        self,
        case_id: str,
        field_value: FieldValue,
    ) -> Case:
        """
        Add or update a field in a case.

        Args:
            case_id: Case ID
            field_value: Field value to add

        Returns:
            Updated case

        Raises:
            CaseNotFoundError: If case doesn't exist
        """
        case = await self.get_case(case_id)

        # Add field to received_fields
        case.received_fields[field_value.field_name] = field_value
        case.updated_at = datetime.utcnow()

        # Check if case is complete after adding field
        if case.is_complete() and case.status != CaseStatus.COMPLETE:
            case.status = CaseStatus.COMPLETE
            case.completed_at = datetime.utcnow()

        return await self.update_case(case)

    async def create_task(self, task: Task) -> Task:
        """
        Create a task (standalone or linked to a case).

        Args:
            task: Task to create

        Returns:
            Created task

        Raises:
            StorageError: If creation fails
        """
        try:
            # Generate ID if not provided
            if not task.id:
                task.id = f"task_{datetime.utcnow().timestamp()}"

            task_dict = task.model_dump()

            if task.case_id:
                # Store as subcollection of case
                case_ref = self.collection.document(task.case_id)
                await case_ref.collection(self.TASKS_SUBCOLLECTION).document(task.id).set(task_dict)
            else:
                # Store in separate tasks collection
                await self.db.collection("tasks").document(task.id).set(task_dict)

            return task

        except Exception as e:
            raise StorageError(f"Failed to create task: {e}")

    async def update_task(self, task: Task) -> Task:
        """
        Update a task.

        Args:
            task: Task with updated data

        Returns:
            Updated task

        Raises:
            StorageError: If update fails
        """
        try:
            task.updated_at = datetime.utcnow()
            task_dict = task.model_dump()

            if task.case_id:
                case_ref = self.collection.document(task.case_id)
                await case_ref.collection(self.TASKS_SUBCOLLECTION).document(task.id).set(task_dict)
            else:
                await self.db.collection("tasks").document(task.id).set(task_dict)

            return task

        except Exception as e:
            raise StorageError(f"Failed to update task: {e}")

    async def find_task_by_title(
        self,
        task_title: str,
        case_id: Optional[str] = None,
    ) -> Optional[Task]:
        """
        Find a task by title.

        Args:
            task_title: Task title
            case_id: Optional case ID to search within

        Returns:
            Task if found, None otherwise
        """
        try:
            if case_id:
                case_ref = self.collection.document(case_id)
                query = case_ref.collection(self.TASKS_SUBCOLLECTION).where(filter=FieldFilter("title", "==", task_title))
            else:
                query = self.db.collection("tasks").where(filter=FieldFilter("title", "==", task_title))

            query = query.where(filter=FieldFilter("status", "!=", CaseStatus.COMPLETE.value)).limit(1)

            async for doc in query.stream():
                return Task(**doc.to_dict())

            return None

        except Exception as e:
            raise StorageError(f"Failed to find task: {e}")
