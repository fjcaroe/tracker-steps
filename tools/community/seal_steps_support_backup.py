"""Freeze the final private H3 SQL database and retain only additional files beyond its accepted R checkpoint."""
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from admit_steps_support_portal import RECOVERY, WORK
from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require
from verify_converted_sql_schema import schema
from verify_steps_support_backup import (ACCEPTANCE, BASE_MANIFEST, FILES, PACKAGES, SOURCE,
                                         base_parts, canonical, file_archive, strong, verify)


def store_tree():
    rows = attachments(SOURCE, query)
    catalog = object_catalog(rows.pop("references"))
    tree = inventory(WORK / "data/filestore" / SOURCE, catalog)
    return rows, tree


def effective(base):
    args = json.loads((WORK / "private-args.json").read_bytes())
    roots = [WORK / "releases" / sha for sha, count in reversed(list(PACKAGES.values()))]
    runtime = WORK / "runtime"
    require("--addons-path=" + ",".join(map(str, [*roots, runtime / "addons", runtime / "odoo/addons"])) in args
            and str(runtime / "odoo-bin") in args and SOURCE in args, "unexpected-active-H3-roots")
    members = json.loads((base / "runtime-members.json").read_bytes())
    require({p.relative_to(runtime).as_posix() for p in runtime.rglob("*") if p.is_file()} == members.keys() and
            all(not (runtime / n).is_symlink() and (runtime / n).stat().st_size == size and
                (runtime / n).stat().st_mode & 0o777 == mode and digest(runtime / n) == sha
                for n, (size, sha, mode) in members.items()), "active-R-runtime-content-drift")
    for name, (sha, count) in PACKAGES.items():
        root = WORK / "releases" / sha
        with tarfile.open(WORK / (sha + ".tar")) as bundle:
            items = bundle.getmembers()
            require(len(items) == count and {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
                    == {m.name for m in items} and all(m.isfile() and (root / m.name).resolve() == root / m.name
                    and (root / m.name).read_bytes() == bundle.extractfile(m).read() for m in items),
                    "active-support-provider-drift")
    return check_modules(SOURCE)


def seal():
    dest = WORK / "final-checkpoint"
    if dest.is_dir():
        sha = digest(dest / "checkpoint.json")
        return verify(RECOVERY, dest, sha)
    require(WORK.resolve(strict=True) == WORK and digest(WORK / "functional-acceptance.json") == ACCEPTANCE,
            "qualified-isolated-source-required")
    require(shutil.disk_usage(WORK).free > 5 * GIB + int(query("postgres", f"SELECT pg_database_size('{SOURCE}')"))
            and shutil.disk_usage(query("postgres", "SHOW data_directory")).free > 5 * GIB, "reserve-for-H3-checkpoint")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{SOURCE}'") == "0",
            "H3-in-use")
    base = base_parts(RECOVERY)
    providers = effective(base)
    frozen = full_snapshot(SOURCE)
    definitions = objects(SOURCE)
    rows, tree = store_tree()
    old = file_archive(base / "filestore.tar")
    old.update(file_archive(base / "filestore-extra.tar"))
    require(strong(old) == json.loads((base / "filestore-physical.json").read_bytes())["tree_sha256"],
            "R-physical-archive-drift")
    changed = sorted(k for k, v in tree.items() if old.get(k) != v)
    with tempfile.TemporaryDirectory(dir=WORK) as temp:
        stage = Path(temp) / "checkpoint"
        stage.mkdir()
        archive = stage / "source.dump"
        with archive.open("xb") as out:
            pg("pg_dump", "-Fc", "--no-tablespaces", SOURCE, readonly=True, stdout=out)
        rendered = subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "--file=-", str(archive)])
        sql_schema = schema(rendered)
        direct = pg("pg_dump", "--schema-only", "--no-tablespaces", SOURCE, readonly=True, stdout=subprocess.PIPE).stdout
        require(schema(direct) == sql_schema, "H3-archive-schema-drift")
        for filename, contents in (("snapshot.json.gz", frozen), ("sql-objects.json.gz", definitions),
                                   ("filestore.json.gz", tree)):
            (stage / filename).write_bytes(gzip.compress(canonical(contents), mtime=0))
        with tarfile.open(stage / "filestore-delta.tar", "x") as bundle:
            for key in changed:
                bundle.add(WORK / "data/filestore" / SOURCE / key, arcname=key, recursive=False)
        for name, (sha, count) in PACKAGES.items():
            shutil.copyfile(WORK / (sha + ".tar"), stage / (name + ".tar"))
        shutil.copyfile(WORK / "functional-acceptance.json", stage / "acceptance.json")
        save(stage / "providers.json", providers)
        verify_same(frozen, full_snapshot(SOURCE))
        require(definitions == objects(SOURCE) and (rows, tree) == store_tree() and providers == check_modules(SOURCE),
                "H3-changed-during-backup")
        proof = {"source": SOURCE, "base_manifest": BASE_MANIFEST, "acceptance": ACCEPTANCE,
                 "tables": len(frozen["public_tables"]), "rows": sum(v[0] for v in frozen["public_tables"].values()),
                 "schema_sha256": sql_schema, "schema_objects": len(definitions), "sequences": len(frozen["sequence_values"]),
                 "changed_files": changed, "removed_files": sorted(old.keys() - tree.keys()),
                 "tree_sha256": strong(tree), "attachment_rows": rows,
                 "files": {n: [p.stat().st_size, digest(p)] for n in FILES for p in [stage / n]}}
        save(stage / "checkpoint.json", proof)
        final = verify(RECOVERY, stage, digest(stage / "checkpoint.json"))
        stage.rename(dest)
    return final


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(seal(), indent=2))
