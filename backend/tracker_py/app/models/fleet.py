"""Isolated GPS domain. Legacy session tables keep their original meaning."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Date, DateTime, JSON, ForeignKey, UniqueConstraint, Index
from app.db.base import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = 'gps_tenants'
    id = Column(String(36), primary_key=True, default=uid)
    issuer = Column(String(100), nullable=False)
    company_id = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    timezone = Column(String(80), nullable=False, default='America/Santiago')
    retention_days = Column(Integer, nullable=False, default=365)
    __table_args__ = (UniqueConstraint('issuer', 'company_id'),)


class Asset(Base):
    __tablename__ = 'gps_assets'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    source_id = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    plate = Column(String(40))
    type = Column(String(50), nullable=False, default='vehicle')
    cost_center = Column(String(200))
    responsible = Column(String(200))
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (UniqueConstraint('tenant_id', 'source_id'),)


class Device(Base):
    __tablename__ = 'gps_devices'
    id = Column(String(36), primary_key=True, default=uid)
    imei = Column(String(32), nullable=False, unique=True)
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    firmware = Column(String(100))
    protocol = Column(String(100))
    freshness_seconds = Column(Integer, nullable=False, default=300)
    tracking_approved = Column(Boolean, nullable=False, default=False)
    # Physical control is deliberately not enabled by a database flag.


class Assignment(Base):
    __tablename__ = 'gps_assignments'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey('gps_devices.id'), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey('gps_assets.id'), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True))


class DeviceRegistration(Base):
    __tablename__ = 'gps_device_registrations'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey('gps_devices.id'), nullable=False, unique=True)
    phone = Column(String(40))
    operator = Column(String(100))
    plan_type = Column(String(20), nullable=False, default='prepaid')
    apn = Column(String(100))
    responsible = Column(String(200))
    last_recharged_on = Column(Date)
    next_recharge_on = Column(Date)
    data_expires_on = Column(Date)
    line_review_on = Column(Date)
    reminder_days = Column(Integer, nullable=False, default=7)
    notes = Column(String(1000))
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Position(Base):
    __tablename__ = 'gps_positions'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False)
    device_id = Column(String(36), ForeignKey('gps_devices.id'), nullable=False)
    asset_id = Column(String(36), ForeignKey('gps_assets.id'), nullable=False)
    assignment_id = Column(String(36), ForeignKey('gps_assignments.id'), nullable=False)
    source_id = Column(String(200), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=now)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    speed_kmh = Column(Float)
    quality = Column(String(30), nullable=False, default='unknown')
    acc = Column(Boolean)
    external_power = Column(Boolean)
    sos = Column(Boolean)
    __table_args__ = (UniqueConstraint('device_id', 'source_id'), Index('gps_position_asset_time', 'tenant_id', 'asset_id', 'recorded_at', 'id'))


class Policy(Base):
    __tablename__ = 'gps_security_policies'
    asset_id = Column(String(36), ForeignKey('gps_assets.id'), primary_key=True)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    armed = Column(Boolean, nullable=False, default=False)
    version = Column(Integer, nullable=False, default=1)
    contacts = Column(JSON, nullable=False, default=list)
    zone = Column(JSON)
    # UTC hours in which operation is authorized; empty means no authorized hours.
    allowed_hours_utc = Column(JSON, nullable=False, default=list)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Incident(Base):
    __tablename__ = 'gps_security_incidents'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey('gps_assets.id'), nullable=False)
    type = Column(String(40), nullable=False)
    severity = Column(String(20), nullable=False)
    state = Column(String(30), nullable=False, default='open')
    responsible = Column(String(200))
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Audit(Base):
    __tablename__ = 'gps_audit_events'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    incident_id = Column(String(36), ForeignKey('gps_security_incidents.id'))
    asset_id = Column(String(36))
    actor = Column(String(200), nullable=False)
    action = Column(String(80), nullable=False)
    detail = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)


class Preference(Base):
    __tablename__ = 'gps_view_preferences'
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), primary_key=True)
    user_id = Column(String(200), primary_key=True)
    view_key = Column(String(80), primary_key=True)
    value = Column(JSON, nullable=False)


class Command(Base):
    __tablename__ = 'gps_device_commands'
    id = Column(String(36), primary_key=True, default=uid)
    tenant_id = Column(String(36), ForeignKey('gps_tenants.id'), nullable=False, index=True)
    incident_id = Column(String(36), ForeignKey('gps_security_incidents.id'), nullable=False)
    intention_id = Column(String(100), nullable=False)
    type = Column(String(40), nullable=False)
    requester = Column(String(200), nullable=False)
    reason = Column(String(2000), nullable=False)
    state = Column(String(30), nullable=False, default='failed')
    result = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now)
    __table_args__ = (UniqueConstraint('tenant_id', 'intention_id'),)
