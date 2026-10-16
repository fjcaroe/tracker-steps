"""Persistent, server-only AISStream receiver. Run as the target Odoo service user.

Credentials come solely from AISSTREAM_API_KEY in a private environment file.
Neither credentials nor full provider messages are logged or sent to a browser.
"""
import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import random
import sys
import time

import websockets

LOG=logging.getLogger('steps.ais')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment',choices=('development','cerro'))
    args=parser.parse_args()
    registry_path=Path(__file__).with_name('environments.json')
    target=json.loads(registry_path.read_text())['environments'][args.environment]
    key=os.environ.get('AISSTREAM_API_KEY','').strip()
    if not key:
        raise SystemExit('AISStream: configure la clave privada antes de activar el colector.')
    sys.path.insert(0,'/opt/odoo18')
    import odoo
    from odoo import api, SUPERUSER_ID
    odoo.tools.config.parse_config(['-c',target['config'],'-d',target['database'],'--no-http'])
    registry=odoo.registry(target['database'])

    def mmsis():
        with registry.cursor() as cr:
            env=api.Environment(cr,SUPERUSER_ID,{})
            values=sorted(set(env['step.export.vessel'].search([('mmsi','!=',False)]).mapped('mmsi')))
            if len(values)>200:
                raise ValueError('AISSTREAM_MMSI_LIMIT')
            return values

    def persist(events,heartbeat=False):
        with registry.cursor() as cr:
            env=api.Environment(cr,SUPERUSER_ID,{'tracking_disable':True,'mail_create_nosubscribe':True})
            for event in events:
                env['step.export.vessel']._ingest_ais_event(event)
            if heartbeat:
                env['ir.config_parameter'].sudo().set_param('step_export_control.ais_heartbeat',datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            cr.commit()

    async def receive():
        delay=2
        while True:
            try:
                identifiers=mmsis()
                if not identifiers:
                    await asyncio.sleep(30)
                    continue
                async with websockets.connect('wss://stream.aisstream.io/v0/stream',compression='deflate',
                        ping_interval=20,ping_timeout=20,open_timeout=15,max_size=262144,max_queue=2048) as socket:
                    await socket.send(json.dumps({'APIKey':key,'BoundingBoxes':[[[-90,-180],[90,180]]],
                        'FiltersShipMMSI':identifiers,'FilterMessageTypes':['PositionReport','StandardClassBPositionReport','ExtendedClassBPositionReport']}))
                    buffer=[];flushed=time.monotonic();refreshed=flushed;confirmed=False
                    while True:
                        try:
                            frame=await asyncio.wait_for(socket.recv(),timeout=10)
                            event=json.loads(frame)
                            if 'error' in event or 'Error' in event:
                                raise ValueError('AISSTREAM_SUBSCRIPTION_REJECTED')
                            if event.get('MessageType')=='SubscriptionConfirmation':
                                confirmed=True;delay=2;persist([],heartbeat=True)
                                LOG.info('AISStream conectado; %s MMSI configurados',len(identifiers))
                            elif confirmed:
                                buffer.append(event)
                        except asyncio.TimeoutError:
                            pass
                        now=time.monotonic()
                        if confirmed and (buffer and now-flushed>=3 or now-flushed>=60):
                            persist(buffer,heartbeat=True);buffer=[];flushed=now
                        if now-refreshed>=60:
                            current=mmsis();refreshed=now
                            if current!=identifiers:
                                persist(buffer)
                                break  # reconnect with the new complete subscription
            except (OSError,ValueError,websockets.exceptions.WebSocketException,asyncio.TimeoutError) as error:
                # Exception text can contain server echoes. Log only its type.
                LOG.warning('AISStream desconectado (%s); se reintentará',type(error).__name__)
                await asyncio.sleep(delay+random.random());delay=min(120,delay*2)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(receive())


if __name__=='__main__':
    main()
