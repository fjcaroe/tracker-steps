from sqlalchemy import Boolean, Column, Integer, Text, TIMESTAMP, func

from app.db.base import Base


class Implement(Base):
    __tablename__ = "implements"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
