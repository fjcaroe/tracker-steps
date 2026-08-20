from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP

from app.db.base import Base


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64))
    name = Column(Text, nullable=False)
    rut = Column(String(20))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True))
