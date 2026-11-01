import uuid
from sqlalchemy import Column, Integer, Text, Float, Boolean, ForeignKey, Numeric, JSON, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base


class MobileIncident(Base):
    """Incidencia reportada desde Steps Móvil (falla, accidente, daño, robo, SOS)."""
    __tablename__ = "mobile_incidents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"))
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    category = Column(Text, nullable=False)  # breakdown | accident | damage | theft | sos | other
    note = Column(Text)
    lat = Column(Float)
    lon = Column(Float)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    photo_path = Column(Text)
    status = Column(Text, nullable=False, default="open")  # open | attended | closed
    handled_by = Column(Integer, ForeignKey("users.id"))
    handled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MobileChecklist(Base):
    __tablename__ = "mobile_checklists"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    items = Column(JSON, nullable=False)
    all_ok = Column(Boolean, nullable=False, default=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MobileExpense(Base):
    """Carga de combustible, peaje u otro gasto de la jornada."""
    __tablename__ = "mobile_expenses"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(PG_UUID(as_uuid=True), ForeignKey("tracking_sessions.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"))
    kind = Column(Text, nullable=False)  # fuel | toll | other
    liters = Column(Numeric(10, 2))
    amount = Column(Numeric(14, 2))
    station = Column(Text)
    odometer = Column(Numeric(12, 2))
    note = Column(Text)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    photo_path = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MobileDevice(Base):
    """Última señal de cada usuario/teléfono: versión de la app y última sincronización."""
    __tablename__ = "mobile_devices"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    version = Column(Text)
    platform = Column(Text)
    pending = Column(Integer)
    last_sync_at = Column(DateTime(timezone=True))
    last_seen_at = Column(DateTime(timezone=True), nullable=False)


class MobileDiagnostic(Base):
    __tablename__ = "mobile_diagnostics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version = Column(Text)
    message = Column(Text)
    log = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MobileRoute(Base):
    """Ruta asignada por un supervisor a una máquina: lista ordenada de puntos que el conductor sigue en el mapa."""
    __tablename__ = "mobile_routes"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False)
    waypoints = Column(JSON, nullable=False)  # [{lat, lon, label?}]
    note = Column(Text)
    status = Column(Text, nullable=False, default="assigned")  # assigned | in_progress | done | cancelled
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))
