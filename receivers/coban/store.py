"""Bounded durable inbox, private capture and retry queue. No raw data in logs."""
from contextlib import contextmanager
import json
import sqlite3
import time
from datetime import datetime, timezone


class Store:
    def __init__(self,path,maximum=1000000,receipts=20000):
        self.path=str(path);self.maximum=maximum;self.receipts=receipts
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS inbox(source TEXT PRIMARY KEY, imei TEXT NOT NULL, route TEXT NOT NULL, payload TEXT NOT NULL, queued REAL NOT NULL, delivered REAL, attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS capture(id INTEGER PRIMARY KEY, imei TEXT, received REAL, frame BLOB, reason TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, count INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS observations(imei TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS relay_attempts(id TEXT PRIMARY KEY, attempted REAL NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS inbox_delivery ON inbox(delivered,queued)')
            db.execute('CREATE INDEX IF NOT EXISTS inbox_retry ON inbox(retry_at,queued) WHERE delivered IS NULL')
            db.execute('CREATE TABLE IF NOT EXISTS queue_state(id INTEGER PRIMARY KEY CHECK(id=1),pending INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO queue_state SELECT 1,count(*) FROM inbox WHERE delivered IS NULL')
            db.execute('CREATE TRIGGER IF NOT EXISTS queue_insert AFTER INSERT ON inbox WHEN NEW.delivered IS NULL BEGIN UPDATE queue_state SET pending=pending+1 WHERE id=1; END')
            db.execute('CREATE TRIGGER IF NOT EXISTS queue_deliver AFTER UPDATE OF delivered ON inbox WHEN OLD.delivered IS NULL AND NEW.delivered IS NOT NULL BEGIN UPDATE queue_state SET pending=pending-1 WHERE id=1; END')
            db.execute('CREATE TRIGGER IF NOT EXISTS queue_delete AFTER DELETE ON inbox WHEN OLD.delivered IS NULL BEGIN UPDATE queue_state SET pending=pending-1 WHERE id=1; END')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=3)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:yield db
        finally:db.close()

    def count(self,name):
        with self.connection() as db:
            db.execute('INSERT INTO counters VALUES (?,1) ON CONFLICT(name) DO UPDATE SET count=count+1',(name,))

    def claim_relay(self, command_id):
        with self.connection() as db:
            db.execute('DELETE FROM relay_attempts WHERE attempted<?',(time.time()-7*86400,))
            if db.execute('SELECT count(*) FROM relay_attempts').fetchone()[0]>=20000:return False
            return db.execute('INSERT OR IGNORE INTO relay_attempts VALUES (?,?)',(command_id,time.time())).rowcount==1

    def observe(self,imei,point=None,error=None):
        stamp=datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            previous=db.execute('SELECT payload FROM observations WHERE imei=?',(imei,)).fetchone()
            value=json.loads(previous[0]) if previous else {'imei':imei}
            value.update(last_seen_at=stamp,error=error)
            # Historical replay is welcome, but never regresses live location or
            # the safety proof used by supervised starter control.
            if point and (not value.get('fix_at') or datetime.fromisoformat(point['recorded_at'])>=datetime.fromisoformat(value['fix_at'])):
                value.update(fix_at=point['recorded_at'],fix_received_at=stamp,lat=point['lat'],lon=point['lon'],speed_kmh=point.get('speed_kmh'))
            db.execute('INSERT INTO observations VALUES (?,?) ON CONFLICT(imei) DO UPDATE SET payload=excluded.payload',(imei,json.dumps(value)))

    def observations(self,imeis):
        with self.connection() as db:
            values=[]
            for imei in imeis:
                row=db.execute('SELECT payload FROM observations WHERE imei=?',(imei,)).fetchone()
                if row:
                    value=json.loads(row[0]);value['pending']=db.execute('SELECT count(*) FROM inbox WHERE imei=? AND delivered IS NULL',(imei,)).fetchone()[0]
                    values.append(value)
            return values

    def capture(self,imei,frame,reason):
        with self.connection() as db:
            db.execute('INSERT INTO capture(imei,received,frame,reason) VALUES (?,?,?,?)',(imei,time.time(),frame[:4096],reason))
            db.execute('DELETE FROM capture WHERE id NOT IN (SELECT id FROM capture ORDER BY id DESC LIMIT 200)')

    def enqueue(self,imei,source,route,payload):
        with self.connection() as db:
            if db.execute('SELECT 1 FROM inbox WHERE source=?',(source,)).fetchone():return
            if db.execute('SELECT pending FROM queue_state WHERE id=1').fetchone()[0]>=self.maximum:raise RuntimeError('queue_full')
            db.execute('INSERT INTO inbox(source,imei,route,payload,queued) VALUES (?,?,?,?,?)',(source,imei,json.dumps(route),json.dumps(payload),time.time()))

    def pending(self):
        with self.connection() as db:
            return db.execute('SELECT source,imei,route,payload,attempts FROM inbox WHERE delivered IS NULL AND retry_at<=? ORDER BY queued LIMIT 50',(time.time(),)).fetchall()

    def result(self,source,delivered,attempts):
        with self.connection() as db:
            if delivered:
                db.execute('UPDATE inbox SET delivered=? WHERE source=?',(time.time(),source))
                db.execute('DELETE FROM inbox WHERE delivered<?',(time.time()-7*86400,))
                if db.execute('SELECT count(*) FROM inbox WHERE delivered IS NOT NULL').fetchone()[0]>self.receipts:
                    db.execute('DELETE FROM inbox WHERE delivered IS NOT NULL AND source NOT IN (SELECT source FROM inbox WHERE delivered IS NOT NULL ORDER BY delivered DESC LIMIT ?)',(self.receipts,))
            else:db.execute('UPDATE inbox SET attempts=?,retry_at=? WHERE source=?',(attempts+1,time.time()+min(300,2**min(attempts+1,8)),source))

    def status(self):
        with self.connection() as db:
            return {'queued':db.execute('SELECT count(*) FROM inbox WHERE delivered IS NULL').fetchone()[0],
                    'capacity':self.maximum,
                    'oldest_pending_at':db.execute('SELECT min(queued) FROM inbox WHERE delivered IS NULL').fetchone()[0],
                    'max_retry_attempts':db.execute('SELECT COALESCE(max(attempts),0) FROM inbox WHERE delivered IS NULL').fetchone()[0],
                    'delivered_retained':db.execute('SELECT count(*) FROM inbox WHERE delivered IS NOT NULL').fetchone()[0],
                    'last_delivered':db.execute('SELECT max(delivered) FROM inbox').fetchone()[0],
                    'private_captures':db.execute('SELECT count(*) FROM capture').fetchone()[0],
                    'counters':dict(db.execute('SELECT name,count FROM counters'))}
