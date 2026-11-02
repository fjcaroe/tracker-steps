"""Same-company object isolation, including counts, writes and guessed IDs."""
from datetime import timedelta
from jose import jwt
from test_fleet import fleet, headers, point
from app.models.fleet import Asset, Incident, Command, Policy, now


def restricted(assets=('a1',), protect=True, role='operator'):
    base = jwt.get_unverified_claims(headers()['Authorization'].split()[1])
    base.update(role=role, asset_ids=list(assets), manage_protection=protect)
    return {'Authorization': 'Bearer '+jwt.encode(base, 'test-key-one', algorithm='HS256')}


def test_vehicle_scope_lists_objects_and_mutations(fleet):
    client, factory = fleet
    with factory() as db:
        db.add(Asset(id='hidden', tenant_id='t1', source_id='fleet:hidden', name='Hidden'))
        db.add_all([Policy(asset_id=a,tenant_id='t1') for a in ('a1','hidden')])
        db.add_all([Incident(id='i-'+a,asset_id=a,tenant_id='t1',type='manual',severity='medium') for a in ('a1','hidden')])
        db.flush()
        db.add(Command(id='hidden-command',tenant_id='t1',incident_id='i-hidden',intention_id='hidden-intention',type='restore_start',requester='u1',reason='Private event',result='Not sent'))
        db.commit()
    h=restricted()
    snapshot=client.get('/v1/fleet/snapshot',headers=h).json()
    assert snapshot['total']==1 and sum(snapshot['counts'].values())==1
    assert [a['asset_id'] for a in snapshot['items']]==['a1']
    assert client.get('/v1/fleet/snapshot?q=Hidden',headers=h).json()['total']==0
    assert [p['asset_id'] for p in client.get('/v1/security/policies',headers=h).json()]==['a1']
    assert [p['asset_id'] for p in client.get('/v1/security/incidents',headers=h).json()['items']]==['a1']
    for path in ('assets/hidden','assets/hidden/positions','security/incidents/i-hidden','security/commands/hidden-command'):
        assert client.get('/v1/'+path,headers=h).status_code==404
    assert client.patch('/v1/security/incidents/i-hidden',headers=h,json={'state':'acknowledged','reason':'Guessed identifier'}).status_code==404
    assert client.post('/v1/security/incidents',headers=h,json={'asset_id':'hidden','type':'manual','reason':'Guessed identifier'}).status_code==404
    body={'asset_id':'hidden','armed':True,'version':1,'reason':'Guessed identifier'}
    assert client.put('/v1/security/policies',headers=h,json=body).status_code==404
    body.update(asset_id='a1')
    assert client.put('/v1/security/policies',headers=h,json=body).status_code==200
    body.update(armed=False,version=2)
    assert client.put('/v1/security/policies',headers=h,json=body).status_code==200
    assert client.put('/v1/security/policies',headers=restricted(protect=False),json={**body,'version':3}).status_code==403
    for path in ('configuration','asset-sources','sync/changes'):
        assert client.get('/v1/'+path,headers=h).status_code==403
    assert client.post('/v1/classic-session',headers=h,json={'login':'pilot','name':'Pilot'}).status_code==403
    assert client.get('/v1/fleet/snapshot',headers=headers()).json()['total']==2


def test_empty_and_revoked_vehicle_scope_denies_access(fleet):
    client,_=fleet
    assert client.get('/v1/assets/a1',headers=restricted()).status_code==200
    assert client.get('/v1/assets/a1',headers=restricted(())).status_code==404
    assert client.get('/v1/fleet/snapshot',headers=restricted(())).json()['items']==[]
    assert client.get('/v1/fleet/snapshot',headers=restricted(('a2',))).json()['items']==[]
    base=jwt.get_unverified_claims(headers()['Authorization'].split()[1]);base['asset_ids']='a1'
    h={'Authorization':'Bearer '+jwt.encode(base,'test-key-one',algorithm='HS256')}
    assert client.get('/v1/fleet/snapshot',headers=h).status_code==401
