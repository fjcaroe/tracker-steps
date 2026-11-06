"""Versioned, bounded-neighbour GPS intervals; half-open UTC buckets are additive.

Distances are estimates, never odometer/engine readings. Attribute each interval,
gap and first confirmed stop to its ending fix. Chile dates are presentation only.
"""
import math
from datetime import timezone

VERSION = 2
HALO_SECONDS = 1200


def stamp(value):
    if isinstance(value, str):
        from datetime import datetime
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def meters(a, b):
    rad = math.pi / 180
    h = math.sin((b['lat']-a['lat'])*rad/2)**2 + math.cos(a['lat']*rad)*math.cos(b['lat']*rad)*math.sin((b['lon']-a['lon'])*rad/2)**2
    return 6371000 * 2 * math.atan2(math.sqrt(h), math.sqrt(max(0, 1-h)))


def summarize(rows, start, end):
    points = []
    seen = set()
    for source in rows:
        p = dict(source)
        if p['id'] in seen or p.get('quality') != 'gps':
            continue
        if not (math.isfinite(p['lat']) and abs(p['lat']) <= 90 and math.isfinite(p['lon']) and abs(p['lon']) <= 180):
            continue
        seen.add(p['id']); p['at'] = stamp(p['recorded_at'])
        speed = p.get('speed_kmh')
        p['speed'] = speed if speed is not None and math.isfinite(speed) and 0 <= speed <= 300 else None
        points.append(p)
    points.sort(key=lambda p: (p['at'], p['id']))
    selected = [p for p in points if start <= p['at'] < end]
    result = dict(point_count=len(selected), distance_m=0.0, moving_seconds=0.0, stop_count=0, gap_count=0,
                  max_speed=max((p['speed'] for p in selected if p['speed'] is not None), default=None),
                  first_at=selected[0]['at'].isoformat() if selected else None,
                  last_at=selected[-1]['at'].isoformat() if selected else None)
    edges = []
    moving = set()
    for i in range(1, len(points)):
        a, b = points[i-1:i+1]; seconds = (b['at']-a['at']).total_seconds(); distance = meters(a, b)
        valid = 0 < seconds <= 600 and distance <= 5000 and distance/seconds*3.6 <= 220 and a['assignment_id'] == b['assignment_id']
        edges.append((a, b, seconds, distance, valid))
        if valid and distance >= 25 and all(p['speed'] is not None and p['speed'] >= 8 for p in (a, b)):
            moving.update((a['id'], b['id']))
    for i in range(2, len(points)):
        a, b, c = points[i-2:i+1]; ab, bc = edges[i-2], edges[i-1]
        dt = (c['at']-a['at']).total_seconds(); net = meters(a, c)
        fast = sum(p['speed'] is not None and p['speed'] >= 8 for p in (a,b,c)) >= 2
        inferred = all(p['speed'] is None for p in (a,b,c)) and dt > 0 and net/dt*3.6 >= 8
        if ab[4] and bc[4] and net >= 60 and net/max(1,ab[3]+bc[3]) > .65 and (fast or inferred):
            moving.update((a['id'],b['id'],c['id']))
    stop_start = None; stop_reported = False
    for i, p in enumerate(points):
        slow = p['speed'] is not None and p['speed'] <= 2
        edge = edges[i-1] if i else None
        continuation = bool(edge and edge[4] and edge[3] <= 35 and points[i-1]['speed'] is not None and points[i-1]['speed'] <= 2)
        if not slow or not continuation:
            stop_start = p['at'] if slow else None; stop_reported = False
        if slow and stop_start is not None and not stop_reported and (p['at']-stop_start).total_seconds() >= 180:
            if start <= p['at'] < end: result['stop_count'] += 1
            stop_reported = True
        if not edge or not start <= p['at'] < end: continue
        a,b,seconds,distance,valid = edge
        if not valid:
            result['gap_count'] += 1
        elif a['id'] in moving and b['id'] in moving:
            if not (distance < 25 and (a['speed'] or 0) < 5 and (b['speed'] or 0) < 5):
                result['distance_m'] += distance
                if not (a['speed'] is not None and b['speed'] is not None and a['speed'] <= 2 and b['speed'] <= 2):
                    result['moving_seconds'] += seconds
    return result
