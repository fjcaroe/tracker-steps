"""Read-only inventory; run as root on the Odoo host. Never print credentials."""
import configparser
import json
import pathlib
import subprocess

CONFIGS = {
    "odoo18-dev": ("/etc/dev_odoo18.conf", "LAB_TAREAS"),
    "odoo18-demo": ("/etc/demo_odoo18.conf", "STEPS_DEMO"),
    "odoo18-demo-sys": ("/etc/odoo18-demo-sys.conf", "STEPS_DEMO_SYS"),
    "odoo18-cerroelplomo": ("/etc/odoo18-cerroelplomo.conf", "CERRO_EL_PLOMO"),
    "odoo18-sys": ("/etc/odoo18-sys.conf", "SyS"),
    "odoo18-everfruit": ("/etc/odoo18-everfruit.conf", "Everfruit"),
    "odoo18": ("/etc/odoo18.conf", "karo_consultorias"),
    "odoo18-admin": ("/etc/odoo18-admin.conf", None),
}


def sql(db, query):
    return subprocess.check_output(
        ["sudo", "-u", "postgres", "psql", "-X", "-A", "-t", "-d", db, "-c", query], text=True
    ).strip()


def main():
    databases = sql("postgres", "SELECT datname FROM pg_database WHERE NOT datistemplate AND datallowconn ORDER BY datname").splitlines()
    print("DATABASES", json.dumps(databases))
    for service, (conf, database) in CONFIGS.items():
        config = configparser.ConfigParser(interpolation=None)
        config.read(conf)
        options = config["options"]
        paths = [pathlib.Path(p.strip()) for p in options["addons_path"].split(",")]
        modules = {}
        for module in ("step_hr", "step_management_costs_agriculture"):
            matches = [str(p / module) for p in paths if (p / module / "__manifest__.py").exists()]
            modules[module] = matches
        result = dict(service=service, config=conf, database=database, modules=modules)
        result["dbfilter"] = options.get("dbfilter", "")
        result["db_name"] = options.get("db_name", "")
        if database:
            result["installed"] = sql(database, "SELECT name || ':' || state FROM ir_module_module WHERE name IN ('step_hr','step_management_costs_agriculture') ORDER BY name")
            result["columns"] = sql(database, "SELECT table_name || '.' || column_name || ':' || data_type FROM information_schema.columns WHERE (table_name='account_analytic_account' AND column_name='has_cost') OR (table_name='step_cuartel_line' AND column_name='has_cuartel') ORDER BY 1")
        print(json.dumps(result))
        if service == "odoo18-admin":
            for db in databases:
                if sql(db, "SELECT to_regclass('public.ir_module_module')"):
                    state = sql(db, "SELECT state FROM ir_module_module WHERE name='step_hr'")
                    print(json.dumps(dict(admin_candidate=db, step_hr=state)))


if __name__ == "__main__":
    main()
