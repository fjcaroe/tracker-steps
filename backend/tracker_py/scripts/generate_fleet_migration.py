"""Build explicit, reviewable PostgreSQL DDL from this release's GPS metadata."""
from pathlib import Path
from sqlalchemy.schema import CreateTable, CreateIndex, DropTable
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.ddl import sort_tables
from app.models.fleet import Base

tables = sort_tables([t for t in Base.metadata.tables.values() if t.name.startswith('gps_')])
dialect = postgresql.dialect()
up = ['BEGIN;']
for table in tables:
    up.append(str(CreateTable(table).compile(dialect=dialect))+';')
    up.extend(str(CreateIndex(index).compile(dialect=dialect))+';' for index in table.indexes)
up.extend([
    'CREATE EXTENSION IF NOT EXISTS btree_gist;',
    'ALTER TABLE gps_assets ADD CONSTRAINT gps_asset_tenant_pair UNIQUE (id, tenant_id);',
    'ALTER TABLE gps_assignments ADD CONSTRAINT gps_assignment_asset_tenant FOREIGN KEY (asset_id, tenant_id) REFERENCES gps_assets (id, tenant_id);',
    "ALTER TABLE gps_assignments ADD CONSTRAINT gps_assignment_dates CHECK (valid_to IS NULL OR valid_to > valid_from);",
    "ALTER TABLE gps_assignments ADD CONSTRAINT gps_device_no_overlap EXCLUDE USING gist (device_id WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&);",
    "CREATE UNIQUE INDEX gps_asset_current_device ON gps_assignments(asset_id) WHERE valid_to IS NULL;",
    'COMMIT;'])
target = Path('migrations')
(target/'20260930_fleet_protection.up.sql').write_text('\n'.join(up), encoding='utf-8')
(target/'20260930_fleet_protection.down.sql').write_text('BEGIN;\n'+'\n'.join(str(DropTable(t).compile(dialect=dialect))+';' for t in reversed(tables))+'\nCOMMIT;\n', encoding='utf-8')
