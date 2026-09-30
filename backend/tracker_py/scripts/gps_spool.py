"""Durable adapter boundary for a VERIFIED receiver, not a Coban decoder.

enqueue reads a normalized PointInput JSON from stdin and fsyncs it to SQLite.
flush retries stored events; API deduplication handles response loss. Never
connect this adapter to a firmware/protocol without captured-frame tests.
"""
import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from jose import jwt
from app.main import app  # Match API model registration in standalone workers.
from app.routers.fleet import PointInput, bridge_keys

parser = argparse.ArgumentParser()
parser.add_argument('operation', choices=['enqueue', 'flush'])
parser.add_argument('--queue', required=True)
args = parser.parse_args()
db = sqlite3.connect(args.queue)
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA synchronous=FULL')
db.execute('CREATE TABLE IF NOT EXISTS outbox (device TEXT, source TEXT, payload TEXT, PRIMARY KEY(device, source))')
if args.operation == 'enqueue':
    point = PointInput.model_validate(json.load(sys.stdin))
    db.execute('INSERT OR IGNORE INTO outbox VALUES (?, ?, ?)', (point.device_id, point.source_id, point.model_dump_json()))
    db.commit()
else:
    issuer = os.environ['GPS_ISSUER']
    key = bridge_keys()[issuer]
    for device, source, payload in db.execute('SELECT device, source, payload FROM outbox ORDER BY rowid LIMIT 500').fetchall():
        stamp = int(datetime.now(timezone.utc).timestamp())
        token = jwt.encode({'iss': issuer, 'aud': 'steps-tracker-v1', 'sub': 'receiver:verified-adapter',
                            'company_id': int(os.environ['GPS_COMPANY_ID']), 'role': 'ingestor', 'iat': stamp, 'exp': stamp+60}, key, algorithm='HS256')
        request = Request('http://127.0.0.1:8000/v1/ingest/positions', data=payload.encode(), headers={'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'})
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
            if not result.get('id'):
                raise RuntimeError('Missing durable receipt')
        db.execute('DELETE FROM outbox WHERE device=? AND source=?', (device, source))
        db.commit()
print(json.dumps({'queued': db.execute('SELECT count(*) FROM outbox').fetchone()[0]}))
