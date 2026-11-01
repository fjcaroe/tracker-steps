"""Transport manifests owned by Tracker; references reuse operational masters."""
import uuid
from sqlalchemy import Column, Integer, Float, Text, ForeignKey, DateTime, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class PassengerService(Base):
    __tablename__ = 'mobile_passenger_services'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    route_id = Column(UUID(as_uuid=True), ForeignKey('mobile_routes.id'), nullable=False)
    driver_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    # Historic capacity at scheduling, never inferred from the manifest size.
    capacity = Column(Integer, nullable=False)
    payload_hash = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (CheckConstraint('capacity BETWEEN 1 AND 250', name='passenger_service_capacity'),)


class ServiceStop(Base):
    __tablename__ = 'mobile_service_stops'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey('mobile_passenger_services.id'), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    lat = Column(Float)
    lon = Column(Float)
    __table_args__ = (UniqueConstraint('service_id','position', name='service_stop_position'),)


class ServicePassenger(Base):
    __tablename__ = 'mobile_service_passengers'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id = Column(UUID(as_uuid=True), ForeignKey('mobile_passenger_services.id'), nullable=False, index=True)
    name = Column(Text, nullable=False)
    document = Column(Text, nullable=False)
    document_key = Column(Text, nullable=False)
    boarding_stop_id = Column(UUID(as_uuid=True), ForeignKey('mobile_service_stops.id'), nullable=False)
    alighting_stop_id = Column(UUID(as_uuid=True), ForeignKey('mobile_service_stops.id'), nullable=False)
    seat = Column(Integer)
    __table_args__ = (UniqueConstraint('service_id','document_key', name='service_passenger_document'),
                     CheckConstraint('seat IS NULL OR seat > 0', name='service_passenger_seat'))
