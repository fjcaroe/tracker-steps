"""Strict GPS103 ASCII subset. No guessed binary decoding or actuator commands.

Protocol reference: Traccar Gps103ProtocolDecoder (Apache-2.0), independently
implemented here. Regular NMEA degree/minute positions and decimal ALT frames
are distinct formats with different speed units. Clock must be set to UTC.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import math
import re


class InvalidFrame(ValueError):pass


class Framer:
    def __init__(self):self.buffer=b''

    def feed(self,data):
        self.buffer+=data
        if len(self.buffer)>16384:raise InvalidFrame('oversize')
        frames=[]
        while self.buffer:
            self.buffer=self.buffer.lstrip(b'\r\n\x00')
            if not self.buffer:break
            login=re.match(rb'##,imei:\d{15},A',self.buffer)
            if login:
                size=login.end()
                if self.buffer[size:size+1]==b';':size+=1
            elif len(self.buffer)>=15 and self.buffer[:15].isdigit():size=15
            else:
                ends=[i for i in (self.buffer.find(b';'),self.buffer.find(b'*'),self.buffer.find(b'\n')) if i>=0]
                if not ends:break
                size=min(ends)+1
            if size>4096:raise InvalidFrame('oversize')
            frames.append(self.buffer[:size]);self.buffer=self.buffer[size:]
        return frames


def identify(frame):
    text=frame.decode('ascii',errors='strict').strip(';\r\n\x00')
    if re.fullmatch(r'\d{15}',text):return text,'heartbeat'
    found=re.match(r'(##,)?imei:(\d{15}),',text)
    if not found:raise InvalidFrame('identity')
    if found[1] and text.endswith(',A'):return found[2],'login'
    # December 2023 status synchronization contains configuration, including
    # credentials, but no GPS coordinates. Never persist it as a raw capture.
    if len(text.split(','))>=21 and re.match('imei:'+found[2]+r',status,[012],\d{1,6},\d{1,6},',text):return found[2],'status'
    return found[2],'data'


def number(text):
    value=float(text)
    if not math.isfinite(value):raise InvalidFrame('non_finite')
    return value


def coordinate(value,hemisphere,latitude):
    if hemisphere not in (('N','S') if latitude else ('E','W')):raise InvalidFrame('hemisphere')
    raw=number(value)
    if raw<0:raise InvalidFrame('coordinate')
    degrees=int(raw//100);minutes=raw-degrees*100
    result=degrees+minutes/60
    if minutes>=60 or result>(90 if latitude else 180):raise InvalidFrame('coordinate')
    return -result if hemisphere in ('S','W') else result


def decode(frame,now=None):
    """Return an actual GPS fix or None; LBS/invalid fixes never fabricate a point."""
    now=now or datetime.now(timezone.utc)
    try:
        imei,kind=identify(frame)
        if kind!='data':return None
        text=frame.decode('ascii').strip(';*\r\n\x00')
        fields=text.split(',')
        alarm=fields[1]
        if len(fields)>5 and fields[4]=='L':return None
        acc=None;power=None
        if len(fields)>11 and fields[4]=='F':
            if fields[6]!='A':return None
            # Devices are configured UTC; use local date + UTC clock, including
            # nearest-day correction when the local/date field lags at midnight.
            local=re.sub(r'[/ :]', '',fields[2])
            if len(local) not in (10,12):raise InvalidFrame('date')
            stamp=datetime.strptime(local[:6]+fields[5].split('.')[0],'%y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            local_stamp=datetime.strptime(local[:10],'%y%m%d%H%M').replace(tzinfo=timezone.utc)
            if stamp-local_stamp>timedelta(hours=12):stamp-=timedelta(days=1)
            elif local_stamp-stamp>timedelta(hours=12):stamp+=timedelta(days=1)
            lat=coordinate(fields[7],fields[8],True);lon=coordinate(fields[9],fields[10],False)
            speed=number(fields[11])*1.852 if fields[11] else None
            if len(fields)>14 and fields[14] in ('0','1'):acc=fields[14]=='1'
        elif len(fields)>=19 and frame.rstrip().endswith(b'*'):
            if fields[8]=='0':return None
            if fields[8] not in ('1','2'):raise InvalidFrame('fix')
            stamp=datetime.strptime(fields[6]+fields[5],'%d%m%y%H%M%S').replace(tzinfo=timezone.utc)
            lat=number(fields[9]);lon=number(fields[10]);speed=number(fields[11])
            if fields[16] in ('0','1'):acc=fields[16]=='1'
            # ALT charge/battery state does not prove external power presence.
        else:raise InvalidFrame('unsupported_format')
        if not -90<=lat<=90 or not -180<=lon<=180:raise InvalidFrame('coordinate')
        if speed is not None and not 0<=speed<=300:raise InvalidFrame('speed')
        if stamp>now+timedelta(minutes=5) or stamp<datetime(2020,1,1,tzinfo=timezone.utc):raise InvalidFrame('clock')
        if alarm=='acc on':acc=True
        elif alarm=='acc off':acc=False
        if alarm=='ac alarm':power=False
        return {'recorded_at':stamp.isoformat(),'lat':lat,'lon':lon,'speed_kmh':speed,
                'quality':'gps','acc':acc,'external_power':power,'sos':alarm=='help me'}
    except (ValueError,IndexError,UnicodeError,OverflowError) as exc:
        if isinstance(exc,InvalidFrame):raise
        raise InvalidFrame('malformed') from None


def source_id(frame):
    return 'gps103:'+hashlib.sha256(frame.strip(b';\r\n\x00')).hexdigest()
