from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from test_fleet import fleet, headers
from app.models.fleet import Position, Audit
from app.services.zone_metrics import polygon_info, summarize

START=datetime(2026,9,1,tzinfo=timezone.utc)
RING=[{'lat':0,'lon':0},{'lat':0,'lon':.002},{'lat':.002,'lon':.002},{'lat':.002,'lon':0}]
BODY={'name':'Patio norte','vertices':RING}

def fix(seconds,lon,lat=.001,**kwargs):
    return SimpleNamespace(recorded_at=START+timedelta(seconds=seconds),lon=lon,lat=lat,
        **({'quality':'gps','speed_kmh':10,'assignment_id':'as1'}|kwargs))

def test_crossing_with_both_fixes_outside_and_clipping():
    points=[fix(0,-.001),fix(120,.003)]
    report=summarize(RING,points,START,START+timedelta(seconds=120))
    assert report['entries']==report['exits']==1
    assert report['inside']['seconds']==pytest.approx(60)
    assert report['outside']['seconds']==pytest.approx(60)
    assert report['inside']['distance_m']==pytest.approx(222.39,abs=.1)
    assert report['coverage_pct']==pytest.approx(100)
    assert [e['at'] for e in report['events']]==[START+timedelta(seconds=30),START+timedelta(seconds=90)]
    clipped=summarize(RING,points,START+timedelta(seconds=40),START+timedelta(seconds=80))
    assert clipped['inside']['seconds']==pytest.approx(40)
    assert clipped['entries']==clipped['exits']==0

@pytest.mark.parametrize('changes,seconds,reason',[({},301,'long_gap'),({'quality':'invalid'},120,'invalid_fix'),({'assignment_id':'another'},120,'assignment_change'),({},1,'implausible_jump')])
def test_untrustworthy_intervals_never_invent_activity(changes,seconds,reason):
    report=summarize(RING,[fix(0,-.001),fix(seconds,.003,**changes)],START,START+timedelta(seconds=seconds))
    assert report['observed_seconds']==0
    assert report['entries']==report['exits']==0
    assert report['rejected_intervals'][reason]==1

def test_stationary_no_extrapolation_unknown_speed_and_tangent():
    result=summarize(RING,[fix(10,.001,speed_kmh=0),fix(70,.001,speed_kmh=0),fix(100,.001,speed_kmh=None)],START,START+timedelta(seconds=120))
    assert result['inside']['stationary_seconds']==60
    assert result['inside']['unknown_motion_seconds']==30
    assert result['unobserved_seconds']==30
    tangent=summarize(RING,[fix(0,-.001,lat=.001),fix(120,.001,lat=-.001)],START,START+timedelta(seconds=120))
    assert tangent['entries']==tangent['exits']==0
    assert tangent['inside']['seconds']==0

def test_concave_zone_and_geometry_validation():
    concave=[{'lat':y,'lon':x} for x,y in [(0,0),(.003,0),(.003,.003),(.002,.003),(.002,.001),(.001,.001),(.001,.003),(0,.003)]]
    result=summarize(concave,[fix(0,-.001,lat=.002),fix(150,.004,lat=.002)],START,START+timedelta(seconds=150))
    assert result['entries']==result['exits']==2
    assert result['inside']['seconds']==pytest.approx(60)
    assert polygon_info(RING)['area_m2']==pytest.approx(49457,abs=10)
    for vertices in [RING+[RING[0]],[RING[0],RING[2],RING[1],RING[3]],RING[:2], [{'lat':0,'lon':0},{'lat':0,'lon':.003},{'lat':0,'lon':.001},{'lat':.003,'lon':0}]]:
        with pytest.raises(ValueError):polygon_info(vertices)

def test_zone_permissions_version_and_tenant_isolation(fleet):
    client,factory=fleet
    assert client.get('/v1/zones').status_code==401
    for role in ['viewer','operator']:
        assert client.post('/v1/zones',headers=headers(role=role),json=BODY).status_code==403
    response=client.post('/v1/zones',headers=headers(),json=BODY)
    assert response.status_code==200,response.text
    zone=response.json()
    assert len(client.get('/v1/zones',headers=headers(role='viewer')).json())==1
    assert client.get('/v1/zones',headers=headers('test-two')).json()==[]
    url='/v1/zones/'+zone['id']
    assert client.patch(url,headers=headers('test-two'),json=BODY|{'version':1}).status_code==404
    assert client.patch(url,headers=headers(),json=BODY|{'version':2}).status_code==409
    changed=client.patch(url,headers=headers(),json=BODY|{'version':1,'active':False})
    assert changed.json()['version']==2 and changed.json()['active'] is False
    assert client.patch(url,headers=headers(),json=BODY|{'version':1}).status_code==409
    assert client.post('/v1/zones',headers=headers(),json=BODY|{'name':'  '}).status_code==422
    assert client.post('/v1/zones',headers=headers(),json=BODY|{'vertices':[RING[0],RING[2],RING[1],RING[3]]}).status_code==422
    params={'asset_id':'a1','start':START.isoformat(),'end':(START+timedelta(seconds=120)).isoformat()}
    assert client.get(url+'/report',headers=headers('test-two'),params=params).status_code==404
    assert client.get(url+'/report',headers=headers(),params=params|{'asset_id':'a2'}).status_code==404
    assert client.get(url+'/report',headers=headers(),params=params|{'end':(START+timedelta(days=32)).isoformat()}).status_code==422
    assert client.get(url+'/report',headers=headers(),params=params|{'start':'2026-09-01T00:00:00'}).status_code==422
    with factory() as db:
        assert db.query(Audit).filter_by(action='zone_updated').count()==1

def test_report_actual_positions_ambiguous_timestamps_and_no_data(fleet):
    client,factory=fleet
    zone=client.post('/v1/zones',headers=headers(),json=BODY).json()
    url='/v1/zones/'+zone['id']+'/report'
    params={'asset_id':'a1','start':START.isoformat(),'end':(START+timedelta(seconds=120)).isoformat()}
    empty=client.get(url,headers=headers(role='viewer'),params=params).json()
    assert empty['coverage_pct']==0 and empty['unobserved_seconds']==120
    def insert(id,p):
        with factory() as db:
            db.add(Position(id=id,tenant_id='t1',asset_id='a1',device_id='d1',source_id=id,**vars(p)))
            db.commit()
    insert('p1',fix(0,-.001));insert('p2',fix(120,.003))
    result=client.get(url,headers=headers(),params=params).json()
    assert result['entries']==result['exits']==1
    insert('p3',fix(120,.005))
    result=client.get(url,headers=headers(),params=params).json()
    assert result['observed_seconds']==0
    with factory() as db:
        assert db.get(Position,'p3').quality=='gps'
