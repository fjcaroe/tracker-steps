"""Check the full frozen SyS schema, business data, 21 historical field identities and the local print extension."""
import argparse
import gzip
import json
from pathlib import Path

import psycopg2

from compare_sys_full_restore import snapshot
from guard_sys_original_catalogue import SQL, digest
from sys_cohort_required import DOCUMENT_FIELD_IDS, DOCUMENTS, inventory, read_original


DB = "COMMUNITY_SYS_FISCAL_PRINT_20261127U45P"
WORK = Path("/work/sys-print")
SOCKET = "/run/sys-55441"
PORT = 55441
MODULE = "step_report_print_colors"
# The original module registry already contains a row for each discovered module.
# Installing one module and compiling a changed stylesheet can advance only technical tables.
TECHNICAL = {"ir_module_module", "ir_module_module_dependency", "ir_model_data", "ir_attachment",
             "ir_cron_trigger", "ir_ui_view"}


def inspect(stage):
    frozen = json.loads(gzip.decompress((WORK / "source-snapshot.json.gz").read_bytes()))
    live = snapshot(DB, socket_dir=SOCKET, port=PORT)
    expected = {name: row[1] for name, row in json.loads((WORK/"effective-providers.json").read_bytes()).items()}
    with psycopg2.connect(dbname=DB, user="postgres", host=SOCKET, port=PORT) as conn, conn.cursor() as cr:
        cr.execute("SET TRANSACTION READ ONLY")
        cr.execute("SET LOCAL search_path=pg_catalog,public")
        cr.execute(SQL)
        catalogue = cr.fetchone()[0]
        protected = inventory(cr)
        for table, field in DOCUMENTS:
            key = table + "." + field
            identity = read_original(cr, table, field, DOCUMENTS)
            if DOCUMENT_FIELD_IDS[key] != identity:
                raise ValueError("Historical Documents field identity differs")
            protected[key] = identity
        cr.execute("SELECT name,latest_version FROM ir_module_module WHERE state='installed'")
        modules = dict(cr.fetchall())
    if stage in ("installed", "rendered"):
        expected[MODULE] = "18.0.1.0.0"
    if modules != expected or len(protected) != 21:
        raise ValueError("Unexpected module set or mandatory field inventory")
    if digest(catalogue) != json.loads((WORK/"final-schema.json").read_bytes())["observed_sha256"]:
        raise ValueError("Different original columns, constraints, relations, sequences, views, layouts or indexes")
    delta = {name: {key: [rows.get(key), live[name].get(key)] for key in rows.keys() | live[name].keys()
                      if rows.get(key) != live[name].get(key)} for name, rows in frozen.items()}
    if stage != "restored":
        registry_rows = json.loads((WORK / (stage + "-rows.json")).read_bytes())
        for table, row in registry_rows.items():
            if table == "ir_attachment" and stage == "rendered":
                expected_cache = ["web.report_assets_common.min.css", "web.report_assets_pdf.min.css"]
                if (row["added_caches"] != expected_cache or row["removed_caches"] != expected_cache
                        or row["changed"] or row["added"] != 2 or row["deleted"] != 2):
                    raise ValueError("Only the two generated report stylesheets may be replaced")
                continue
            allowed_updates = {"ir_module_module": {"write_date": 76}, "ir_ui_view": {"write_date": 1}}
            allowed_adds = {"ir_model_data": 1, "ir_module_module": 1, "ir_module_module_dependency": 1, "ir_cron_trigger": 1}
            if (row["deleted"] or row["added"] != allowed_adds.get(table, 0)
                    or row["columns"] != allowed_updates.get(table, {})
                    or table == "ir_ui_view" and row["first_changed_ids"] != [167]):
                raise ValueError("Unexpected field-level change to " + table)
    for name, changes in delta.items():
        if not changes:
            continue
        if stage == "restored":
            raise ValueError("The SQL restoration differs in " + name + ": " + str(list(changes)[:3]))
        if name == "public_tables" and changes.keys() <= TECHNICAL:
            continue
        if name == "sequence_values" and all(value[0] and value[1] and value[0][0] <= value[1][0] for value in changes.values()):
            continue
        raise ValueError("Original SQL differs in " + name + ": " + str(list(changes)[:15]))
    result = {"database": DB, "stage": stage, "modules": len(modules), "protected": protected,
              "schema_sha256": digest(catalogue), "source_tables": len(frozen["public_tables"]),
              "source_rows": sum(v[0] for v in frozen["public_tables"].values()),
              "changed_tables": delta["public_tables"], "advanced_sequences": delta["sequence_values"]}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("restored", "installed", "rendered"))
    inspect(parser.parse_args().stage)
