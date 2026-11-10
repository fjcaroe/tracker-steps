"""Bounded passive GPS103 audit. Never sends a device command or saves packets.

Run on the receiver host as root, with the exact asset UUID. Output contains
only timings/counts and allowlisted non-secret settings, never IMEI/coordinates.
Requires tcpdump and this repository on PYTHONPATH. Capture is limited to TCP5001.
"""
import argparse,collections,json,os,statistics,struct,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import UUID
from receivers.coban.protocol import Framer,InvalidFrame,identify,decode


def packet_tcp(packet,link):
    offsets={1:14,113:16,276:20,101:0}
    offset=offsets.get(link)
    if offset is None or len(packet)<offset+20:return None
    ip=packet[offset:]
    if ip[0]>>4!=4 or ip[9]!=6 or int.from_bytes(ip[6:8],'big')&0x1fff:return None
    total=int.from_bytes(ip[2:4],'big')
    if total<40 or total>len(ip):return None
    ip=ip[:total]
    ihl=(ip[0]&15)*4
    if ihl<20 or len(ip)<ihl+20:return None
    tcp=ip[ihl:];src,dst,sequence=struct.unpack('!HHI',tcp[:8]);header=(tcp[12]>>4)*4
    if header<20 or len(tcp)<header:return None
    flow=(ip[12:16],src,ip[16:20],dst)
    return flow,sequence,tcp[13],tcp[header:]


class Audit:
    def __init__(self,imei):
        self.imei=imei;self.flows=set();self.framers={};self.sequences={}
        self.counts=collections.Counter();self.heartbeats=[];self.ack_ms=[]
        self.pending={};self.delays=[];self.settings=[]

    def accept(self,flow,sequence,flags,payload,at):
        outgoing=flow[1]==5001
        key=(flow[2],flow[3],flow[0],flow[1]) if outgoing else flow
        if not outgoing and (payload.startswith(self.imei.encode()) or ('imei:'+self.imei+',').encode() in payload):self.flows.add(key)
        if key not in self.flows:return
        if flags&4:self.counts['tcp_reset']+=1
        elif flags&1:self.counts['tcp_fin']+=1
        if not payload:return
        previous=self.sequences.get(flow)
        if previous is not None and sequence<previous:
            self.counts['retransmitted_or_overlapping_packets']+=1;return
        if previous is not None and sequence>previous:
            self.counts['capture_stream_gaps']+=1;self.framers.pop(flow,None)
        self.sequences[flow]=sequence+len(payload)
        if outgoing:
            if payload in (b'ON',b'LOAD'):
                self.counts['server_'+payload.decode()]+=1
                stamp=self.pending.pop((key,payload),None)
                if stamp is not None:self.ack_ms.append(round((at-stamp)*1000,3))
            return
        try:frames=self.framers.setdefault(flow,Framer()).feed(payload)
        except InvalidFrame:
            self.counts['capture_unframed']+=1;self.framers.pop(flow,None);return
        for frame in frames:
            try:
                device,kind=identify(frame)
                if device!=self.imei:continue
                self.counts[kind]+=1
                if kind=='heartbeat':self.heartbeats.append(at);self.pending[(key,b'ON')]=at
                elif kind=='login':self.pending[(key,b'LOAD')]=at
                elif kind=='status':
                    fields=frame.decode('ascii').strip(';\r\n').split(',')
                    # Status contains passwords/phone numbers: only these 3 fields leave memory.
                    if fields[2] in ('0','1','2') and all(v.isdecimal() and len(v)<=6 for v in fields[3:5]):
                        self.settings.append({'observed_at':datetime.fromtimestamp(at,timezone.utc).isoformat(),
                            'mode':int(fields[2]),
                            'moving_seconds':int(fields[3]) if fields[2]!='2' else None,
                            'stationary_seconds':int(fields[4]) if fields[2]!='2' else None})
                else:
                    p=decode(frame,datetime.fromtimestamp(at,timezone.utc))
                    if p is None:self.counts['no_valid_gps']+=1
                    else:self.delays.append(round(at-datetime.fromisoformat(p['recorded_at']).timestamp(),3))
            except (InvalidFrame,UnicodeError,ValueError):self.counts['unclassified_data']+=1

    def report(self):
        intervals=[round(b-a,3) for a,b in zip(self.heartbeats,self.heartbeats[1:])]
        def summary(values):return {'count':len(values),'minimum':min(values),'median':statistics.median(values),'maximum':max(values)} if values else {'count':0}
        return {'counts':dict(self.counts),'observed_connections':len(self.flows),
                'heartbeat_interval_seconds':summary(intervals),'acknowledgement_ms':summary(self.ack_ms),
                'gps_arrival_delay_seconds':summary(self.delays),'settings':self.settings,
                'raw_packets_saved':False,'commands_sent':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset',type=UUID,required=True)
    parser.add_argument('--seconds',type=int,default=240)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();assert os.geteuid()==0 and 30<=args.seconds<=600
    sql="SELECT d.imei FROM gps_assignments a JOIN gps_devices d ON d.id=a.device_id WHERE a.asset_id='"+str(args.asset)+"' AND a.valid_to IS NULL"
    imei=subprocess.check_output(['sudo','-u','postgres','psql','-d','tracker_steps','-Atc',sql],text=True).strip()
    assert len(imei)==15 and imei.isdecimal(),'Expected one assigned GPS'
    audit=Audit(imei)
    process=subprocess.Popen(['timeout',str(args.seconds+2),'tcpdump','-i','any','-p','-nn','-s','0','-U','-w','-','tcp port 5001'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        header=process.stdout.read(24)
        assert len(header)==24 and header[:4] in (b'\xd4\xc3\xb2\xa1',b'\xa1\xb2\xc3\xd4'),'Unsupported capture format'
        endian='<' if header[:4]==b'\xd4\xc3\xb2\xa1' else '>'
        link=struct.unpack(endian+'I',header[20:24])[0]
        while True:
            h=process.stdout.read(16)
            if len(h)!=16:break
            sec,micro,size,_=struct.unpack(endian+'IIII',h)
            assert size<=262144,'Oversized capture'
            packet=process.stdout.read(size)
            if len(packet)!=size:break
            parsed=packet_tcp(packet,link)
            if parsed:audit.accept(*parsed,sec+micro/1000000)
    finally:
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    report=audit.report();report['observed_seconds']=args.seconds
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2));args.output.chmod(0o600)
    print(json.dumps(report))


if __name__=='__main__':main()
