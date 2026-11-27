"""Freeze the qualified 165-module Steps installation after its fiscal and portal acceptance."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from admit_steps_support_portal import RECOVERY, WORK as SUPPORT
from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_support_backup import OUTPUT as WORK
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import resolve_providers
from verify_converted_sql_schema import schema
from verify_steps_integrated_backup import FISCAL, FISCAL_SHA, H3_SHA, INVOICES, OFFICIAL, PIECES, PORTAL, PORTAL_SHA, verify
from verify_steps_support_backup import PACKAGES, SUCCESSOR, canonical, compressed, strong, verify as verify_support


PARENT = SUPPORT / "final-checkpoint"
BASE = RECOVERY / "sealed"
EVIDENCE = WORK / "functional-evidence"
FISCAL_TAR = WORK.parent / "steps-sales-fiscal-20261127U45F" / ("status-" + FISCAL_SHA + ".tar")


def physical():
    results = attachments(SUCCESSOR, query)
    return inventory(WORK / "data/filestore" / SUCCESSOR, object_catalog(results.pop("references"))), results


def effective(active, stage):
    stable = WORK / ("support-portal-" + PORTAL_SHA[:12])
    roots = [stable / "addons", WORK / "fiscal-addons", WORK / "addons", WORK / "runtime/addons", WORK / "runtime/odoo/addons"]
    command = json.loads((WORK / "private-args.json").read_bytes())
    require("--addons-path=" + ",".join(map(str, roots)) in command and str(WORK / "runtime/odoo-bin") in command
            and command[command.index("-d") + 1] == SUCCESSOR, "wrong-integrated-runtime")
    actual = resolve_providers(WORK / "runtime", roots, WORK / "data", active)
    for name, values in active.items():
        if name == PORTAL:
            root = roots[0]
        elif name in OFFICIAL or name == FISCAL:
            root = roots[1]
        elif name in PACKAGES:
            root = roots[2]
        else:
            root = roots[4] if name == "base" else roots[3]
        require(actual[name] == [str(root / name), *values], "unqualified-provider-path-or-version:" + name)
    runtime = json.loads((BASE / "runtime-members.json").read_bytes())
    code = WORK / "runtime"
    require({p.relative_to(code).as_posix() for p in code.rglob("*") if p.is_file()} == runtime.keys() and
            all((code / n).resolve() == code / n and digest(code / n) == v[1] and
                (code / n).stat().st_mode & 0o777 == v[2] for n, v in runtime.items()), "changed-R-runtime")
    for name, path, root in [(n, PARENT / (n + ".tar"), roots[2]) for n in PACKAGES if n != PORTAL] + [
            (FISCAL, FISCAL_TAR, roots[1]), (PORTAL, stable / "portal.tar", roots[0])]:
        expected = PORTAL_SHA if name == PORTAL else PACKAGES[name][0] if name in PACKAGES else FISCAL_SHA
        require(digest(path) == expected, "unqualified-module-archive")
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            require({p.relative_to(root).as_posix() for p in (root / name).rglob("*") if p.is_file()}
                    == {m.name for m in members} and all(m.isfile() and (root / m.name).resolve() == root / m.name
                    and (root / m.name).read_bytes() == archive.extractfile(m).read() for m in members),
                    "private-active-module-differs")
    shutil.copyfile(FISCAL_TAR, stage / "fiscal-release.tar")
    shutil.copyfile(stable / "portal.tar", stage / "portal-release.tar")
    with tarfile.open(stage / "official-fiscal.tar", "x", format=tarfile.USTAR_FORMAT) as archive:
        for name, (version, count, checksum) in OFFICIAL.items():
            root = roots[1] / name
            files = {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}
            require(len(files) == count and strong(files) == checksum, "official-module-tree-changed")
            for relative in sorted(files):
                path = root / relative
                require(path.resolve() == path, "unexpected-official-source-link")
                member = tarfile.TarInfo(name + "/" + relative)
                member.size, member.mode = path.stat().st_size, 0o644
                with path.open("rb") as data:
                    archive.addfile(member, data)


def seal(evidence_sha):
    require(WORK.resolve(strict=True) == WORK and EVIDENCE.resolve(strict=True) == EVIDENCE and
            digest(EVIDENCE / "manifest.json") == evidence_sha, "unknown-functional-evidence")
    evidence = json.loads((EVIDENCE / "manifest.json").read_bytes())
    require(isinstance(evidence, dict) and all(Path(n).name == n and n.endswith(".json") and
            (EVIDENCE / n).resolve(strict=True) == EVIDENCE / n and digest(EVIDENCE / n) == sha
            for n, sha in evidence.items()), "unrecognized-evidence-file")
    require({"support-original.json", "support-integrated.json", "fiscal-repeat.json", "fiscal-install.json",
             INVOICES, "workflow-acceptance.json"} <= evidence.keys(), "missing-accepted-workflows")
    support = json.loads((EVIDENCE / "support-integrated.json").read_bytes())
    require(support["db"] == SUCCESSOR and support["modules"] == 165 and
            support["reference_sha256"] == evidence["support-original.json"], "wrong-ticket-portal-evidence")
    for key, original in (("fiscal-install.json", "fiscal-integration.json"), ("fiscal-repeat.json", "fiscal-repeat.json")):
        require(digest(WORK / original) == evidence[key] and
                json.loads((WORK / original).read_bytes())["package"] == FISCAL_SHA, "another-fiscal-package-was-tested")
    final = WORK / "final-checkpoint"
    if final.is_dir():
        require(json.loads((final / "checkpoint.json").read_bytes())["functional_evidence"] == evidence,
                "different-frozen-workflow-receipts")
        return verify(RECOVERY, PARENT, final, digest(final / "checkpoint.json"))
    require(shutil.disk_usage(WORK).free > 5 * GIB + int(query("postgres", f"SELECT pg_database_size('{SUCCESSOR}')"))
            and shutil.disk_usage(query("postgres", "SHOW data_directory")).free > 5 * GIB, "private-storage-reserve")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{SUCCESSOR}'") == "0",
            "integration-copy-in-use")
    verify_support(RECOVERY, PARENT, H3_SHA)
    active = check_modules(SUCCESSOR)
    before = full_snapshot(SUCCESSOR)
    definitions = objects(SUCCESSOR)
    tree, rows = physical()
    old = compressed(PARENT, "filestore.json.gz")
    changed = sorted(k for k, value in tree.items() if old.get(k) != value)
    roles = json.loads(query(SUCCESSOR, """SELECT json_agg(name ORDER BY name) FROM (
        SELECT DISTINCT pg_get_userbyid(refobjid) AS name FROM pg_shdepend
        WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND refclassid='pg_authid'::regclass
        UNION SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) AS roles"""))
    with tempfile.TemporaryDirectory(dir=WORK) as tmp:
        stage = Path(tmp) / "checkpoint"
        stage.mkdir()
        effective(active, stage)
        with (stage / "source.dump").open("xb") as output:
            pg("pg_dump", "-Fc", "--no-tablespaces", SUCCESSOR, readonly=True, stdout=output)
        archived = subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "--file=-", str(stage / "source.dump")])
        source_schema = schema(pg("pg_dump", "--schema-only", "--no-tablespaces", SUCCESSOR, readonly=True,
                                  stdout=subprocess.PIPE).stdout)
        require(schema(archived) == source_schema, "recorded-schema-differs-from-source")
        for name, value in (("snapshot.json.gz", before), ("sql-objects.json.gz", definitions), ("filestore.json.gz", tree)):
            (stage / name).write_bytes(gzip.compress(canonical(value), mtime=0))
        save(stage / "providers.json", active)
        with tarfile.open(stage / "filestore-delta.tar", "x") as archive:
            for key in changed:
                archive.add(WORK / "data/filestore" / SUCCESSOR / key, arcname=key, recursive=False)
        with tarfile.open(stage / "functional-evidence.tar", "x") as archive:
            for key in sorted(evidence):
                archive.add(EVIDENCE / key, arcname=key, recursive=False)
        verify_same(before, full_snapshot(SUCCESSOR))
        require(check_modules(SUCCESSOR) == active and objects(SUCCESSOR) == definitions and physical() == (tree, rows),
                "integrated-state-changed-during-capture")
        proof = {"source": SUCCESSOR, "parent": H3_SHA, "fiscal_package_sha256": FISCAL_SHA, "required_roles": roles,
                 "tables": len(before["public_tables"]), "sequences": len(before["sequence_values"]),
                 "rows": sum(row[0] for row in before["public_tables"].values()), "schema_sha256": source_schema,
                 "schema_objects": len(definitions), "functional_evidence": evidence, "attachment_rows": rows,
                 "tree_sha256": strong(tree), "changed_files": changed, "removed_files": sorted(old.keys() - tree.keys()),
                 "files": {n: [(stage / n).stat().st_size, digest(stage / n)] for n in PIECES}}
        save(stage / "checkpoint.json", proof)
        result = verify(RECOVERY, PARENT, stage, digest(stage / "checkpoint.json"))
        stage.rename(final)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        print(json.dumps(seal(args.evidence_sha256), indent=2))
