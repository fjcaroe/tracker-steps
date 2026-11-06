"""Bounded background worker; no raw telemetry or master data is rewritten."""
import argparse
from app.db.session import SessionLocal
from app.services.gps_analytics import rebuild

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--limit', type=int, default=500)
    args = parser.parse_args()
    with SessionLocal() as db:
        print('GPS_ANALYTICS_REFRESHED', rebuild(db, min(5000,max(1,args.limit))))
