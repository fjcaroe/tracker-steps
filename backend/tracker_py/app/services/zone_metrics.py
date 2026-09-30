"""Local simple polygons, linear interpolation between trustworthy GPS fixes.

No extrapolation beyond fixes. Gaps, assignment changes and implausible jumps
remain unobserved. Distances are GPS chord estimates, never worked surface.
"""
import math
from datetime import timedelta, timezone

EARTH_M = 6371008.8
EPS = 1e-12
MAX_GAP_SECONDS = 300
MAX_SPEED_KMH = 200


def cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def sub(a, b):
    return (a[0]-b[0], a[1]-b[1])


def on_edge(p, a, b):
    return abs(cross(sub(p,a),sub(b,a))) <= EPS and min(a[0],b[0])-EPS <= p[0] <= max(a[0],b[0])+EPS and min(a[1],b[1])-EPS <= p[1] <= max(a[1],b[1])+EPS


def inside(p, ring):
    result = False
    for a, b in zip(ring, ring[1:]+ring[:1]):
        if on_edge(p,a,b):
            return True
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:
            result = not result
    return result


def intersection(a,b,c,d):
    r,s=sub(b,a),sub(d,c)
    denominator=cross(r,s)
    if abs(denominator) <= EPS:
        return None
    t,u=cross(sub(c,a),s)/denominator,cross(sub(c,a),r)/denominator
    return max(0.,min(1.,t)) if -EPS <= t <= 1+EPS and -EPS <= u <= 1+EPS else None


def distance(a,b):
    lat1,lat2=map(math.radians,(a[1],b[1]))
    dlat,dlon=lat2-lat1,math.radians(b[0]-a[0])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2*EARTH_M*math.asin(min(1,math.sqrt(h)))


def polygon_info(vertices):
    ring=[(p['lon'],p['lat']) for p in vertices]
    if len(ring)<3 or len(ring)>100 or len(set(ring))!=len(ring):
        raise ValueError('Usa entre 3 y 100 vértices distintos, sin repetir el primero al final.')
    if any(not math.isfinite(x) or not math.isfinite(y) or abs(x)>180 or abs(y)>80 for x,y in ring):
        raise ValueError('Coordenadas inválidas; latitud entre -80 y 80, longitud entre -180 y 180.')
    if max(p[0] for p in ring)-min(p[0] for p in ring)>2 or max(p[1] for p in ring)-min(p[1] for p in ring)>2:
        raise ValueError('La zona debe ser local (extensión máxima de 2 grados).')
    edges=list(zip(ring,ring[1:]+ring[:1]))
    for i,(a,b) in enumerate(edges):
        if distance(a,b)<.5:
            raise ValueError('Separa los vértices al menos medio metro.')
        # Adjacent edges may meet only at their shared vertex, never overlap.
        c=ring[(i+2)%len(ring)]
        if on_edge(c,a,b) or on_edge(a,b,c):
            raise ValueError('El polígono tiene bordes superpuestos.')
        for j,(c,d) in enumerate(edges):
            if j<=i+1 or (i==0 and j==len(edges)-1):
                continue
            if intersection(a,b,c,d) is not None or any((on_edge(a,c,d),on_edge(b,c,d),on_edge(c,a,b),on_edge(d,a,b))):
                raise ValueError('Los bordes del polígono no pueden cruzarse ni tocarse.')
    origin=ring[0]
    scale=math.cos(math.radians(sum(p[1] for p in ring)/len(ring)))
    xy=[(math.radians(p[0]-origin[0])*EARTH_M*scale,math.radians(p[1]-origin[1])*EARTH_M) for p in ring]
    area=abs(sum(cross(a,b) for a,b in zip(xy,xy[1:]+xy[:1])))/2
    if area<1:
        raise ValueError('La zona debe tener al menos 1 m² de superficie.')
    return {'area_m2':area,'perimeter_m':sum(distance(a,b) for a,b in edges)}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def interpolate(a,b,t):
    return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)


def summarize(vertices, points, start, end):
    ring=[(p['lon'],p['lat']) for p in vertices]
    stats={key:{'seconds':0.,'distance_m':0.,'moving_seconds':0.,'stationary_seconds':0.,'unknown_motion_seconds':0.,'max_speed_kmh':None} for key in ('inside','outside')}
    events,segments=[],[]
    previous_state,previous_end=None,None
    rejected={'long_gap':0,'assignment_change':0,'invalid_fix':0,'implausible_jump':0}
    for p in points:
        if start<=utc(p.recorded_at)<=end and p.quality=='gps' and p.speed_kmh is not None and 0<=p.speed_kmh<=MAX_SPEED_KMH:
            key='inside' if inside((p.lon,p.lat),ring) else 'outside'
            stats[key]['max_speed_kmh']=max(stats[key]['max_speed_kmh'] or 0,p.speed_kmh)
    for a,b in zip(points,points[1:]):
        ta,tb=utc(a.recorded_at),utc(b.recorded_at)
        if tb<=ta or tb<=start or ta>=end:
            continue
        dt=(tb-ta).total_seconds()
        reason=None
        pa,pb=(a.lon,a.lat),(b.lon,b.lat)
        meters=distance(pa,pb)
        if a.assignment_id!=b.assignment_id:
            reason='assignment_change'
        elif a.quality!='gps' or b.quality!='gps':
            reason='invalid_fix'
        elif dt>MAX_GAP_SECONDS:
            reason='long_gap'
        elif meters/dt*3.6>MAX_SPEED_KMH or any(s is not None and (not math.isfinite(s) or s<0 or s>MAX_SPEED_KMH) for s in (a.speed_kmh,b.speed_kmh)):
            reason='implausible_jump'
        if reason:
            rejected[reason]+=1
            previous_state,previous_end=None,None
            continue
        lo=max(0,(start-ta).total_seconds()/dt)
        hi=min(1,(end-ta).total_seconds()/dt)
        cuts=[lo,hi]
        for c,d in zip(ring,ring[1:]+ring[:1]):
            t=intersection(pa,pb,c,d)
            if t is not None and lo<t<hi:
                cuts.append(t)
        cuts=sorted(set(round(t,12) for t in cuts))
        motion='unknown_motion_seconds'
        if a.speed_kmh is not None and b.speed_kmh is not None:
            if a.speed_kmh>2 and b.speed_kmh>2:motion='moving_seconds'
            elif a.speed_kmh<=2 and b.speed_kmh<=2:motion='stationary_seconds'
        for f,t in zip(cuts,cuts[1:]):
            if t-f<1e-10:continue
            state='inside' if inside(interpolate(pa,pb,(f+t)/2),ring) else 'outside'
            first,last=ta+timedelta(seconds=f*dt),ta+timedelta(seconds=t*dt)
            seconds=(t-f)*dt
            stats[state]['seconds']+=seconds
            stats[state]['distance_m']+=meters*(t-f)
            stats[state][motion]+=seconds
            p1,p2=interpolate(pa,pb,f),interpolate(pa,pb,t)
            if previous_state is not None and previous_state!=state and previous_end and abs((first-previous_end).total_seconds())<.01:
                events.append({'type':'entry' if state=='inside' else 'exit','at':first,'lat':p1[1],'lon':p1[0]})
            segments.append({'state':state,'start':first,'end':last,'path':[{'lat':p1[1],'lon':p1[0]},{'lat':p2[1],'lon':p2[0]}]})
            previous_state,previous_end=state,last
    duration=(end-start).total_seconds()
    observed=sum(s['seconds'] for s in stats.values())
    return {**stats,'period_seconds':duration,'observed_seconds':observed,
            'unobserved_seconds':max(0,duration-observed),'coverage_pct':min(100,observed/duration*100),
            'entries':sum(e['type']=='entry' for e in events),'exits':sum(e['type']=='exit' for e in events),
            'events':events[-1000:],'events_truncated':len(events)>1000,
            'segments':segments[-500:],'map_truncated':len(segments)>500,
            'point_count':sum(start<=utc(p.recorded_at)<=end for p in points),
            'rejected_intervals':rejected,'max_gap_seconds':MAX_GAP_SECONDS,
            'max_speed_threshold_kmh':MAX_SPEED_KMH}
