"""
Repository for audit logging in Firestore.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from google.cloud.firestore import FieldFilter

from core.enums import ActionType
from core.exceptions import StorageError
from core.models import AuditLog

if TYPE_CHECKING:
    from google.cloud.firestore import AsyncClient


class AuditRepository:
    """Repository for managing audit logs in Firestore."""

    COLLECTION_NAME = "audit_logs"

    def __init__(self, firestore_client: "AsyncClient"):
        """
        Initialize the repository.

        Args:
            firestore_client: Firestore async client
        """
        self.db = firestore_client
        self.collection = self.db.collection(self.COLLECTION_NAME)

    async def log_action(self, audit_log: AuditLog) -> AuditLog:
        """
        Log an action to the audit trail.

        Args:
            audit_log: Audit log entry

        Returns:
            Created audit log with ID

        Raises:
            StorageError: If logging fails
        """
        try:
            # Generate ID if not provided
            if not audit_log.id:
                audit_log.id = f"audit_{datetime.utcnow().timestamp()}"

            # Convert to dictionary
            log_dict = audit_log.model_dump()

            # Store in Firestore
            await self.collection.document(audit_log.id).set(log_dict)

            return audit_log

        except Exception as e:
            raise StorageError(f"Failed to log action: {e}")

    async def get_case_audit_trail(
        self,
        case_id: str,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit trail for a specific case.

        Args:
            case_id: Case ID
            limit: Maximum number of entries to return

        Returns:
            List of audit logs ordered by timestamp (newest first)

        Raises:
            StorageError: If retrieval fails
        """
        try:
            query = (
                self.collection
                .where(filter=FieldFilter("case_id", "==", case_id))
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
            )

            logs = []
            async for doc in query.stream():
                logs.append(AuditLog(**doc.to_dict()))

            return logs

        except Exception as e:
            raise StorageError(f"Failed to get audit trail: {e}")

    async def get_recent_logs(
        self,
        limit: int = 100,
        action_type: Optional[ActionType] = None,
    ) -> List[AuditLog]:
        """
        Get recent audit logs across all cases.

        Args:
            limit: Maximum number of entries to return
            action_type: Optional filter by action type

        Returns:
            List of audit logs ordered by timestamp (newest first)

        Raises:
            StorageError: If retrieval fails
        """
        try:
            query = self.collection

            if action_type:
                query = query.where(filter=FieldFilter("action_type", "==", action_type.value))

            query = query.order_by("timestamp", direction="DESCENDING").limit(limit)

            logs = []
            async for doc in query.stream():
                logs.append(AuditLog(**doc.to_dict()))

            return logs

        except Exception as e:
            raise StorageError(f"Failed to get recent logs: {e}")

    async def get_failed_actions(
        self,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit logs for failed actions.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of failed action audit logs

        Raises:
            StorageError: If retrieval fails
        """
        try:
            query = (
                self.collection
                .where(filter=FieldFilter("success", "==", False))
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
            )

            logs = []
            async for doc in query.stream():
                logs.append(AuditLog(**doc.to_dict()))

            return logs

        except Exception as e:
            raise StorageError(f"Failed to get failed actions: {e}")
