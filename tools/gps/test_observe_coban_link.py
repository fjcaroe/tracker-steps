import json,unittest,struct
from tools.gps.observe_coban_link import Audit,packet_tcp

class PassiveAuditTests(unittest.TestCase):
    def test_allowlisted_settings_and_ack_without_identifiers(self):
        imei='990000000000001';a=Audit(imei)
        flow=(b'peer',14000,b'host',5001);reverse=(b'host',5001,b'peer',14000)
        frame=('imei:'+imei+',status,0,10,3600,'+','.join(['PRIVATE']*17)+';').encode()
        a.accept(flow,1,0,frame,1000)
        a.accept(flow,len(frame)+1,0,imei.encode()+b';',1001)
        a.accept(reverse,10,0,b'ON',1001.002)
        a.accept(flow,len(frame)+17,0,imei.encode()+b';',1061)
        a.accept(reverse,12,0,b'ON',1061.003)
        report=a.report();text=json.dumps(report)
        self.assertNotIn(imei,text);self.assertNotIn('PRIVATE',text)
        self.assertEqual(report['settings'][0]['mode'],0)
        self.assertEqual(report['heartbeat_interval_seconds']['median'],60)
        self.assertEqual(report['acknowledgement_ms']['count'],2)
        self.assertEqual(report['commands_sent'],0)

    def test_tcp_padding_is_not_application_data(self):
        ip=bytearray(20);ip[0]=0x45;ip[9]=6;ip[2:4]=struct.pack('!H',42)
        tcp=bytearray(20);tcp[:8]=struct.pack('!HHI',5001,14000,10);tcp[12]=0x50
        parsed=packet_tcp(bytes(ip+tcp)+b'ON'+b'\x00'*8,101)
        self.assertEqual(parsed[-1],b'ON')
        self.assertIsNone(packet_tcp(b'broken',113))

    def test_power_saving_schedule_is_not_seconds(self):
        imei='990000000000001';a=Audit(imei)
        frame=('imei:'+imei+',status,2,0930,1,'+','.join(['PRIVATE']*17)+';').encode()
        a.accept((b'peer',14000,b'host',5001),1,0,frame,1000)
        settings=a.report()['settings'][0]
        self.assertEqual(settings['mode'],2)
        self.assertIsNone(settings['moving_seconds']);self.assertIsNone(settings['stationary_seconds'])

    def test_other_device_is_never_reported(self):
        a=Audit('990000000000001')
        a.accept((b'peer',14000,b'host',5001),1,0,b'990000000000002;',1000)
        self.assertEqual(a.report()['observed_connections'],0)
        self.assertEqual(a.report()['counts'],{})

if __name__=='__main__':unittest.main()
