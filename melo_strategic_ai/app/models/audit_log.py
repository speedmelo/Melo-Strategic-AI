from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    risks_found = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)