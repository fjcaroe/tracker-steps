"""Compare the complete original SyS relation, sequence, column, constraint, view and index catalogues in FG."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import tempfile
import os

from restore_native_product_backup import query
from restore_sys_previred_pair import require
from sys_cohort_required import COLUMNS


SOURCE = "COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L"
TARGET = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FG"
ROOT = Path("/opt/steps-validation/community-sys-six-upgrades-20261127U44FG")
SEALED = Path("/opt/steps-validation/community-sys-payroll-document-20261127U43C/sealed")
REQUIRED = sorted([table + "." + col for table, col in COLUMNS] + ["documents_document.alias_id", "documents_document.document_token"])
SQL = """
WITH rel AS (SELECT oid,relname,relkind,reloptions,relowner,relacl FROM pg_class WHERE relnamespace='public'::regnamespace),
cols AS (SELECT c.relname||'.'||a.attname AS key,json_build_array(format_type(a.atttypid,a.atttypmod),a.attnotnull,
    a.attidentity,a.attgenerated,pg_get_expr(d.adbin,d.adrelid)) AS value FROM rel c JOIN pg_attribute a ON a.attrelid=c.oid
    LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum WHERE c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped),
cons AS (SELECT c.relname||'.'||k.conname AS key,json_build_array(pg_get_constraintdef(k.oid),k.convalidated) AS value
    FROM rel c JOIN pg_constraint k ON k.conrelid=c.oid),
views AS (SELECT relname AS key,json_build_array(relkind,pg_get_viewdef(oid,false),reloptions,pg_get_userbyid(relowner),relacl) AS value
    FROM rel WHERE relkind IN ('v','m')),
indexes AS (SELECT i.relname AS key,json_build_array(t.relname,pg_get_indexdef(x.indexrelid),x.indisvalid,x.indisready,
    x.indislive,x.indisunique,x.indisprimary,x.indisclustered,x.indisreplident,i.reloptions,
    pg_get_userbyid(i.relowner),i.relacl::text) AS value
    FROM pg_index x JOIN rel i ON i.oid=x.indexrelid JOIN rel t ON t.oid=x.indrelid),
owners AS (SELECT relname AS key,json_build_array(relkind,pg_get_userbyid(relowner),relacl::text) AS value
    FROM rel WHERE relkind IN ('r','p','S')),
sequences AS (SELECT sequencename AS key,json_build_array(data_type::text,start_value,min_value,max_value,
    increment_by,cycle,cache_size) AS value FROM pg_sequences WHERE schemaname='public'),
dependents AS (SELECT s.relname AS key,json_build_array(t.relname,a.attname,d.deptype) AS value FROM rel s
    JOIN pg_depend d ON d.classid='pg_class'::regclass AND d.objid=s.oid AND d.objsubid=0
    AND d.refclassid='pg_class'::regclass AND d.deptype IN ('a','i') JOIN rel t ON t.oid=d.refobjid
    JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid WHERE s.relkind='S'),
layouts AS (SELECT id::text AS key,json_build_array(inherit_id,active,
    encode(sha256(convert_to(arch_db::text,'UTF8')),'hex')) AS value FROM ir_ui_view WHERE id IN (204,1215,1281))
SELECT json_build_object('columns',(SELECT json_object_agg(key,value) FROM cols),'constraints',(SELECT json_object_agg(key,value) FROM cons),
    'views',coalesce((SELECT json_object_agg(key,value) FROM views),'{}'),'indexes',(SELECT json_object_agg(key,value) FROM indexes),
    'relation_owner_and_acl',(SELECT json_object_agg(key,value) FROM owners),
    'sequence_definitions',(SELECT json_object_agg(key,value) FROM sequences),
    'sequence_owned_by',(SELECT json_object_agg(key,value) FROM dependents),
    'invoice_layouts',(SELECT json_object_agg(key,value) FROM layouts))
"""


def catalogue(database):
    return json.loads(query(database, "SET search_path=pg_catalog,public; " + SQL))


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def checkpoint(database, module, position):
    require(database == TARGET and re.fullmatch("[a-z0-9_]{1,60}", module)
            and position in ("before", "after"), "fixed-sys-fg-catalogue-scope")
    folder = ROOT / "catalogue"
    folder.mkdir(mode=0o700, exist_ok=True)
    baseline = folder / "original-with-ownership.json.gz"
    if baseline.is_file():
        original = json.loads(gzip.decompress(baseline.read_bytes()))
    else:
        frozen = json.loads(gzip.decompress((SEALED / "source-snapshot.json.gz").read_bytes()))
        original = catalogue(SOURCE)
        require(all(original[k] == frozen[k] for k in ("columns", "constraints", "relation_owner_and_acl",
                "sequence_definitions")), "live-schema-differs-from-sealed-L")
        require(len(REQUIRED) == 21 and all(original["columns"][name][1] for name in REQUIRED),
                "source-FG-mandatory-fields-incomplete")
        with tempfile.NamedTemporaryFile(dir=folder, delete=False) as temporary:
            tmp = Path(temporary.name)
            try:
                temporary.write(gzip.compress(json.dumps(original, sort_keys=True).encode(), mtime=0))
                temporary.flush()
                os.link(tmp, baseline)
            finally:
                tmp.unlink(missing_ok=True)
    now = catalogue(database)
    sections = {}
    for kind, source in original.items():
        sections[kind] = {"original": len(source), "added": sorted(now[kind].keys() - source.keys()),
                          "missing": sorted(source.keys() - now[kind].keys()),
                          "changed": sorted(k for k in source.keys() & now[kind].keys() if now[kind][k] != source[k])}
    required = {name: bool(now["columns"].get(name, [False, False])[1]) for name in REQUIRED}
    result = {"source": SOURCE, "database": database, "module": module, "position": position, "sections": sections,
              "required": required, "reference_sha256": digest(original), "observed_sha256": digest(now)}
    name = module + "-" + position + "-" + digest(result)[:16] + ".json"
    output = folder / name
    if output.is_file():
        require(json.loads(output.read_bytes()) == result, "unexpected-catalogue-receipt")
    else:
        with output.open("x") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
    require(all(required.values()) and all(not v["changed"] and not v["missing"] for v in sections.values()),
            "changed-original-schema-ownership-or-invoice-layouts:" + name)
    return name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    parser.add_argument("module")
    parser.add_argument("position", choices=("before", "after"))
    args = parser.parse_args()
    print(checkpoint(args.database, args.module, args.position))
