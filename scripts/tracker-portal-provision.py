"""Server-only provisioning, run as postgres. Never prints credentials.

Uses explicit Odoo DB/company mappings; leaves legacy GPS data unassigned.
The generated key file is consumed only by the API systemd unit.
"""
import json
import os
import secrets
import uuid
from pathlib import Path
import psycopg2

key_path = Path('/etc/tracker-bridge-keys.json')
keys = json.loads(key_path.read_text()) if key_path.exists() else {}
with psycopg2.connect(dbname='tracker_steps') as tracker:
    with tracker.cursor() as target:
        for database in ('LAB_TAREAS', 'STEPS_DEMO', 'CERRO_EL_PLOMO'):
            keys.setdefault(database, secrets.token_hex(32))
            with psycopg2.connect(dbname=database) as odoo:
                with odoo.cursor() as source:
                    source.execute('SELECT id,name FROM res_company')
                    companies = source.fetchall()
                    for company_id, name in companies:
                        target.execute('''INSERT INTO gps_tenants (id,issuer,company_id,name,timezone,retention_days)
                            VALUES (%s,%s,%s,%s,'America/Santiago',365) ON CONFLICT(issuer,company_id) DO UPDATE SET name=EXCLUDED.name RETURNING id''',
                            (str(uuid.uuid4()), database, company_id, name))
                        tenant_id = target.fetchone()[0]
                        # Read-only source inventory, one stable source identity per company.
                        source.execute('''SELECT v.id,COALESCE(v.license_plate,'Vehículo '||v.id),v.license_plate,v.create_date
                            FROM fleet_vehicle v WHERE v.company_id=%s AND v.active=true''', (company_id,))
                        for vehicle_id, vehicle_name, plate, created_at in source.fetchall():
                            target.execute('''INSERT INTO gps_assets (id,tenant_id,source_id,name,plate,type,created_at)
                                VALUES (%s,%s,%s,%s,%s,'vehicle',%s) ON CONFLICT(tenant_id,source_id) DO NOTHING''',
                                (str(uuid.uuid4()), tenant_id, 'odoo:fleet.vehicle:'+str(vehicle_id), vehicle_name, plate, created_at))
                    source.execute('''INSERT INTO ir_config_parameter (key,value,create_uid,write_uid,create_date,write_date)
                        VALUES ('step_tracker_portal.bridge_key',%s,1,1,now(),now())
                        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=now()''', (keys[database],))
                    print(json.dumps({'database': database, 'companies': len(companies)}))
    # This process runs as postgres; /etc is prepared with a restrictive file by deploy.
    key_path.write_text(json.dumps(keys))
    os.chmod(key_path, 0o600)
