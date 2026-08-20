from typing import List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import text
from fastapi import Body, Header, Request
from pydantic import BaseModel
from typing import List, Optional, Union
from datetime import datetime, timezone
import os
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import distinct
from app.db.session import get_db
from app.core.security import get_current_user, allowed_cost_center_ids, assert_cost_center_access
from app.core.utils import haversine_m, _f, duration_hours, estimate_fuel_liters
from app.models.users import User
from app.models.enums import TrackingStatus
from app.models.sessions import TrackingSession, TrackingPoint
from app.models.machines import Machine
from app.models.drivers import Driver
from app.models.cost_centers import CostCenter
from app.models.work_orders import WorkOrder
from app.models.activities import Labor
from app.schemas.sessions import (
    SessionsDayOut,
    SessionStart,
    TrackingSessionOut,
    PointsBatchIn,
    SessionSummaryOut,
    TrackingPointOut,
    TrackPointOut,
    TrackResponse
)
from fastapi import Query

router = APIRouter(prefix="", tags=["sessions"])


@router.post("/sessions/start", response_model=TrackingSessionOut)
def start_session(
    payload: SessionStart,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    machine = db.query(Machine).get(payload.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    work_order = None
    if payload.work_order_id is not None:
        work_order = db.query(WorkOrder).get(payload.work_order_id)
        if not work_order:
            raise HTTPException(status_code=404, detail="Work order not found")

    started_at = payload.started_at or datetime.utcnow()
    cc_id = payload.cost_center_id or (work_order.cost_center_id if work_order else None) or machine.cost_center_id
    assert_cost_center_access(db, current, cc_id)

    session_obj = TrackingSession(
        machine_id=payload.machine_id,
        driver_id=payload.driver_id,
        cost_center_id=cc_id,
        work_order_id=payload.work_order_id,
        started_at=started_at,
        status=TrackingStatus.open,
        created_at=datetime.utcnow(),
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj

@router.get("/sessions/search", response_model=List[SessionSummaryOut])
def search_sessions(
    # rango: inclusive en from, exclusive en to (patrón típico)
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    limit: int = 200,
    status: Optional[str] = Query(None),
    cost_center_id: int | None = None,
    machine_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    q = (
    db.query(
        TrackingSession,
        Machine.name.label("machine_name"),
        Driver.name.label("driver_name"),
        CostCenter.name.label("cost_center_name"),
        TrackingSession.points_count.label("points_count"),
        WorkOrder.id.label("work_order_id"),
        WorkOrder.labor_id.label("labor_id"),
        Labor.effort_factor.label("effort_factor"),
        Labor.target_speed_kmh.label("target_speed_kmh"),
        Machine.fuel_consumption_lph.label("machine_lph"),
        Machine.fuel_consumption_lpkm.label("machine_lpkm"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(WorkOrder, TrackingSession.work_order_id == WorkOrder.id)
        .outerjoin(Labor, WorkOrder.labor_id == Labor.id)
        .filter(TrackingSession.started_at >= date_from)
        .filter(TrackingSession.started_at < date_to)
    )

    # permisos
    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        q = q.filter(TrackingSession.cost_center_id.in_(allowed_ids))

    # filtros opcionales
    if status is not None:
        q = q.filter(TrackingSession.status == status)

    if cost_center_id is not None:
        if not current.is_admin:
            allowed_ids = set(allowed_cost_center_ids(db, current.id))
            if cost_center_id not in allowed_ids:
                raise HTTPException(status_code=403, detail="Not allowed cost center")
        q = q.filter(TrackingSession.cost_center_id == cost_center_id)

    if machine_id is not None:
        q = q.filter(TrackingSession.machine_id == machine_id)

    # al final recién orden y limit
    q = q.order_by(TrackingSession.started_at.desc()).limit(limit)

    rows = q.all()


    out: List[SessionSummaryOut] = []
    for (
        s, machine_name, driver_name, cost_center_name, points_count,
        work_order_id, labor_id, effort_factor, target_speed_kmh,
        machine_lph, machine_lpkm
    ) in rows:
        dur_h = duration_hours(s.started_at, s.ended_at)
        ef = _f(effort_factor)
        eff_h = (dur_h * ef) if (dur_h is not None and ef is not None) else None

        total_dist_m = _f(s.total_distance_m)
        avg_kmh = _f(s.avg_speed_kmh)

        est_fuel = estimate_fuel_liters(
            duration_h=dur_h,
            total_distance_m=total_dist_m,
            machine_lph=_f(machine_lph),
            machine_lpkm=_f(machine_lpkm),
            effort_factor=ef,
        )

        out.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
                work_order_id=work_order_id,
                labor_id=labor_id,
                effort_factor=ef,
                target_speed_kmh=_f(target_speed_kmh),
                total_distance_m=total_dist_m,
                avg_speed_kmh=avg_kmh,
                duration_hours=dur_h,
                effective_hours=eff_h,
                estimated_fuel_liters=est_fuel,
                last_point_ts=s.last_point_ts,
                last_lat=_f(s.last_lat),
                last_lon=_f(s.last_lon),
                last_speed_mps=_f(s.last_speed_mps),
            )
        )
    return out

@router.get("/sessions/days", response_model=List[SessionsDayOut])
def sessions_days(
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    machine_id: int | None = None,
    cost_center_id: int | None = None,
    status: TrackingStatus | None = None,
    tz: str = "America/Santiago",
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    # Base query de sesiones en rango (tabla chica)
    sq = db.query(TrackingSession.id)

    # Recomendación: filtra por OVERLAP real (sesiones que tocan el rango),
    # no solo started_at. Esto incluye sesiones largas abiertas.
    sq = sq.filter(TrackingSession.started_at < date_to)
    sq = sq.filter(func.coalesce(TrackingSession.ended_at, func.now()) >= date_from)

    if machine_id is not None:
        sq = sq.filter(TrackingSession.machine_id == machine_id)

    # permisos (por cost center)
    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        sq = sq.filter(TrackingSession.cost_center_id.in_(allowed_ids))

    if cost_center_id is not None:
        if not current.is_admin:
            allowed_ids = set(allowed_cost_center_ids(db, current.id))
            if cost_center_id not in allowed_ids:
                raise HTTPException(status_code=403, detail="Not allowed cost center")
        sq = sq.filter(TrackingSession.cost_center_id == cost_center_id)

    if status is not None:
        sq = sq.filter(TrackingSession.status == status)

    session_ids_subq = sq.subquery()

    # Agrupar puntos por día local (timezone)
    local_day = func.date(func.timezone(tz, TrackingPoint.ts))

    rows = (
        db.query(
            local_day.label("day"),
            func.count(TrackingPoint.id).label("points_count"),
            func.count(distinct(TrackingPoint.session_id)).label("sessions_count"),
        )
        .filter(TrackingPoint.session_id.in_(session_ids_subq))
        .filter(TrackingPoint.ts >= date_from)
        .filter(TrackingPoint.ts < date_to)
        .group_by(local_day)
        .order_by(local_day.asc())
        .all()
    )

    return [
        SessionsDayOut(
            day=r.day.isoformat(),
            points_count=int(r.points_count or 0),
            sessions_count=int(r.sessions_count or 0),
        )
        for r in rows
    ]

@router.post("/sessions/{session_id:uuid}/close", response_model=TrackingSessionOut)
def close_session(
    session_id: uuid.UUID,
    ended_at: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    session_obj = db.query(TrackingSession).get(session_id)
    if not session_obj:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_session_allowed(db, current, session_obj)

    if session_obj.status == TrackingStatus.closed:
        return session_obj

    points = (
        db.query(TrackingPoint)
        .filter(TrackingPoint.session_id == session_id)
        .order_by(TrackingPoint.ts.asc())
        .all()
    )

    if len(points) >= 2:
        total_distance_m = 0.0
        start_ts = points[0].ts
        end_ts = points[-1].ts

        prev = points[0]
        for p in points[1:]:
            total_distance_m += haversine_m(prev.lat, prev.lon, p.lat, p.lon)
            prev = p

        duration_h = (end_ts - start_ts).total_seconds() / 3600.0
        avg_speed_kmh = ((total_distance_m / 1000.0) / duration_h) if duration_h > 0 else 0.0

        session_obj.total_distance_m = total_distance_m
        session_obj.avg_speed_kmh = avg_speed_kmh

    session_obj.status = TrackingStatus.closed
    session_obj.ended_at = ended_at or datetime.utcnow()

    db.commit()
    db.refresh(session_obj)
    return session_obj


@router.get("/sessions/{session_id:uuid}", response_model=TrackingSessionOut)
def get_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    return s


def _get_session_or_404(db: Session, session_id: uuid.UUID) -> TrackingSession:
    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s

def _assert_session_allowed(db: Session, current: User, s: TrackingSession) -> None:
    if current.is_admin:
        return
    allowed_ids = set(allowed_cost_center_ids(db, current.id))
    if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Not allowed")


from sqlalchemy import desc
from decimal import Decimal
import os

def _to_float(x):
    if x is None:
        return None
    if isinstance(x, Decimal):
        return float(x)
    return float(x)

def _ensure_dt_utc(ts_value):
    """
    Soporta datetime (ideal) o epoch ms/s (por si algún dispositivo cambia formato).
    """
    if isinstance(ts_value, datetime):
        if ts_value.tzinfo is None:
            return ts_value.replace(tzinfo=timezone.utc)
        return ts_value.astimezone(timezone.utc)

    # epoch: segundos (10 dígitos) o ms
    if isinstance(ts_value, (int, float)):
        if ts_value < 10_000_000_000:
            return datetime.fromtimestamp(ts_value, tz=timezone.utc)
        return datetime.fromtimestamp(ts_value / 1000.0, tz=timezone.utc)

    raise ValueError(f"Unsupported timestamp type: {type(ts_value)}")


class TrackingPointIn(BaseModel):
    ts: int  # epoch (ms o s)
    lat: float
    lon: float
    speed_mps: Optional[float] = None

def ts_to_dt(ts: int) -> datetime:
    # si viene en segundos (10 dígitos aprox) conviértelo; si viene en ms, divide por 1000
    if ts < 10_000_000_000:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)

@router.post("/sessions/{session_id}/points")
def add_points(
    session_id: uuid.UUID,
    payload: PointsBatchIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    session = db.query(TrackingSession).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _assert_session_allowed(db, current, session)

    if session.status != "open":
        raise HTTPException(
            status_code=400,
            detail="Session is closed; no more points can be recorded.",
        )

    # ---- parámetros por ENV ----
    MIN_MOVE_METERS = float(os.getenv("TRACK_MIN_MOVE_METERS", "10"))
    MIN_SPEED_MPS = float(os.getenv("TRACK_MIN_SPEED_MPS", "0.5"))
    MIN_SAVE_INTERVAL_SEC = int(os.getenv("TRACK_MIN_SAVE_INTERVAL_SEC", "3"))

    # Baseline: primero intenta desde tracking_sessions.last_*
    last_ts = session.last_point_ts
    last_lat = session.last_lat
    last_lon = session.last_lon

    # Fallback solo si aún no hay last_* (por ejemplo, sesiones antiguas antes de la migración)
    if last_ts is None or last_lat is None or last_lon is None:
        last = (
            db.query(TrackingPoint)
            .filter(TrackingPoint.session_id == session_id)
            .order_by(TrackingPoint.ts.desc())
            .first()
        )
        last_ts = last.ts if last else None
        last_lat = float(last.lat) if last else None
        last_lon = float(last.lon) if last else None

    incoming_points = list(payload.points or [])
    incoming_points.sort(key=lambda p: _ensure_dt_utc(p.timestamp))

    now = datetime.utcnow()

    received = len(incoming_points)
    skipped_throttle = 0
    skipped_no_move = 0

    rows_to_insert = []
    inserted = 0

    # Para actualizar last_* al final
    last_inserted_row = None

    for p in incoming_points:
        try:
            p_ts = _ensure_dt_utc(p.timestamp)
        except Exception:
            skipped_no_move += 1
            continue

        p_lat = float(p.lat)
        p_lon = float(p.lon)
        p_speed = float(p.speed_mps) if (p.speed_mps is not None) else None

        # 1) Primer punto si no hay baseline
        if last_ts is None:
            row = {
                "session_id": session_id,
                "ts": p_ts,
                "lat": p_lat,
                "lon": p_lon,
                "speed_mps": p_speed,
                "accuracy_m": p.accuracy_m,
                "extra": p.extra,
                "created_at": now,
            }
            rows_to_insert.append(row)
            inserted += 1
            last_inserted_row = row
            last_ts, last_lat, last_lon = p_ts, p_lat, p_lon
            continue

        # 2) Throttle por tiempo
        dt_sec = (p_ts - last_ts).total_seconds()
        if dt_sec < MIN_SAVE_INTERVAL_SEC:
            skipped_throttle += 1
            continue

        # 3) Movimiento real
        dist_m = haversine_m(float(last_lat), float(last_lon), p_lat, p_lon)
        speed_ok = (p_speed is not None) and (p_speed >= MIN_SPEED_MPS)

        if dist_m < MIN_MOVE_METERS and not speed_ok:
            skipped_no_move += 1
            continue

        # 4) Punto válido -> lo dejamos en batch
        row = {
            "session_id": session_id,
            "ts": p_ts,
            "lat": p_lat,
            "lon": p_lon,
            "speed_mps": p_speed,
            "accuracy_m": p.accuracy_m,
            "extra": p.extra,
            "created_at": now,
        }
        rows_to_insert.append(row)
        inserted += 1
        last_inserted_row = row
        last_ts, last_lat, last_lon = p_ts, p_lat, p_lon

    # Inserta batch + actualiza stats sesión
    if inserted > 0:
        db.bulk_insert_mappings(TrackingPoint, rows_to_insert)

        # Update atómico: suma points_count y actualiza last_* solo si ts es más nuevo
        db.execute(
            text("""
                UPDATE tracking_sessions
                SET
                    points_count = points_count + :ins,
                    last_point_ts = CASE
                        WHEN last_point_ts IS NULL OR :ts > last_point_ts THEN :ts
                        ELSE last_point_ts
                    END,
                    last_lat = CASE
                        WHEN last_point_ts IS NULL OR :ts > last_point_ts THEN :lat
                        ELSE last_lat
                    END,
                    last_lon = CASE
                        WHEN last_point_ts IS NULL OR :ts > last_point_ts THEN :lon
                        ELSE last_lon
                    END,
                    last_speed_mps = CASE
                        WHEN last_point_ts IS NULL OR :ts > last_point_ts THEN :speed
                        ELSE last_speed_mps
                    END,
                    last_accuracy_m = CASE
                        WHEN last_point_ts IS NULL OR :ts > last_point_ts THEN :acc
                        ELSE last_accuracy_m
                    END
                WHERE id = :session_id
            """),
            {
                "ins": inserted,
                "ts": last_inserted_row["ts"],
                "lat": last_inserted_row["lat"],
                "lon": last_inserted_row["lon"],
                "speed": last_inserted_row.get("speed_mps"),
                "acc": last_inserted_row.get("accuracy_m"),
                "session_id": str(session_id),
            }
        )

    db.commit()

    return {
        "inserted": inserted,
        "received": received,
        "skipped_throttle": skipped_throttle,
        "skipped_no_move": skipped_no_move,
        "min_move_m": MIN_MOVE_METERS,
        "min_speed_mps": MIN_SPEED_MPS,
        "min_interval_sec": MIN_SAVE_INTERVAL_SEC,
    }

@router.get("/sessions/{session_id:uuid}/track", response_model=TrackResponse)
def get_session_track(
    session_id: uuid.UUID,
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    resolution: str = Query("raw", pattern="^(raw|10s|1m)$"),
    limit: int = Query(5000, ge=100, le=20000),
    cursor: str | None = Query(None, description="ISO timestamp of last item returned"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    # cursor -> datetime
    cursor_dt = None
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
            if cursor_dt.tzinfo is None:
                cursor_dt = cursor_dt.replace(tzinfo=timezone.utc)
            else:
                cursor_dt = cursor_dt.astimezone(timezone.utc)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor format")

    # -------- RAW --------
    if resolution == "raw":
        q = db.query(TrackingPoint).filter(TrackingPoint.session_id == session_id)
        q = q.filter(TrackingPoint.ts >= date_from, TrackingPoint.ts < date_to)
        if cursor_dt is not None:
            q = q.filter(TrackingPoint.ts > cursor_dt)

        rows = q.order_by(TrackingPoint.ts.asc()).limit(limit).all()

        items = [
            TrackPointOut(
                ts=r.ts,
                lat=float(r.lat),
                lon=float(r.lon),
                speed_mps=float(r.speed_mps) if r.speed_mps is not None else None,
                n=1,
            )
            for r in rows
        ]
        next_cursor = items[-1].ts.isoformat().replace("+00:00", "Z") if len(items) == limit else None
        return TrackResponse(items=items, next_cursor=next_cursor, resolution=resolution)

    # -------- BUCKETS (PG12) --------
    if resolution == "1m":
        bucket_expr = "date_trunc('minute', ts)"
        def bucket_py(dt: datetime) -> datetime:
            dt = dt.astimezone(timezone.utc)
            return dt.replace(second=0, microsecond=0)
    else:  # "10s"
        bucket_expr = "to_timestamp(floor(extract(epoch from ts) / 10) * 10)"
        def bucket_py(dt: datetime) -> datetime:
            dt = dt.astimezone(timezone.utc)
            sec = math.floor(dt.timestamp() / 10) * 10
            return datetime.fromtimestamp(sec, tz=timezone.utc)

    cursor_clause = ""
    params = {
        "session_id": str(session_id),
        "from_ts": date_from,
        "to_ts": date_to,
        "limit": limit,
    }

    if cursor_dt is not None:
        cursor_bucket = bucket_py(cursor_dt)
        cursor_clause = f"AND {bucket_expr} > :cursor_bucket"
        params["cursor_bucket"] = cursor_bucket

    sql = f"""
        SELECT
            {bucket_expr} AS bucket_ts,
            AVG(lat)::float8 AS lat,
            AVG(lon)::float8 AS lon,
            MAX(speed_mps)::float8 AS speed_mps,
            COUNT(*)::int AS n
        FROM tracking_points
        WHERE session_id = :session_id
          AND ts >= :from_ts
          AND ts < :to_ts
          {cursor_clause}
        GROUP BY 1
        ORDER BY 1
        LIMIT :limit
    """

    rows = db.execute(text(sql), params).fetchall()

    items = [
        TrackPointOut(
            ts=r.bucket_ts,
            lat=float(r.lat),
            lon=float(r.lon),
            speed_mps=float(r.speed_mps) if r.speed_mps is not None else None,
            n=int(r.n),
        )
        for r in rows
    ]

    next_cursor = items[-1].ts.isoformat().replace("+00:00", "Z") if len(items) == limit else None
    return TrackResponse(items=items, next_cursor=next_cursor, resolution=resolution)

@router.get("/sessions/{session_id:uuid}/points", response_model=List[TrackingPointOut])
def get_session_points(
    session_id: uuid.UUID,
    from_ts: int | None = Query(None, description="epoch ms (UTC)"),
    to_ts: int | None = Query(None, description="epoch ms (UTC)"),
    limit: int = Query(20000, ge=1, le=20000),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    q = db.query(TrackingPoint).filter(TrackingPoint.session_id == session_id)

    if from_ts is not None:
        from_dt = datetime.fromtimestamp(from_ts / 1000.0, tz=timezone.utc)
        q = q.filter(TrackingPoint.ts >= from_dt)

    if to_ts is not None:
        to_dt = datetime.fromtimestamp(to_ts / 1000.0, tz=timezone.utc)
        q = q.filter(TrackingPoint.ts <= to_dt) 

    return (
        q.order_by(TrackingPoint.ts.asc())
         .limit(limit)
         .all()
    )

@router.get("/sessions/my", response_model=List[SessionSummaryOut])
def my_sessions(
    limit: int = 50,
    status: TrackingStatus | None = None,
    cost_center_id: int | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    allowed_ids = allowed_cost_center_ids(db, current.id)
    if not allowed_ids:
        return []

    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            TrackingSession.points_count.label("points_count"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .filter(TrackingSession.cost_center_id.in_(allowed_ids))
    )

    if status is not None:
        q = q.filter(TrackingSession.status == status)

    if cost_center_id is not None:
        if not current.is_admin:
            allowed_set = set(allowed_ids)
            if cost_center_id not in allowed_set:
                raise HTTPException(status_code=403, detail="Not allowed cost center")
        q = q.filter(TrackingSession.cost_center_id == cost_center_id)

    rows = q.order_by(TrackingSession.started_at.desc()).limit(limit).all()

    return [
        SessionSummaryOut(
            id=s.id,
            machine_id=s.machine_id,
            machine_name=machine_name,
            driver_name=driver_name,
            cost_center_name=cost_center_name,
            started_at=s.started_at,
            ended_at=s.ended_at,
            status=s.status,
            points_count=int(points_count or 0),
            last_point_ts=s.last_point_ts,
            last_lat=_f(s.last_lat),
            last_lon=_f(s.last_lon),
            last_speed_mps=_f(s.last_speed_mps),
        )
        for (s, machine_name, driver_name, cost_center_name, points_count) in rows
    ]


@router.get("/sessions_active", response_model=List[SessionSummaryOut])
def list_active_sessions(
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            TrackingSession.points_count.label("points_count"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .filter(TrackingSession.status == TrackingStatus.open)
    )
    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        q = q.filter(TrackingSession.cost_center_id.in_(allowed_ids))
    rows = q.order_by(TrackingSession.started_at.desc()).all()

    return [
        SessionSummaryOut(
            id=s.id,
            machine_id=s.machine_id,
            machine_name=machine_name,
            driver_name=driver_name,
            cost_center_name=cost_center_name,
            started_at=s.started_at,
            ended_at=s.ended_at,
            status=s.status,
            points_count=int(points_count or 0),
            last_point_ts=s.last_point_ts,
            last_lat=_f(s.last_lat),
            last_lon=_f(s.last_lon),
            last_speed_mps=_f(s.last_speed_mps),
        )
        for (s, machine_name, driver_name, cost_center_name, points_count) in rows
    ]


@router.get("/sessions/{session_id:uuid}/points_range", response_model=List[TrackingPointOut])
def get_session_points_range(
    session_id: uuid.UUID,
    date_from: datetime = Query(..., alias="from"),
    date_to: datetime = Query(..., alias="to"),
    limit: int = 50000,

    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    if date_to <= date_from:
        raise HTTPException(status_code=400, detail="'to' must be greater than 'from'")

    s = db.query(TrackingSession).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    if not current.is_admin:
        allowed_ids = set(allowed_cost_center_ids(db, current.id))
        if s.cost_center_id is None or s.cost_center_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Not allowed")

    return (
        db.query(TrackingPoint)
        .filter(TrackingPoint.session_id == session_id)
        .filter(TrackingPoint.ts >= date_from)
        .filter(TrackingPoint.ts < date_to)
        .order_by(TrackingPoint.ts.asc())
        .limit(limit)
        .all()
    )

@router.get("/sessions_recent", response_model=List[SessionSummaryOut])
def list_recent_sessions(
    limit: int = 50,
    status: TrackingStatus | None = None,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    subq = (
        db.query(
            TrackingPoint.session_id.label("session_id"),
            func.count(TrackingPoint.id).label("points_count"),
        )
        .group_by(TrackingPoint.session_id)
        .subquery()
    )

    q = (
        db.query(
            TrackingSession,
            Machine.name.label("machine_name"),
            Driver.name.label("driver_name"),
            CostCenter.name.label("cost_center_name"),
            func.coalesce(subq.c.points_count, 0).label("points_count"),
            WorkOrder.id.label("work_order_id"),
            WorkOrder.labor_id.label("labor_id"),
            Labor.effort_factor.label("effort_factor"),
            Labor.target_speed_kmh.label("target_speed_kmh"),
            Machine.fuel_consumption_lph.label("machine_lph"),
            Machine.fuel_consumption_lpkm.label("machine_lpkm"),
        )
        .outerjoin(Machine, TrackingSession.machine_id == Machine.id)
        .outerjoin(Driver, TrackingSession.driver_id == Driver.id)
        .outerjoin(CostCenter, TrackingSession.cost_center_id == CostCenter.id)
        .outerjoin(subq, subq.c.session_id == TrackingSession.id)
        .outerjoin(WorkOrder, TrackingSession.work_order_id == WorkOrder.id)
        .outerjoin(Labor, WorkOrder.labor_id == Labor.id)
    )
    if status is not None:
        q = q.filter(TrackingSession.status == status)
    if not current.is_admin:
        allowed_ids = allowed_cost_center_ids(db, current.id)
        if not allowed_ids:
            return []
        q = q.filter(TrackingSession.cost_center_id.in_(allowed_ids))

    if status is not None:
        q = q.filter(TrackingSession.status == status)

    q = q.order_by(TrackingSession.started_at.desc()).limit(limit)
    rows = q.all()

    out: List[SessionSummaryOut] = []
    for (
        s, machine_name, driver_name, cost_center_name, points_count,
        work_order_id, labor_id, effort_factor, target_speed_kmh,
        machine_lph, machine_lpkm
    ) in rows:
        dur_h = duration_hours(s.started_at, s.ended_at)
        ef = _f(effort_factor)
        eff_h = (dur_h * ef) if (dur_h is not None and ef is not None) else None

        total_dist_m = _f(s.total_distance_m)
        avg_kmh = _f(s.avg_speed_kmh)

        est_fuel = estimate_fuel_liters(
            duration_h=dur_h,
            total_distance_m=total_dist_m,
            machine_lph=_f(machine_lph),
            machine_lpkm=_f(machine_lpkm),
            effort_factor=ef,
        )

        out.append(
            SessionSummaryOut(
                id=s.id,
                machine_id=s.machine_id,
                machine_name=machine_name,
                driver_name=driver_name,
                cost_center_name=cost_center_name,
                started_at=s.started_at,
                ended_at=s.ended_at,
                status=s.status,
                points_count=int(points_count or 0),
                work_order_id=work_order_id,
                labor_id=labor_id,
                effort_factor=ef,
                target_speed_kmh=_f(target_speed_kmh),
                total_distance_m=total_dist_m,
                avg_speed_kmh=avg_kmh,
                duration_hours=dur_h,
                effective_hours=eff_h,
                estimated_fuel_liters=est_fuel,
                last_point_ts=s.last_point_ts,
                last_lat=_f(s.last_lat),
                last_lon=_f(s.last_lon),
                last_speed_mps=_f(s.last_speed_mps),
            )
        )
    return out
