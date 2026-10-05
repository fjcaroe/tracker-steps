"""T49 surgical deployment: preserve environment-specific code and payroll XML.

Run as root on odoo-new. Default prints a plan; --apply backs up, stops the
specified services, patches only field declarations, migrates the two columns
transactionally, checks persisted decimals in Odoo with rollback, then starts.
No module-wide XML reload or historical/test database upgrade is performed.
"""
import argparse
import ast
import configparser
import datetime
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

GROUPS = {
    "development": [
        ("odoo18-dev", "/etc/dev_odoo18.conf", "LAB_TAREAS", "odoo", "/usr/bin/python3.10"),
        ("odoo18", "/etc/odoo18.conf", "karo_consultorias", "odoo", "/opt/odoo18/venv/bin/python"),
    ],
    "demo": [("odoo18-demo", "/etc/demo_odoo18.conf", "STEPS_DEMO", "demo_odoo18", "/usr/bin/python3.10")],
    "demo-sys": [("odoo18-demo-sys", "/etc/odoo18-demo-sys.conf", "STEPS_DEMO_SYS", "demosys_odoo18", "/usr/bin/python3.10")],
    "cerro": [("odoo18-cerroelplomo", "/etc/odoo18-cerroelplomo.conf", "CERRO_EL_PLOMO", "cerro_odoo18", "/usr/bin/python3.10")],
    "admin": [
        ("odoo18-admin", "/etc/odoo18-admin.conf", "steps_dev", "odoo", "/opt/odoo18/venv/bin/python"),
        ("odoo18-admin", "/etc/odoo18-admin.conf", "steps_qa", "odoo", "/opt/odoo18/venv/bin/python"),
    ],
}
FIELDS = {
    "step_hr/models/step_centro_costo.py": "has_cost",
    "step_hr/models/step_cuartel_line.py": "has_cuartel",
    "step_management_costs_agriculture/models/cost_center.py": "agri_hectares",
}


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sql(db, query):
    return subprocess.check_output(["sudo", "-u", "postgres", "psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-d", db], input=query, text=True).strip()


def patch_field(source, name):
    tree = ast.parse(source)
    matches = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)]
    if len(matches) != 1:
        raise ValueError(f"Expected one declaration of {name}, got {len(matches)}")
    node = matches[0]
    call = node.value
    assert isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    assert isinstance(call.func.value, ast.Name) and call.func.value.id == "fields"
    assert call.func.attr in ("Integer", "Float"), call.func.attr
    call.func.attr = "Float"
    call.keywords = [k for k in call.keywords if k.arg != "digits"]
    call.keywords.append(ast.keyword(arg="digits", value=ast.Tuple(elts=[ast.Constant(16), ast.Constant(2)], ctx=ast.Load())))
    lines = source.splitlines(keepends=True)
    prefix = lines[node.lineno - 1][:node.col_offset]
    lines[node.lineno - 1:node.end_lineno] = [prefix + ast.unparse(node) + "\n"]
    result = "".join(lines)
    ast.parse(result)
    return result


def migration(db):
    # Full row-by-row equality comparison, including NULL, before committing.
    return sql(db, """
BEGIN;
SET LOCAL lock_timeout = '30s';
CREATE TEMP TABLE t49_original_cc AS SELECT id, has_cost::numeric AS value FROM account_analytic_account;
CREATE TEMP TABLE t49_original_cuartel AS SELECT id, has_cuartel::numeric AS value FROM step_cuartel_line;
ALTER TABLE account_analytic_account ALTER COLUMN has_cost TYPE numeric USING has_cost::numeric;
ALTER TABLE step_cuartel_line ALTER COLUMN has_cuartel TYPE numeric USING has_cuartel::numeric;
DO $$ BEGIN
IF EXISTS (SELECT 1 FROM t49_original_cc o FULL JOIN account_analytic_account n USING(id) WHERE o.id IS NULL OR n.id IS NULL OR o.value IS DISTINCT FROM n.has_cost)
OR EXISTS (SELECT 1 FROM t49_original_cuartel o FULL JOIN step_cuartel_line n USING(id) WHERE o.id IS NULL OR n.id IS NULL OR o.value IS DISTINCT FROM n.has_cuartel)
THEN RAISE EXCEPTION 'T49 original values changed'; END IF;
END $$;
UPDATE ir_model_fields SET ttype='float' WHERE (model='account.analytic.account' AND name='has_cost') OR (model='step.cuartel.line' AND name='has_cuartel') OR (model='step.management.cost.center' AND name='agri_hectares');
SELECT 'T49_PRESERVED rows_cc=' || (SELECT count(*) FROM t49_original_cc) || ' rows_cuartel=' || (SELECT count(*) FROM t49_original_cuartel);
COMMIT;
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=GROUPS)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    entries = GROUPS[args.group]
    patches = {}
    for service, conf, db, user, python in entries:
        assert sql(db, "SELECT state FROM ir_module_module WHERE name='step_hr'") == "installed", db
        config = configparser.ConfigParser(interpolation=None)
        config.read(conf)
        roots = [Path(p.strip()) for p in config["options"]["addons_path"].split(",")]
        for relative, field in FIELDS.items():
            matches = [root / relative for root in roots if (root / relative).is_file()]
            if not matches:
                assert field == "agri_hectares", (db, relative)
                continue
            path = matches[0]  # Effective Odoo precedence; never overwrite whole addons.
            original = path.read_text()
            updated = patch_field(original, field)
            patches[path] = (original, updated)
    for path, (original, updated) in patches.items():
        print("".join(difflib.unified_diff(original.splitlines(True), updated.splitlines(True), fromfile=str(path), tofile=str(path))), flush=True)
    if not args.apply:
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = Path("/opt/steps_backups") / ("t49_" + args.group + "_" + stamp)
    backup.mkdir(mode=0o700, parents=True)
    services = list(dict.fromkeys(entry[0] for entry in entries))
    for path in patches:
        target = backup / "code" / path.relative_to("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    print("BACKUP " + str(backup), flush=True)
    run(["systemctl", "stop", *services])
    try:
        for _, _, db, _, _ in entries:
            with (backup / (db + ".dump")).open("wb") as stream:
                run(["sudo", "-u", "postgres", "pg_dump", "-Fc", db], stdout=stream)
        for path, (original, updated) in patches.items():
            assert path.read_text() == original, f"Concurrent change: {path}"
            path.write_text(updated)
        for service, conf, db, user, python in entries:
            print(db + " " + migration(db), flush=True)
            command = ["sudo", "-u", user, python, "/opt/odoo18/odoo-bin", "shell", "-c", conf, "-d", db,
                       "--no-http", "--max-cron-threads=0", "--logfile=/dev/stderr"]
            check = subprocess.run(command, input=Path(__file__).with_name("verify_odoo.py").read_text(), text=True, capture_output=True)
            (backup / (db + "-verify.log")).write_text(check.stdout + check.stderr)
            assert check.returncode == 0 and "T49_VERIFY_OK" in check.stdout, f"Verification failed: {backup}/{db}-verify.log"
            print(next(line for line in check.stdout.splitlines() if "T49_VERIFY_OK" in line), flush=True)
        manifest = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in patches}
        (backup / "deployed-sha256.json").write_text(json.dumps(manifest, indent=2))
    finally:
        run(["systemctl", "start", *services])
    for service in services:
        run(["systemctl", "is-active", "--quiet", service])
    print("T49_DEPLOY_OK " + args.group, flush=True)


if __name__ == "__main__":
    main()
