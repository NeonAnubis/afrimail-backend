from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid

from app.db.session import Base


class ScheduledAction(Base):
    """Automated task queue."""
    __tablename__ = "scheduled_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action_type = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_ids = Column(JSONB, default=[])
    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(String, default="pending", index=True)  # pending, completed, failed, cancelled
    action_data = Column(JSONB, default={})
    created_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ScheduledAction {self.action_type} - {self.status}>"


class BulkImportLog(Base):
    """CSV import functionality logs."""
    __tablename__ = "bulk_import_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String, nullable=False)
    total_rows = Column(Integer, default=0)
    successful_imports = Column(Integer, default=0)
    failed_imports = Column(Integer, default=0)
    error_details = Column(JSONB, default=[])
    imported_by = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<BulkImportLog {self.filename}>"
