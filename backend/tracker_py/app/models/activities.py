from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, Numeric, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    code = Column(String(32))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Labor(Base):
    __tablename__ = "labors"

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    name = Column(Text, nullable=False)
    code = Column(String(32))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    effort_factor = Column(Numeric(6, 3))
    target_speed_kmh = Column(Numeric(8, 2))

    activity = relationship("Activity")
