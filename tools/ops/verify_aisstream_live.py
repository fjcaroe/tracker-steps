"""Verify actual AISStream authentication/data without persisting test positions.

Run through systemd-run with the same private EnvironmentFile/service user as
the collector. Uses a small public coastal box and rolls back all ERP changes.
"""
import argparse
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import re
import sys
from unittest.mock import patch
import websockets

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('--commit',required=True)
a=p.parse_args()
key=os.environ.get('AISSTREAM_API_KEY','').strip()
assert key,'Provision the private AISStream key first'
target=json.loads(Path(__file__).with_name('environments.json').read_text())['environments'][a.environment]
sys.path.insert(0,'/opt/odoo18')
import odoo
from odoo import api,fields,SUPERUSER_ID
odoo.tools.config.parse_config(['-c',target['config'],'-d',target['database'],'--no-http'])
registry=odoo.registry(target['database'])


async def verify():
    async with websockets.connect('wss://stream.aisstream.io/v0/stream',compression='deflate',
            open_timeout=15,ping_interval=10,max_size=262144) as socket:
        await socket.send(json.dumps({'APIKey':key,'BoundingBoxes':[[[24,-82],[27,-79]]],
            'FilterMessageTypes':['PositionReport']}))
        confirmed=False
        async for frame in socket:
            event=json.loads(frame)
            if 'error' in event or 'Error' in event:
                raise RuntimeError('AISSTREAM_SUBSCRIPTION_REJECTED')
            if event.get('MessageType')=='SubscriptionConfirmation':
                confirmed=True
                continue
            if not confirmed or event.get('MessageType')!='PositionReport':
                continue
            mmsi=str((event.get('MetaData') or {}).get('MMSI') or '')
            if not re.fullmatch('[0-9]{9}',mmsi):
                continue
            with registry.cursor() as cr:
                try:
                    env=api.Environment(cr,SUPERUSER_ID,{'tracking_disable':True,'mail_create_nosubscribe':True})
                    import odoo.addons.step_export_control as addon
                    assert Path(addon.__file__).resolve().parent.parent.name==a.commit
                    model=env['step.export.vessel']
                    if model.search([('mmsi','=',mmsi)]):
                        continue  # never write a customer's existing vessel
                    candidate=model.create({'name':'PRUEBA AISStream temporal','company_id':env.company.id,'mmsi':mmsi})
                    with patch.object(type(model),'search',return_value=candidate):
                        model._ingest_ais_event(event)
                    if candidate.ais_reported_at and timedelta(0)<=fields.Datetime.now()-candidate.ais_reported_at<timedelta(hours=2):
                        return
                finally:
                    cr.rollback()
    raise RuntimeError('AISSTREAM_NO_CURRENT_POSITION')


try:
    asyncio.run(asyncio.wait_for(verify(),timeout=45))
    # Record only the actual successful provider connection after the business
    # test transaction has rolled back. This is also accurate when no customer
    # MMSIs are configured yet and the persistent collector is waiting for them.
    with registry.cursor() as cr:
        env=api.Environment(cr,SUPERUSER_ID,{})
        env['ir.config_parameter'].sudo().set_param('step_export_control.ais_heartbeat',
            fields.Datetime.to_string(fields.Datetime.now()))
        cr.commit()
    registry.signal_changes()
    print('AISSTREAM_LIVE_DATA_VERIFIED '+json.dumps({'environment':a.environment,'commit':a.commit,
        'authentication':True,'live_position_parsed':True,'test_transaction_rolled_back':True,
        'connection_timestamp_recorded':True}),flush=True)
except Exception as error:
    # Do not print provider response bodies, subscription frames or key values.
    print('AISSTREAM_LIVE_CHECK_FAILED '+type(error).__name__,flush=True)
    raise SystemExit(1)
