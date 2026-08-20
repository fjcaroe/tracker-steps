import math
from datetime import datetime, timezone

def haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6371000.0
    φ1 = math.radians(float(lat1))
    φ2 = math.radians(float(lat2))
    dφ = math.radians(float(lat2) - float(lat1))
    dλ = math.radians(float(lon2) - float(lon1))

    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def duration_hours(started_at, ended_at):
    if not started_at:
        return 0.0
    start = to_utc(started_at)
    end = to_utc(ended_at) if ended_at else datetime.now(timezone.utc)
    h = (end - start).total_seconds() / 3600.0
    return max(0.0, h)
