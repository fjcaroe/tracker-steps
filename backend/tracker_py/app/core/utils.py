import math
from datetime import datetime, timezone


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _f(x):
    return float(x) if x is not None else None


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def duration_hours(started_at, ended_at):
    if not started_at:
        return 0.0
    start = _to_utc(started_at)
    end = _to_utc(ended_at) if ended_at else datetime.now(timezone.utc)
    h = (end - start).total_seconds() / 3600.0
    return max(0.0, h)


def estimate_fuel_liters(
    duration_h: float | None,
    total_distance_m: float | None,
    machine_lph: float | None,
    machine_lpkm: float | None,
    effort_factor: float | None,
) -> float | None:
    ef = effort_factor if (effort_factor is not None and effort_factor > 0) else 1.0

    base = None
    if machine_lph is not None and duration_h is not None:
        base = duration_h * machine_lph
    elif machine_lpkm is not None and total_distance_m is not None:
        base = (total_distance_m / 1000.0) * machine_lpkm

    return (base * ef) if base is not None else None
