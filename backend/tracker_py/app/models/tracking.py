import enum
import uuid
from sqlalchemy import Column, Integer, Text, Numeric, TIMESTAMP, Enum, ForeignKey, BigInteger, JSON, Float 
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.sql import func

from app.db.base import Base

class TrackingStatus(str, enum.Enum):
    open = "open"
    closed = "closed"

class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    started_at = Column(TIMESTAMP(timezone=True), nullable=False)
    ended_at = Column(TIMESTAMP(timezone=True))
    status = Column(Enum(TrackingStatus), nullable=False, default=TrackingStatus.open)

    total_distance_m = Column(Numeric(12, 2))
    avg_speed_kmh = Column(Numeric(8, 2))

    created_at = Column(TIMESTAMP(timezone=True))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))

    work_order = relationship("WorkOrder")
    machine = relationship("Machine")
    driver = relationship("Driver")
    cost_center = relationship("CostCenter")
    points = relationship("TrackingPoint", back_populates="session")
    points_count = Column(BigInteger, nullable=False, default=0)
    last_point_ts = Column(TIMESTAMP(timezone=True))
    last_lat = Column(Float)
    last_lon = Column(Float)
    last_speed_mps = Column(Float)
    last_accuracy_m = Column(Float)
    
class TrackingPoint(Base):
    __tablename__ = "tracking_points"

    id = Column(BigInteger, primary_key=True)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"), nullable=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False)
    lat = Column(Numeric(10, 7), nullable=False)
    lon = Column(Numeric(10, 7), nullable=False)
    speed_mps = Column(Numeric(10, 4))
    accuracy_m = Column(Numeric(10, 4))
    extra = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True))

    session = relationship("TrackingSession", back_populates="points")

class TrackingLot(Base):
    __tablename__ = "tracking_lots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"), nullable=False)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    session = relationship("TrackingSession")
    cost_center = relationship("CostCenter")
    machine = relationship("Machine")
    driver = relationship("Driver")
