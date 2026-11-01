"""Register a user-described real vehicle in native Fleet and explicitly link its GPS asset.

Requires private JSON facts, an ephemeral authenticated Odoo proof, --apply,
an already validated fresh Odoo-copy proof and the shared operation lock.
No odometer, driver, year, expense or financial document is invented.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import requests


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--proof',type=Path,required=True);p.add_argument('--native-qa',type=Path,required=True);p.add_argument('--receipts',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    assert os.geteuid()==0;os.umask(0o077)
    facts=json.loads(a.input.read_text(encoding='utf-8-sig'));proof=json.loads(a.proof.read_text());qa=json.loads(a.native_qa.read_text())
    assert qa['native_models'] and qa['neutralized'] and qa['source_database']=='CERRO_EL_PLOMO'
    assert proof['host']=='cerroelplomo.stepsapp.cl' and proof['company_id']==facts['company_id']
    assert re.fullmatch(r'[0-9a-f-]{36}',facts['asset_id']) and facts['model'].strip() and facts['plate'].strip()
    client=requests.Session();client.cookies.set('session_id',proof['session_id']);client.cookies.set('cids',str(proof['company_id']));client.headers['Host']=proof['host'];base='http://127.0.0.1:8082'
    def rpc(model,method,args=None,**kwargs):
        payload={'jsonrpc':'2.0','method':'call','id':1,'params':{'model':model,'method':method,'args':args or [],'kwargs':{**kwargs,'context':{'allowed_company_ids':[facts['company_id']],'mail_create_nosubscribe':True,'tracking_disable':True,'mail_notify_force_send':False}}}}
        response=client.post(base+'/web/dataset/call_kw/'+model+'/'+method,json=payload,timeout=40);response.raise_for_status();data=response.json()
        assert 'error' not in data,'Odoo rejected the operation; review native records before retrying'
        return data['result']
    def create(model,values):
        result=rpc(model,'create',[[values]]);return result[0] if isinstance(result,list) else result
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        context=client.get(base+'/steps_tracker/context',timeout=30).json();assert context['company_id']==facts['company_id'] and context['role']=='manager'
        asset_response=client.get(base+'/steps_tracker/api/assets/'+facts['asset_id'],timeout=30);assert asset_response.status_code==200
        asset=asset_response.json();assert asset['plate']==facts['plate']
        brands=rpc('fleet.vehicle.model.brand','search_read',domain=[['name','=',facts['brand']]],fields=['id','name'],limit=2);assert len(brands)==1,'Brand must be an unambiguous existing native master'
        models=rpc('fleet.vehicle.model','search_read',domain=[['name','=',facts['model']],['brand_id','=',brands[0]['id']]],fields=['id','name','brand_id'],limit=2);assert len(models)<2
        vehicles=rpc('fleet.vehicle','search_read',domain=[['company_id','=',facts['company_id']],['license_plate','=',facts['plate']]],fields=['id','model_id','company_id','license_plate'],limit=2);assert len(vehicles)<2
        links=rpc('step.tracker.asset.link','search_read',domain=[['company_id','=',facts['company_id']],['asset_id','=',facts['asset_id']]],fields=['id','vehicle_id'],limit=2);assert len(links)<2
        if links:
            assert vehicles and links[0]['vehicle_id'][0]==vehicles[0]['id']
            print(json.dumps({'already_linked':True,'physical_odometer_recorded':False}));return
        if not a.apply:print(json.dumps({'eligible':True,'dry_run':True,'existing_model':bool(models),'existing_vehicle':bool(vehicles)}));return
        root=a.receipts/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');root.mkdir(parents=True,mode=0o700)
        (root/'before.json').write_text(json.dumps({'asset':asset,'models':models,'vehicles':vehicles,'links':links},indent=2))
        # Preserve a current native-database backup immediately before creating records.
        with (root/'cerro-before-onboarding.dump').open('wb') as out:subprocess.run(['sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO'],stdout=out,check=True)
        subprocess.run(['pg_restore','--file=/dev/null',str(root/'cerro-before-onboarding.dump')],check=True)
        model_id=models[0]['id'] if models else create('fleet.vehicle.model',{'name':facts['model'],'brand_id':brands[0]['id']})
        if vehicles:
            assert vehicles[0]['model_id'][0]==model_id,'Existing vehicle model differs; stop'
            vehicle_id=vehicles[0]['id']
        else:vehicle_id=create('fleet.vehicle',{'model_id':model_id,'license_plate':facts['plate'],'company_id':facts['company_id']})
        link_id=create('step.tracker.asset.link',{'company_id':facts['company_id'],'asset_id':facts['asset_id'],'vehicle_id':vehicle_id,'note':'Vehículo real de piloto descrito por el usuario en este chat. Vínculo explícito; sin lectura física inicial informada.'})
        saved=rpc('step.tracker.asset.link','read',[[link_id]],fields=['id','asset_id','vehicle_id','company_id']);assert saved[0]['asset_id']==facts['asset_id'] and saved[0]['vehicle_id'][0]==vehicle_id
        vehicle=rpc('fleet.vehicle','read',[[vehicle_id]],fields=['id','name','license_plate','model_id','company_id','tracker_asset_id']);assert vehicle[0]['tracker_asset_id']==facts['asset_id']
        (root/'after.json').write_text(json.dumps({'vehicle':vehicle,'link':saved,'native_qa':qa},indent=2))
        print(json.dumps({'vehicle_ready':True,'linked_to_existing_gps_asset':True,'physical_odometer_recorded':False,'no_expenses_or_financial_documents':True}))


if __name__=='__main__':main()
