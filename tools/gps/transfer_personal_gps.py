"""Move one explicitly identified personal GPS between existing tenants.
Worker runs as postgres; private payload/receipts only. UUIDs and samples persist.
No other device is updated. Rehearse on a fresh destination copy first.
"""
import json,sys,uuid
import psycopg2
from psycopg2.extras import Json

TABLES=('gps_assets','gps_assignments','gps_positions','gps_security_policies','gps_security_incidents','gps_device_commands','gps_audit_events','gps_device_registrations')
def move(database,plan,apply=False):
 assert database=='tracker_steps' or database.startswith('PERSONAL_GPS_QA_')
 with psycopg2.connect(dbname=database,options='-c lock_timeout=5s -c statement_timeout=30s') as db:
  with db.cursor() as cr:
   def rows(sql,args=()):cr.execute(sql,args);return cr.fetchall()
   source=rows('SELECT id FROM gps_tenants WHERE issuer=%s AND company_id=%s',('CERRO_EL_PLOMO',plan['source_company']));target=rows('SELECT id FROM gps_tenants WHERE issuer=%s AND company_id=%s',('LAB_TAREAS',plan['target_company']));assert len(source)==len(target)==1
   source,target=source[0][0],target[0][0];asset=plan['asset_id']
   a=rows('SELECT row_to_json(a) FROM gps_assets a WHERE id=%s FOR UPDATE',(asset,));assert len(a)==1 and a[0][0]['plate']==plan['plate'];assert a[0][0]['tenant_id'] in (source,target)
   assignments=rows('SELECT row_to_json(a) FROM gps_assignments a WHERE asset_id=%s ORDER BY id FOR UPDATE',(asset,));assert assignments
   devices={x[0]['device_id'] for x in assignments};assert len(devices)==1;device=devices.pop()
   d=rows('SELECT row_to_json(d) FROM gps_devices d WHERE id=%s FOR UPDATE',(device,))[0][0];assert d['imei']==plan['imei']
   reg=rows('SELECT row_to_json(r) FROM gps_device_registrations r WHERE device_id=%s FOR UPDATE',(device,));assert len(reg)==1 and reg[0][0]['phone']==plan['phone'];reg=reg[0][0]
   assert reg['receiver_mode']=='forward' and d['tracking_approved']
   assert not rows('SELECT id FROM gps_assignments WHERE device_id=%s AND asset_id<>%s',(device,asset)),'Device has another asset history'
   incident_ids=[r[0] for r in rows('SELECT id FROM gps_security_incidents WHERE asset_id=%s',(asset,))]
   selectors={t:('asset_id=%s',(asset,)) for t in TABLES if t not in ('gps_assets','gps_device_registrations','gps_audit_events','gps_device_commands')}
   selectors.update({'gps_assets':('id=%s',(asset,)),'gps_device_registrations':('device_id=%s',(device,)),
    'gps_audit_events':("asset_id=%s OR incident_id=ANY(%s) OR detail->>'registration_id'=%s",(asset,incident_ids,reg['id'])),
    'gps_device_commands':('incident_id=ANY(%s)',(incident_ids,))})
   snapshot={}
   for table,(where,args) in selectors.items():
    data=rows('SELECT row_to_json(t) FROM '+table+' t WHERE '+where+' ORDER BY 1::text',args)
    snapshot[table]=[r[0] for r in data]
    assert all(r[0]['tenant_id']==a[0][0]['tenant_id'] for r in data),'Mixed asset ownership'
   others=rows('SELECT row_to_json(r),row_to_json(d) FROM gps_device_registrations r JOIN gps_devices d ON d.id=r.device_id WHERE r.tenant_id=%s AND r.device_id<>%s ORDER BY r.id',(source,device));assert len(others)==4
   assert not rows('SELECT id FROM gps_assets WHERE tenant_id=%s AND source_id=%s AND id<>%s',(target,a[0][0]['source_id'],asset))
   result={'source_tenant':source,'target_tenant':target,'device_id':device,'registration_id':reg['id'],'snapshot':snapshot,'other_devices':others,'position_count':len(snapshot['gps_positions'])}
   if not apply or a[0][0]['tenant_id']==target:return result
   for table,(where,args) in selectors.items():cr.execute('UPDATE '+table+' SET tenant_id=%s WHERE '+where,(target,*args))
   cr.execute('UPDATE gps_device_registrations SET version=version+1 WHERE id=%s',(reg['id'],))
   cr.execute('INSERT INTO gps_audit_events(id,tenant_id,asset_id,actor,action,detail,created_at) VALUES(%s,%s,%s,%s,%s,%s,now())',(str(uuid.uuid4()),target,asset,'support:codex','personal_asset_transferred',Json({'previous_issuer':'CERRO_EL_PLOMO','previous_company_id':plan['source_company'],'destination_issuer':'LAB_TAREAS','reason':'Usuario solicitó separar su vehículo personal de la flota productiva; historial conservado.'})))
   assert len(rows('SELECT id FROM gps_device_registrations WHERE tenant_id=%s',(source,)))==4
   assert rows('SELECT row_to_json(r),row_to_json(d) FROM gps_device_registrations r JOIN gps_devices d ON d.id=r.device_id WHERE r.tenant_id=%s ORDER BY r.id',(source,))==others
   for table,(where,args) in selectors.items():
    data=[r[0] for r in rows('SELECT row_to_json(t) FROM '+table+' t WHERE '+where,args)]
    expected=[{**r,'tenant_id':target,**({'version':r['version']+1} if table=='gps_device_registrations' else {})} for r in snapshot[table]]
    if table=='gps_audit_events':data=[r for r in data if r['action']!='personal_asset_transferred']
    assert sorted(data,key=lambda r:str(r.get('id',r)))==sorted(expected,key=lambda r:str(r.get('id',r))),table+' failed preservation'
   return result
if __name__=='__main__':
 payload=json.load(sys.stdin);print(json.dumps(move(sys.argv[1],payload['plan'],payload.get('apply',False)),default=str))
