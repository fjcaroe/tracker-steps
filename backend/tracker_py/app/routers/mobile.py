"""Endpoints de Steps Móvil: checklist, incidencias, gastos de ruta, estado de dispositivos y diagnóstico.

Todos los POST con id de cliente son idempotentes: la app los envía desde una cola sin conexión y un
reintento no duplica registros. Las fotos viajan como base64 (JPEG comprimido en el teléfono) y se
guardan fuera del directorio público; se sirven solo con sesión.
"""
import base64
import binascii
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PField
from sqlalchemy.orm import Session

from app.core.security import allowed_cost_center_ids, assert_cost_center_access, get_current_user
from app.db.session import get_db
from app.models.machines import Machine
from app.models.mobile import MobileChecklist, MobileDevice, MobileDiagnostic, MobileExpense, MobileIncident, MobileRoute
from app.models.sessions import TrackingSession
from app.models.users import User

router = APIRouter(prefix="/mobile", tags=["mobile"])

MEDIA_DIR = os.getenv("MOBILE_MEDIA_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "media")
MAX_PHOTO_BYTES = 3 * 1024 * 1024
INCIDENT_CATEGORIES = {"breakdown", "accident", "damage", "theft", "sos", "other"}
EXPENSE_KINDS = {"fuel", "toll", "other"}
INCIDENT_STATUSES = {"open", "attended", "closed"}

DEFAULT_CHECKLIST = [
    {"key": "lights", "label": "Luces y señalización"},
    {"key": "brakes", "label": "Frenos"},
    {"key": "tires", "label": "Neumáticos (presión y desgaste)"},
    {"key": "oil", "label": "Nivel de aceite y refrigerante"},
    {"key": "leaks", "label": "Sin fugas de aceite o combustible"},
    {"key": "extinguisher", "label": "Extintor vigente"},
    {"key": "belt", "label": "Cinturón de seguridad y asiento"},
    {"key": "mirrors", "label": "Espejos y parabrisas"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _save_photo(kind: str, record_id: uuid.UUID, data: Optional[str]) -> Optional[str]:
    if not data:
        return None
    if "," in data[:100]:
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data, validate=False)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="La foto no es válida.")
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=400, detail="La foto está vacía o supera los 3 MB.")
    if not (raw.startswith(b"\xff\xd8\xff") or raw.startswith(b"\x89PNG") or raw[8:12] == b"WEBP"):
        raise HTTPException(status_code=400, detail="La foto debe ser JPEG, PNG o WebP.")
    folder = os.path.join(MEDIA_DIR, kind)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{record_id}.img")
    with open(path, "wb") as fh:
        fh.write(raw)
    return path


def _machine_cc(db: Session, machine_id: Optional[int], session_id: Optional[uuid.UUID]) -> Optional[int]:
    if session_id is not None:
        s = db.get(TrackingSession, session_id)
        if s is not None:
            return s.cost_center_id
    if machine_id is not None:
        m = db.get(Machine, machine_id)
        if m is not None:
            return m.cost_center_id
    return None


def _check_access(db: Session, user: User, machine_id: Optional[int], session_id: Optional[uuid.UUID]) -> Optional[int]:
    cc = _machine_cc(db, machine_id, session_id)
    if cc is not None or not user.is_admin:
        assert_cost_center_access(db, user, cc)
    return cc


# ---------------------------------------------------------------- Checklist (I5)
class ChecklistItem(BaseModel):
    key: str
    label: str
    ok: bool
    note: Optional[str] = None


class ChecklistIn(BaseModel):
    id: uuid.UUID
    machine_id: int
    session_id: Optional[uuid.UUID] = None
    items: List[ChecklistItem] = PField(..., min_length=1)
    occurred_at: Optional[datetime] = None


@router.get("/checklist_template")
def checklist_template(machine_id: Optional[int] = None, current: User = Depends(get_current_user)):
    return {"machine_id": machine_id, "items": DEFAULT_CHECKLIST}


@router.post("/checklists")
def create_checklist(payload: ChecklistIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    existing = db.get(MobileChecklist, payload.id)
    if existing is not None:
        return {"id": str(existing.id), "all_ok": existing.all_ok}
    _check_access(db, current, payload.machine_id, payload.session_id)
    row = MobileChecklist(
        id=payload.id, user_id=current.id, session_id=payload.session_id, machine_id=payload.machine_id,
        items=[i.model_dump() for i in payload.items], all_ok=all(i.ok for i in payload.items),
        occurred_at=payload.occurred_at or _now(),
    )
    db.add(row)
    db.commit()
    return {"id": str(row.id), "all_ok": row.all_ok}


# ---------------------------------------------------------------- Incidencias (I5, I12, I13)
class IncidentIn(BaseModel):
    id: uuid.UUID
    category: str
    machine_id: Optional[int] = None
    session_id: Optional[uuid.UUID] = None
    note: Optional[str] = PField(None, max_length=2000)
    lat: Optional[float] = PField(None, ge=-90, le=90)
    lon: Optional[float] = PField(None, ge=-180, le=180)
    occurred_at: Optional[datetime] = None
    photo_b64: Optional[str] = None


class IncidentOut(BaseModel):
    id: uuid.UUID
    category: str
    note: Optional[str]
    status: str
    machine_id: Optional[int]
    machine_name: Optional[str] = None
    session_id: Optional[uuid.UUID]
    user_id: int
    user_name: Optional[str] = None
    lat: Optional[float]
    lon: Optional[float]
    occurred_at: datetime
    has_photo: bool


class IncidentPatch(BaseModel):
    status: str


def _incident_out(db: Session, i: MobileIncident) -> IncidentOut:
    machine = db.get(Machine, i.machine_id) if i.machine_id else None
    user = db.get(User, i.user_id)
    return IncidentOut(
        id=i.id, category=i.category, note=i.note, status=i.status, machine_id=i.machine_id,
        machine_name=machine.name if machine else None, session_id=i.session_id, user_id=i.user_id,
        user_name=user.full_name if user else None, lat=i.lat, lon=i.lon, occurred_at=i.occurred_at,
        has_photo=bool(i.photo_path),
    )


@router.post("/incidents", response_model=IncidentOut)
def create_incident(payload: IncidentIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if payload.category not in INCIDENT_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría de incidencia no válida.")
    existing = db.get(MobileIncident, payload.id)
    if existing is not None:
        return _incident_out(db, existing)
    cc = _check_access(db, current, payload.machine_id, payload.session_id)
    row = MobileIncident(
        id=payload.id, user_id=current.id, session_id=payload.session_id, machine_id=payload.machine_id,
        cost_center_id=cc, category=payload.category, note=payload.note, lat=payload.lat, lon=payload.lon,
        occurred_at=payload.occurred_at or _now(), photo_path=_save_photo("incidents", payload.id, payload.photo_b64),
        status="open",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _incident_out(db, row)


@router.get("/incidents", response_model=List[IncidentOut])
def list_incidents(status: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(MobileIncident)
    if not current.is_admin:
        q = q.filter(MobileIncident.user_id == current.id)
    if status:
        q = q.filter(MobileIncident.status == status)
    rows = q.order_by(MobileIncident.occurred_at.desc()).limit(max(1, min(limit, 500))).all()
    return [_incident_out(db, r) for r in rows]


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def update_incident(incident_id: uuid.UUID, payload: IncidentPatch, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Solo un supervisor puede atender incidencias.")
    if payload.status not in INCIDENT_STATUSES:
        raise HTTPException(status_code=400, detail="Estado no válido.")
    row = db.get(MobileIncident, incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada.")
    row.status = payload.status
    row.handled_by = current.id
    row.handled_at = _now()
    db.commit()
    db.refresh(row)
    return _incident_out(db, row)


# ---------------------------------------------------------------- Gastos de ruta (I6)
class ExpenseIn(BaseModel):
    id: uuid.UUID
    kind: str
    session_id: Optional[uuid.UUID] = None
    work_order_id: Optional[int] = None
    machine_id: Optional[int] = None
    liters: Optional[float] = PField(None, ge=0)
    amount: Optional[float] = PField(None, ge=0)
    station: Optional[str] = PField(None, max_length=200)
    odometer: Optional[float] = PField(None, ge=0)
    note: Optional[str] = PField(None, max_length=1000)
    occurred_at: Optional[datetime] = None
    photo_b64: Optional[str] = None


class ExpenseOut(BaseModel):
    id: uuid.UUID
    kind: str
    session_id: Optional[uuid.UUID]
    work_order_id: Optional[int]
    machine_id: Optional[int]
    liters: Optional[float]
    amount: Optional[float]
    station: Optional[str]
    odometer: Optional[float]
    note: Optional[str]
    occurred_at: datetime
    has_photo: bool


def _expense_out(e: MobileExpense) -> ExpenseOut:
    f = lambda v: float(v) if v is not None else None  # noqa: E731
    return ExpenseOut(
        id=e.id, kind=e.kind, session_id=e.session_id, work_order_id=e.work_order_id, machine_id=e.machine_id,
        liters=f(e.liters), amount=f(e.amount), station=e.station, odometer=f(e.odometer), note=e.note,
        occurred_at=e.occurred_at, has_photo=bool(e.photo_path),
    )


@router.post("/expenses", response_model=ExpenseOut)
def create_expense(payload: ExpenseIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if payload.kind not in EXPENSE_KINDS:
        raise HTTPException(status_code=400, detail="Tipo de gasto no válido.")
    if payload.kind == "fuel" and not payload.liters:
        raise HTTPException(status_code=400, detail="Indica los litros cargados.")
    existing = db.get(MobileExpense, payload.id)
    if existing is not None:
        return _expense_out(existing)
    _check_access(db, current, payload.machine_id, payload.session_id)
    row = MobileExpense(
        id=payload.id, user_id=current.id, session_id=payload.session_id, work_order_id=payload.work_order_id,
        machine_id=payload.machine_id, kind=payload.kind, liters=payload.liters, amount=payload.amount,
        station=payload.station, odometer=payload.odometer, note=payload.note,
        occurred_at=payload.occurred_at or _now(), photo_path=_save_photo("expenses", payload.id, payload.photo_b64),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _expense_out(row)


@router.get("/expenses", response_model=List[ExpenseOut])
def list_expenses(session_id: Optional[uuid.UUID] = None, limit: int = 100, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(MobileExpense)
    if not current.is_admin:
        q = q.filter(MobileExpense.user_id == current.id)
    if session_id is not None:
        q = q.filter(MobileExpense.session_id == session_id)
    return [_expense_out(r) for r in q.order_by(MobileExpense.occurred_at.desc()).limit(max(1, min(limit, 500))).all()]


# ---------------------------------------------------------------- Fotos
@router.get("/photos/{kind}/{record_id}")
def get_photo(kind: str, record_id: uuid.UUID, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    model = {"incidents": MobileIncident, "expenses": MobileExpense}.get(kind)
    if model is None:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    row = db.get(model, record_id)
    if row is None or not row.photo_path or not os.path.isfile(row.photo_path):
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    if not current.is_admin and row.user_id != current.id:
        raise HTTPException(status_code=403, detail="No autorizado.")
    return FileResponse(row.photo_path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


# ---------------------------------------------------------------- Dispositivos y diagnóstico (I15)
class HeartbeatIn(BaseModel):
    version: str = PField(..., max_length=40)
    platform: Optional[str] = PField(None, max_length=40)
    pending: Optional[int] = PField(None, ge=0)
    last_sync_at: Optional[datetime] = None


class DeviceOut(BaseModel):
    user_id: int
    user_name: Optional[str]
    version: Optional[str]
    platform: Optional[str]
    pending: Optional[int]
    last_sync_at: Optional[datetime]
    last_seen_at: datetime


class DiagnosticIn(BaseModel):
    version: Optional[str] = PField(None, max_length=40)
    message: Optional[str] = PField(None, max_length=500)
    log: Optional[str] = PField(None, max_length=20000)


@router.post("/heartbeat")
def heartbeat(payload: HeartbeatIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    row = db.get(MobileDevice, current.id)
    if row is None:
        row = MobileDevice(user_id=current.id, last_seen_at=_now())
        db.add(row)
    row.version, row.platform, row.pending = payload.version, payload.platform, payload.pending
    if payload.last_sync_at is not None:
        row.last_sync_at = payload.last_sync_at
    row.last_seen_at = _now()
    db.commit()
    return {"ok": True}


@router.get("/devices", response_model=List[DeviceOut])
def list_devices(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Se requiere perfil administrador.")
    out = []
    for d in db.query(MobileDevice).order_by(MobileDevice.last_seen_at.desc()).all():
        u = db.get(User, d.user_id)
        out.append(DeviceOut(user_id=d.user_id, user_name=u.full_name if u else None, version=d.version, platform=d.platform,
                             pending=d.pending, last_sync_at=d.last_sync_at, last_seen_at=d.last_seen_at))
    return out


@router.post("/diagnostics")
def create_diagnostic(payload: DiagnosticIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    db.add(MobileDiagnostic(user_id=current.id, version=payload.version, message=payload.message, log=payload.log))
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- Rutas asignadas
ROUTE_STATUSES = {"assigned", "in_progress", "done", "cancelled"}


class Waypoint(BaseModel):
    lat: float = PField(..., ge=-90, le=90)
    lon: float = PField(..., ge=-180, le=180)
    label: Optional[str] = PField(None, max_length=80)


class RouteIn(BaseModel):
    id: uuid.UUID
    name: str = PField(..., min_length=1, max_length=120)
    machine_id: int
    waypoints: List[Waypoint] = PField(..., min_length=2, max_length=60)
    note: Optional[str] = PField(None, max_length=1000)


class RoutePatch(BaseModel):
    status: str


class RouteOut(BaseModel):
    id: uuid.UUID
    name: str
    machine_id: int
    machine_name: Optional[str]
    waypoints: List[Waypoint]
    note: Optional[str]
    status: str
    created_by_name: Optional[str]
    created_at: Optional[datetime]


def _route_out(db: Session, r: MobileRoute) -> RouteOut:
    m, u = db.get(Machine, r.machine_id), db.get(User, r.created_by)
    return RouteOut(id=r.id, name=r.name, machine_id=r.machine_id, machine_name=m.name if m else None, waypoints=r.waypoints,
                    note=r.note, status=r.status, created_by_name=u.full_name if u else None, created_at=r.created_at)


@router.post("/routes", response_model=RouteOut)
def create_route(payload: RouteIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not current.is_admin:
        raise HTTPException(status_code=403, detail="Solo un supervisor puede asignar rutas.")
    existing = db.get(MobileRoute, payload.id)
    if existing is not None:
        return _route_out(db, existing)
    if db.get(Machine, payload.machine_id) is None:
        raise HTTPException(status_code=404, detail="Máquina no encontrada.")
    row = MobileRoute(id=payload.id, name=payload.name.strip(), machine_id=payload.machine_id,
                      waypoints=[w.model_dump() for w in payload.waypoints], note=payload.note, status="assigned", created_by=current.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _route_out(db, row)


@router.get("/routes", response_model=List[RouteOut])
def list_routes(machine_id: Optional[int] = None, active_only: bool = True, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(MobileRoute)
    if machine_id is not None:
        q = q.filter(MobileRoute.machine_id == machine_id)
    if active_only:
        q = q.filter(MobileRoute.status.in_(["assigned", "in_progress"]))
    if not current.is_admin:
        allowed = allowed_cost_center_ids(db, current.id)
        ids = [m.id for m in db.query(Machine).filter(Machine.cost_center_id.in_(allowed)).all()] if allowed else []
        q = q.filter(MobileRoute.machine_id.in_(ids)) if ids else q.filter(False)
    return [_route_out(db, r) for r in q.order_by(MobileRoute.created_at.desc()).limit(200).all()]


@router.patch("/routes/{route_id}", response_model=RouteOut)
def update_route(route_id: uuid.UUID, payload: RoutePatch, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if payload.status not in ROUTE_STATUSES:
        raise HTTPException(status_code=400, detail="Estado no válido.")
    row = db.get(MobileRoute, route_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ruta no encontrada.")
    if not current.is_admin:
        if payload.status == "cancelled":
            raise HTTPException(status_code=403, detail="Solo un supervisor puede cancelar una ruta.")
        _check_access(db, current, row.machine_id, None)
    row.status, row.updated_at = payload.status, _now()
    db.commit()
    db.refresh(row)
    return _route_out(db, row)
