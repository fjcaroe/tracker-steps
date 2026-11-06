from datetime import datetime,timedelta,timezone
from app.services.gps_metrics import summarize,meters

BASE=datetime(2026,9,6,2,0,tzinfo=timezone.utc)


def point(i,minutes,lat=-33.4,speed=30,assignment='one'):
    return dict(id=str(i),recorded_at=BASE+timedelta(minutes=minutes),lat=lat,lon=-70.6,speed_kmh=speed,quality='gps',assignment_id=assignment)


def test_boundaries_holes_swaps_and_clock_conflicts():
    points=[point(0,0),point(1,1,-33.401),point(2,2,-33.402),point(3,30,-34),point(4,31,-34.001,assignment='two')]
    m=summarize(points,BASE,BASE+timedelta(hours=1))
    assert m['point_count']==5 and m['gap_count']==2
    assert abs(m['distance_m']-2*meters(points[0],points[1]))<.01
    assert m['moving_seconds']==120
    assert summarize(points,BASE,BASE)['point_count']==0


def test_daily_additivity_midnight_and_dst_with_bounded_halo():
    points=[point(i,i,-33.4-i*.0005) for i in range(240)]
    full=summarize(points,BASE,BASE+timedelta(hours=4))
    buckets=[]
    for hour in range(4):
        start=BASE+timedelta(hours=hour);end=start+timedelta(hours=1)
        bounded=[p for p in points if start-timedelta(minutes=20)<=p['recorded_at']<end+timedelta(minutes=20)]
        buckets.append(summarize(bounded,start,end))
    for field in ('point_count','distance_m','moving_seconds','gap_count','stop_count'):
        assert abs(sum(m[field] for m in buckets)-full[field])<.00001


def test_long_parking_drift_and_one_speed_spike_are_not_a_journey():
    points=[point(i,i,-33.4+(i%3)*.000001,0) for i in range(180)]
    points[80]['speed_kmh']=80
    metric=summarize(points,BASE,BASE+timedelta(hours=3))
    assert metric['distance_m']==0 and metric['moving_seconds']==0
    assert metric['stop_count']==2


def test_stop_crossing_hour_counted_once_and_invalid_fixes_ignored():
    points=[point(i,58+i,speed=0) for i in range(20)]
    a=summarize(points,BASE,BASE+timedelta(hours=1))
    b=summarize(points,BASE+timedelta(hours=1),BASE+timedelta(hours=2))
    assert a['stop_count']==0 and b['stop_count']==1
    points.append({**point(99,70), 'quality':'lbs'})
    points.append({**point(100,70), 'lat':float('nan')})
    assert summarize(points,BASE,BASE+timedelta(hours=2))['point_count']==20
