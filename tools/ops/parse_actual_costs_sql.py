"""Parse the report SELECT before restoring QA; no data or schema changes.

This only validates PostgreSQL syntax/types. It substitutes typed constants for
the new company configuration columns, which do not yet exist before upgrade.
Fresh-copy functional certification is still required for the exact package.
"""
import argparse
import ast
from pathlib import Path
import subprocess


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--database", default="LAB_TAREAS")
args = parser.parse_args()
assert args.database == "LAB_TAREAS" or args.database.startswith("MANAGEMENT_QA_DEVELOPMENT_")
module = ast.parse(args.source.read_text(encoding="utf-8"))
queries = [node.value for node in ast.walk(module) if isinstance(node, ast.Constant)
           and isinstance(node.value, str) and node.value.lstrip().startswith("CREATE VIEW %s AS")]
assert len(queries) == 1
select = queries[0].split("CREATE VIEW %s AS", 1)[1]
assert select.count("JOIN res_company co") == 1
select = select.replace("JOIN res_company co", """JOIN (SELECT id,
    NULL::integer management_actual_season_plan_id,
    NULL::integer management_actual_center_plan_id,
    NULL::integer management_actual_activity_plan_id FROM res_company) co""")
result = subprocess.run(["sudo", "-u", "postgres", "psql", "-d", args.database,
    "-v", "ON_ERROR_STOP=1", "-Atc", "EXPLAIN (FORMAT JSON) " + select], capture_output=True, text=True)
assert result.returncode == 0, result.stderr
print("ACTUAL_COSTS_SQL_PARSE_OK")
