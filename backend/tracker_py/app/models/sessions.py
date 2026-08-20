import uuid
from sqlalchemy import Column, Integer, BigInteger, ForeignKey, Numeric, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Float, DateTime, func

from app.db.base import Base
from app.models.enums import TrackingStatus


class TrackingSession(Base):
    __tablename__ = "tracking_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))

    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))

    status = Column(Enum(TrackingStatus), nullable=False, default=TrackingStatus.open)

    total_distance_m = Column(Numeric(12, 2))
    avg_speed_kmh = Column(Numeric(8, 2))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # cached stats
    points_count = Column(Integer, nullable=False, default=0)
    last_point_ts = Column(DateTime(timezone=True))
    last_lat = Column(Float)
    last_lon = Column(Float)
    last_speed_mps = Column(Float)
    last_accuracy_m = Column(Float)

    # relations
    work_order = relationship("WorkOrder")
    machine = relationship("Machine")
    driver = relationship("Driver")
    cost_center = relationship("CostCenter")
    points = relationship(
        "TrackingPoint",
        back_populates="session",
        passive_deletes=True, 
    )


class TrackingPoint(Base):
    __tablename__ = "tracking_points"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("tracking_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    ts = Column(DateTime(timezone=True), nullable=False)

    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    speed_mps = Column(Float)
    accuracy_m = Column(Float)

    extra = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TrackingSession", back_populates="points")


class TrackingLot(Base):
    __tablename__ = "tracking_lots"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)

    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"), nullable=False)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TrackingSession")
    cost_center = relationship("CostCenter")
    machine = relationship("Machine")
    driver = relationship("Driver")
