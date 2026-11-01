import asyncio
import base64
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from .protocol import Framer,InvalidFrame,decode,identify,source_id
from .server import Receiver,flush,mapping,token,poll_configuration
from .store import Store

IMEI='000000000000001'
NOW=datetime(2026,10,31,23,59,tzinfo=timezone.utc)
FRAME=('imei:'+IMEI+',tracker,261031230000,,F,230000.000,A,3300.0000,S,07000.0000,W,10.00,0,,1,0,;').encode()


class ProtocolTests(unittest.TestCase):
    def test_regular_fix_and_units(self):
        p=decode(FRAME,NOW)
        self.assertEqual((p['lat'],p['lon'],p['acc']),(-33,-70,True));self.assertAlmostEqual(p['speed_kmh'],18.52)
        self.assertIsNone(p['external_power']);self.assertEqual(p['recorded_at'],'2026-10-31T23:00:00+00:00')

    def test_alt_decimal_format_and_units(self):
        raw=('imei:'+IMEI+',unit,---,------,----,230000,311026,26,1,-33.42317,-70.61930,067,229,0674,1.00,08,0,1,---,*').encode()
        p=decode(raw,NOW);self.assertEqual(p['speed_kmh'],67);self.assertEqual(p['lat'],-33.42317);self.assertFalse(p['acc']);self.assertIsNone(p['external_power'])

    def test_invalid_fix_and_lbs_do_not_make_positions(self):
        self.assertIsNone(decode(FRAME.replace(b',A,',b',V,'),NOW))
        self.assertIsNone(decode(('imei:'+IMEI+',tracker,000000000,,L,;').encode(),NOW))

    def test_midnight_rollover(self):
        p=decode(FRAME.replace(b'261031230000',b'261031235900').replace(b'230000.000',b'000001.000'),datetime(2026,11,1,0,2,tzinfo=timezone.utc))
        self.assertTrue(p['recorded_at'].startswith('2026-11-01T00:00:01'))

    def test_invalid_payloads(self):
        for raw in [b'\xff;',b'garbage;',FRAME.replace(b'3300.0000',b'3360.0000'),FRAME.replace(b'07000.0000',b'19000.0000'),FRAME.replace(b'10.00',b'NaN'),FRAME.replace(b'10.00',b'9999'),FRAME.replace(b'261031',b'991031')]:
            with self.subTest(raw=raw[:8]),self.assertRaises((InvalidFrame,UnicodeError)):decode(raw,NOW)

    def test_future_clock(self):
        with self.assertRaises(InvalidFrame):decode(FRAME,datetime(2026,10,30,tzinfo=timezone.utc))

    def test_alarm_fields_are_explicit(self):
        self.assertTrue(decode(FRAME.replace(b',tracker,',b',help me,'),NOW)['sos'])
        self.assertFalse(decode(FRAME.replace(b',tracker,',b',ac alarm,'),NOW)['external_power'])

    def test_framing_split_login_heartbeat_and_combined_packets(self):
        f=Framer();login=('##,imei:'+IMEI+',A').encode()
        self.assertEqual(f.feed(login[:10]),[])
        self.assertEqual(f.feed(login[10:]+IMEI.encode()+FRAME+FRAME),[login,IMEI.encode(),FRAME,FRAME])

    def test_split_position(self):
        f=Framer();self.assertEqual(f.feed(FRAME[:35]),[]);self.assertEqual(f.feed(FRAME[35:]),[FRAME])

    def test_frame_bounds(self):
        with self.assertRaises(InvalidFrame):Framer().feed(b'x'*17000)
        with self.assertRaises(InvalidFrame):Framer().feed(b'x'*5000+b';')

    def test_stable_dedup_identifier(self):
        self.assertEqual(source_id(FRAME),source_id(FRAME+b'\r\n'));self.assertNotEqual(source_id(FRAME),source_id(FRAME.replace(b'10.00',b'11.00')))


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.map=self.root/'devices.json';self.route={'issuer':'CERRO_EL_PLOMO','company_id':2,'mode':'forward','device_id':'00000000-0000-4000-8000-000000000001'}
        self.map.write_text(json.dumps({IMEI:self.route}));self.store=Store(self.root/'inbox.sqlite');self.receiver=Receiver(self.store,self.map)
        self.key=self.root/'key.json';self.key.write_text(json.dumps({'issuer':'CERRO_EL_PLOMO','key':'test-only-coban-key'}))

    def tearDown(self):self.tmp.cleanup()

    def process(self,frame=FRAME):
        if not hasattr(self,'fixed_now'):self.fixed_now=datetime.now(timezone.utc)
        now=self.fixed_now
        frame=frame.replace(b'261031230000',now.strftime('%y%m%d%H%M%S').encode()).replace(b'230000.000',now.strftime('%H%M%S').encode()+b'.000')
        return self.receiver.process(frame)

    def test_known_login_heartbeat_and_unknown_denial(self):
        self.assertEqual(self.receiver.process(('##,imei:'+IMEI+',A').encode()),b'LOAD')
        self.assertEqual(self.receiver.process(IMEI.encode()),b'ON')
        with self.assertRaises(InvalidFrame):self.receiver.process(b'000000000000002')
        self.assertEqual(self.store.status()['private_captures'],0)

    def test_durable_restart_and_dedup(self):
        self.process();self.process()
        restored=Store(self.root/'inbox.sqlite');self.assertEqual(restored.status()['queued'],1)
        self.assertEqual(len(restored.pending()),1)

    def test_capture_mode_never_creates_outbox(self):
        self.route['mode']='capture';self.map.write_text(json.dumps({IMEI:self.route}))
        self.process();self.assertEqual(self.store.status()['queued'],0);self.assertEqual(self.store.status()['private_captures'],1)
        observations=self.store.observations([IMEI]);self.assertEqual(observations[0]['lat'],-33)
        self.assertEqual(Store(self.root/'inbox.sqlite').observations([IMEI]),observations)

    def test_configuration_revocation_and_outage_cache(self):
        replies={'devices':[]};requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(inner):
                requests.append(json.loads(inner.rfile.read(int(inner.headers['Content-Length']))))
                inner.send_response(200);inner.end_headers();inner.wfile.write(json.dumps(replies).encode())
            def log_message(self,*args):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        cfg={'mapping':str(self.map),'key_file':str(self.key),'api':'http://127.0.0.1:'+str(http.server_port),'companies':[2]}
        try:
            self.process();poll_configuration(self.store,cfg);self.assertEqual(mapping(self.map),{})
            self.assertEqual(requests[0]['observations'][0]['lat'],-33)
            replies['devices']=[{'imei':IMEI,**self.route}]
            poll_configuration(self.store,cfg);self.assertEqual(mapping(self.map)[IMEI],self.route)
            replies['devices'][0]['company_id']=3
            poll_configuration(self.store,cfg);self.assertEqual(mapping(self.map)[IMEI]['company_id'],2)
        finally:http.shutdown();http.server_close();thread.join()
        cfg['api']='http://127.0.0.1:1';poll_configuration(self.store,cfg)
        self.assertEqual(mapping(self.map)[IMEI]['company_id'],2)

    def test_invalid_known_frame_is_private_and_bounded(self):
        for _ in range(205):self.receiver.process(('imei:'+IMEI+',unknown;').encode())
        self.assertEqual(self.store.status()['private_captures'],200);self.assertEqual(self.store.status()['queued'],0)

    def test_map_change_hot_reload_and_wrong_issuer(self):
        self.map.write_text('{}')
        with self.assertRaises(InvalidFrame):self.process()
        self.route['issuer']='LAB_TAREAS';self.map.write_text(json.dumps({IMEI:self.route}))
        with self.assertRaises(ValueError):mapping(self.map)

    def test_queue_limit_has_no_sos_ack(self):
        self.store.maximum=0
        with self.assertRaises(RuntimeError):self.process(FRAME.replace(b',tracker,',b',help me,'))

    def test_receipt_retention_is_bounded_without_deleting_pending(self):
        self.store.receipts=2
        for n in range(4):
            self.store.enqueue(IMEI,str(n),{},{});self.store.result(str(n),True,0)
        self.store.enqueue(IMEI,'pending',{},{});
        self.assertEqual(self.store.status()['delivered_retained'],2)
        self.assertEqual(self.store.status()['queued'],1)

    def test_no_reroute_on_mapping_change(self):
        self.process();self.route['company_id']=3;self.map.write_text(json.dumps({IMEI:self.route}))
        flush(self.store,{'mapping':str(self.map),'key_file':str(self.key),'api':'http://127.0.0.1:1'})
        self.assertEqual(self.store.status()['queued'],1)

    def test_signed_jwt_has_tenant_and_no_unbounded_lifetime(self):
        value=token('CERRO_EL_PLOMO',2,'test-only-key')
        claims=json.loads(base64.urlsafe_b64decode(value.split('.')[1]+'=='))
        self.assertEqual((claims['company_id'],claims['role'],claims['exp']-claims['iat']),(2,'ingestor',60))

    def test_http_retry_then_receipt_and_restart_dedup(self):
        self.process();seen=[];accept={'ok':False}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(inner):
                seen.append(json.loads(inner.rfile.read(int(inner.headers['Content-Length']))))
                inner.send_response(200 if accept['ok'] else 503);inner.end_headers();inner.wfile.write(b'{"id":"durable-test-receipt"}')
            def log_message(self,*args):pass
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        cfg={'mapping':str(self.map),'key_file':str(self.key),'api':'http://127.0.0.1:'+str(http.server_port)}
        try:
            flush(self.store,cfg);self.assertEqual(self.store.status()['queued'],1)
            with self.store.connection() as db:db.execute('UPDATE inbox SET retry_at=0')
            accept['ok']=True;flush(self.store,cfg)
            self.assertEqual(self.store.status()['queued'],0);self.assertEqual(len(seen),2)
            self.process();self.assertEqual(self.store.status()['queued'],0)
        finally:http.shutdown();http.server_close();thread.join()

    def test_tcp_real_socket_split_and_unknown_close(self):
        async def scenario():
            listener=await asyncio.start_server(self.receiver.connection,'127.0.0.1',0)
            port=listener.sockets[0].getsockname()[1]
            try:
                reader,writer=await asyncio.open_connection('127.0.0.1',port)
                writer.write(('##,imei:'+IMEI[:5]).encode());await writer.drain()
                writer.write((IMEI[5:]+',A').encode());await writer.drain()
                self.assertEqual(await asyncio.wait_for(reader.readexactly(4),2),b'LOAD')
                writer.write(IMEI.encode());await writer.drain();self.assertEqual(await reader.readexactly(2),b'ON')
                writer.close();await writer.wait_closed()
                reader,writer=await asyncio.open_connection('127.0.0.1',port)
                writer.write(b'000000000000002');await writer.drain()
                self.assertEqual(await asyncio.wait_for(reader.read(),2),b'')
                writer.close();await writer.wait_closed()
            finally:listener.close();await listener.wait_closed()
        asyncio.run(scenario())


if __name__=='__main__':unittest.main()
