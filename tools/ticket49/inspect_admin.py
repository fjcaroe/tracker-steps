"""Read-only investigation of legacy Admin databases and actual connections."""
import json
from inventory import sql

for db in ("steps_dev", "steps_qa", "karo_consultorias"):
    print(json.dumps({"database": db,
        "module": sql(db, "SELECT name || ':' || state || ':' || COALESCE(latest_version,'') FROM ir_module_module WHERE name='step_hr'"),
        "fields": sql(db, "SELECT model || '.' || name || ':' || ttype FROM ir_model_fields WHERE name IN ('has_cost','has_cuartel')"),
        "columns": sql(db, "SELECT table_name || '.' || column_name || ':' || data_type FROM information_schema.columns WHERE column_name IN ('has_cost','has_cuartel')"),
        "url": sql(db, "SELECT value FROM ir_config_parameter WHERE key='web.base.url'"),
    }))
print("CONNECTIONS", sql("postgres", "SELECT datname || ':' || usename || ':' || count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND datname IS NOT NULL GROUP BY datname, usename ORDER BY 1"))
