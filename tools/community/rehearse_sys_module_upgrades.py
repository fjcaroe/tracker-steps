"""Restore a sealed SyS Community cohort and exercise official upgrades on an isolated copy."""
import argparse
import ast
import fcntl
import gzip
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile
import tempfile

from audit_sys_upgrade_policy import audit
from build_sys_upgrade_policy_profile import build, fingerprint, seal_profile
from compare_sys_payroll_exports_all import changes, index
from custody_sys_previred_filestore import attachments, digest, object_catalog, restore_objects
from package_sys_original_policy_providers import COMMIT, TREES
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require


MODULES = {
    "l10n_cl_simpledigital_payroll": ("18.0.1.0.0", "18.0.1.1.0"),
    "step_hr_previred": ("18.0.3.8.7", "18.0.3.8.8"),
    "step_hr_previred_simpledigital": ("18.0.2.4.1", "18.0.2.4.2"),
    "hr_timesheet": ("18.0.1.0", "18.0.1.1"),
    "project_sms": ("18.0.1.0", "18.0.1.1"),
    "l10n_latam_invoice_document": ("18.0.1.0", "18.0.1.1"),
}
PINNED_ARCHIVE = "e1ab99abe55ac7693afe6c48f3ee51aa4ac27208b483472a6e8ae20f0be6233b"
FORWARD = tuple(module for module in MODULES if module not in TREES)
PRIVATE = Path("/opt/steps-validation")
SPACE = "steps_community_storage_20261028_community"


def save(file, value):
    with file.open("x", encoding="utf8") as output:
        json.dump(value, output, sort_keys=True, indent=2)


def snapshot(db):
    code = ("import json,sys\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from compare_sys_full_restore import snapshot\nprint(json.dumps(snapshot(" + repr(db) + ")))")
    return json.loads(subprocess.check_output(["sudo", "-n", "-u", "postgres", "python3", "-B", "-"], input=code.encode()))


def differences(before, after):
    return {section: sorted(k for k in before[section].keys() | after[section].keys()
                            if before[section].get(k) != after[section].get(k)) for section in before}


def module_versions(db):
    return json.loads(query(db, "SELECT json_object_agg(name,json_build_array(state,latest_version)) "
                                "FROM ir_module_module WHERE state<>'uninstalled'"))


def guards(db):
    return json.loads(query(db, """SELECT json_object_agg(c.relname||'.'||t.tgname,
        json_build_array(t.tgenabled, md5(pg_get_triggerdef(t.oid)), md5(pg_get_functiondef(t.tgfoid))))
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        WHERE NOT t.tgisinternal AND c.relnamespace='public'::regnamespace"""))


def check_space(size):
    data = Path(query("postgres", "SHOW data_directory"))
    target = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    require(target.resolve().is_relative_to(PRIVATE / "community-payroll-storage-20261028"), "wrong-tablespace-root")
    free = {"postgres": shutil.disk_usage(data).free, "private": shutil.disk_usage(target).free}
    require(free["postgres"] >= 5 * GIB and free["private"] >= 5 * GIB + 3 * size, "reserve-required")
    return free


def restore(args, proof):
    out, sealed, db = args.output, args.sealed, args.database
    require(not out.exists(), "private-output-exists")
    require(query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{db}'") == "0", "target-exists")
    source = proof["source"]
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9]+", source), "unexpected-source")
    owner, enc, coll, ctype, size = json.loads(query("postgres", f"""
         SELECT json_build_array(pg_get_userbyid(datdba),pg_encoding_to_char(encoding),datcollate,datctype,
                                 pg_database_size(datname)) FROM pg_database WHERE datname='{source}'"""))
    require(owner == "odoo", "original-owner")
    free = check_space(size)
    service = pwd.getpwnam(owner)
    for name, expected in {
        "source.dump": proof["sql_sha256"], "filestore.tar": proof["archive_sha256"],
        "runtime.tar.gz": proof["runtime"]["archive_sha256"], "runtime-members.json": proof["runtime"]["manifest_sha256"],
        "original-release.tar": proof["release_sha256"],
    }.items():
        require(digest(sealed / name) == expected, "sealed-checksum-" + name)
    runtime = sealed / "runtime"
    members = json.loads((sealed / "runtime-members.json").read_bytes())
    require(all(not Path(n).is_absolute() and ".." not in Path(n).parts and (runtime / n).is_file()
                and (runtime / n).stat().st_size == info[0] and digest(runtime / n) == info[1]
                for n, info in members.items()), "sealed-runtime-mismatch")
    require({p.relative_to(runtime).as_posix() for p in runtime.rglob("*") if p.is_file()} == set(members),
            "sealed-runtime-extra-files")
    out.mkdir(mode=0o750)
    os.chown(out, 0, service.pw_gid)
    out.chmod(0o750)
    pg("createdb", "--template=template0", "--owner=" + owner, "--tablespace=" + SPACE, "--encoding=" + enc,
       "--lc-collate=" + coll, "--lc-ctype=" + ctype, db)
    with (sealed / "source.dump").open("rb") as source_data, (out / "pg-restore.log").open("xb") as log:
        pg("pg_restore", "--exit-on-error", "--single-transaction", "--no-tablespaces", "--dbname=" + db,
           stdin=source_data, stdout=log, stderr=log)
    require(query("postgres", f"SELECT s.spcname FROM pg_database d JOIN pg_tablespace s ON d.dattablespace=s.oid "
                              f"WHERE d.datname='{db}'") == SPACE, "database-tablespace-mismatch")
    frozen = json.loads(gzip.decompress((sealed / "source-snapshot.json.gz").read_bytes()))
    require(not any(differences(frozen, snapshot(db)).values()), "original-sql-drift")
    catalog = object_catalog(attachments(db, query)["references"])
    data = out / "data"
    store = data / "filestore" / db
    store.mkdir(parents=True)
    restore_objects(sealed / "filestore.tar", store, catalog)
    require({p.relative_to(store).as_posix() for p in store.glob("*/*") if p.is_file()} == set(catalog)
            and all((store / n).stat().st_size == num and digest(store / n, "sha1") == Path(n).name
                    for n, num in catalog.items()), "original-filestore-drift")
    for path in (data, *data.rglob("*")):
        require(not path.is_symlink(), "private-filestore-symlink")
        os.chown(path, service.pw_uid, service.pw_gid)
    original_guards = guards(source)
    require(len(original_guards) >= 40 and guards(db) == original_guards, "original-trigger-drift")
    versions = module_versions(db)
    require(all(versions[name] == ["installed", old] for name, (old, new) in MODULES.items()), "original-version-drift")
    (out / "runtime").mkdir(mode=0o755)
    save(out / "restored.json", {"database": db, "sealed": str(sealed), "dump": proof["sql_sha256"],
                                 "runtime": proof["runtime"]["archive_sha256"], "free": free,
                                 "rows": proof["rows"], "objects": len(catalog), "tablespace": SPACE, "guards": original_guards})


def pin_original_providers(args):
    out = args.output
    require(args.database.endswith(("U41MQ", "U41MV", "U41MW")) and not (out / "pinned").exists(), "fresh-original-policy-copy-required")
    archive = Path(__file__).with_name("original-public-addons.tar")
    require(digest(archive) == PINNED_ARCHIVE, "unexpected-original-public-package")
    versions = module_versions(args.database)
    require(all(versions[m] == ["installed", "18.0.1.0"] for m in TREES), "unexpected-original-policy-version")
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        pinned = Path(tmp) / "pinned"
        pinned.mkdir()
        with tarfile.open(archive, "r|") as incoming:
            for entry in incoming:
                rel = Path(entry.name)
                require(not rel.is_absolute() and ".." not in rel.parts and rel.parts[0] in TREES
                        and entry.isfile() and entry.mode in (0o644, 0o755), "invalid-original-module-member")
                target = pinned / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with incoming.extractfile(entry) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(entry.mode)
        for module in TREES:
            manifest = ast.literal_eval((pinned / module / "__manifest__.py").read_text())
            require(manifest["version"] == "1.0" and manifest["license"] == "LGPL-3", "wrong-original-manifest")
        for directory in (pinned, *(p for p in pinned.rglob("*") if p.is_dir())):
            directory.chmod(0o755)
        files, sha = fingerprint(pinned)
        require(files == 200, "unexpected-number-of-original-policy-files")
        pinned.rename(out / "pinned")
    save(out / "pinned-providers.json", {"commit": COMMIT, "trees": TREES, "files": files, "sha256": sha,
                                       "archive": PINNED_ARCHIVE})


def effective_profile(out):
    return ((out / "tested-profile", out / "tested-profile-proof.json") if (out / "tested-profile-proof.json").is_file()
            else (out / "profile", out / "profile-proof.json"))


def verify_retained_profile(args):
    require(args.database.endswith(("U41MQ", "U41MV", "U41MW")), "original-sys-layout-copy-required")
    out = args.output
    directory, receipt = effective_profile(out)
    expected = json.loads(receipt.read_bytes())
    latam = expected["modules"]["l10n_latam_invoice_document"]["files"]
    if args.database.endswith(("U41MV", "U41MW")):
        require("l10n_cl" in expected["modules"] and "step_account_monthly_books" in expected["modules"]
                and "views/report_templates.xml" in latam, "complete-fiscal-preservation-profile-required")
    if "views/report_templates.xml" not in latam:
        args_root = (*FORWARD, "step_payroll_engine_transition")
        save(out / "tested-profile-proof.json", build(args.database, args.sealed, out / "tested-profile",
                                                    args_root, original_admin_seeds=True))


def guarded_plan(args):
    template = PRIVATE / "community-sys-cohort-20261126U40J/receipts/cohort-plan.json"
    require(digest(template) == "4b42c4c1789196f72b32f96a6f14e39bb18a822b8958907057337fbe34ec8573",
            "original-protection-plan-drift")
    plan = json.loads(template.read_bytes())
    require(plan["database"] == "COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J"
            and len(plan["mandatory_columns"]) == 18 and len(plan["retained_supplier_aliases"]) == 2,
            "unexpected-original-protections")
    plan["database"] = args.database
    output = args.output / "cohort-guards.json"
    if output.exists():
        require(json.loads(output.read_bytes()) == plan, "candidate-guard-plan-drift")
    else:
        save(output, plan)
        os.chown(output, 0, pwd.getpwnam("odoo").pw_gid)
        output.chmod(0o440)
    return output


def odoo(args, mode, options, log, stdin=None, comparison_key=None, loopback=False):
    out, db = args.output, args.database
    core = out / "runtime"
    temporary = out / "data" / "tmp"
    temporary.mkdir(mode=0o700, exist_ok=True)
    service = pwd.getpwnam("odoo")
    require(temporary.resolve() == temporary, "unexpected-temporary-directory")
    os.chown(temporary, service.pw_uid, service.pw_gid)
    argv = ["unshare", "--net", "--", "bwrap", "--die-with-parent", "--ro-bind", "/", "/",
            "--tmpfs", str(PRIVATE), "--tmpfs", "/srv/odoo-data/steps-anchor-validation", "--tmpfs", "/opt/odoo18",
            "--ro-bind", str(out), str(out), "--ro-bind", str(args.sealed / "runtime"), str(core),
            "--bind", str(out / "data"), str(out / "data"), "--proc", "/proc", "--dev-bind", "/dev", "/dev", "--",
            "sudo", "-n", "-u", "odoo", "env", "PYTHONDONTWRITEBYTECODE=1", "TMPDIR=" + str(temporary),
            "/usr/bin/python3.10", str(core / "odoo-bin")]
    if comparison_key is not None:
        require(comparison_key.is_file() and comparison_key.stat().st_size == 32, "private-comparison-key-required")
        placeholder = out / "export-proof-key"
        placeholder.touch(mode=0o440, exist_ok=True)
        position = argv.index("--proc")
        argv[position:position] = ["--ro-bind", str(comparison_key), str(placeholder)]
    if mode:
        argv.append(mode)
    addons = [core / "addons", core / "odoo/addons"]
    if (out / "profile").exists():
        directory, receipt = effective_profile(out)
        expected = json.loads(receipt.read_bytes())
        require(args.database.endswith(("U41MP", "U41MQ", "U41MV", "U41MW")) and fingerprint(directory) == (expected["files"], expected["sha256"]),
                "profile-checksum-drift")
        addons.insert(0, directory)
    if (out / "pinned").exists():
        pins = json.loads((out / "pinned-providers.json").read_bytes())
        require(args.database.endswith(("U41MQ", "U41MV", "U41MW")) and pins["archive"] == PINNED_ARCHIVE
                and fingerprint(out / "pinned") == (pins["files"], pins["sha256"]), "original-pinned-modules-drift")
        addons.insert(0, out / "pinned")
    # The standalone CLI can register runtime/addons before reading its configuration.
    # Expose the same verified sources at that location for both registry entry points.
    mounts = []
    modules = set()
    for private in addons[:-2]:
        for source in sorted(private.iterdir()):
            require(source.is_dir() and (source / "__manifest__.py").is_file() and source.name not in modules,
                    "ambiguous-original-provider")
            require((args.sealed / "runtime/addons" / source.name / "__manifest__.py").is_file(),
                    "missing-sealed-provider-target")
            mounts.extend(["--ro-bind", str(source), str(core / "addons" / source.name)])
            modules.add(source.name)
    position = argv.index("--proc")
    argv[position:position] = mounts
    if not mode and (out / "profile").is_dir():
        require(options == ["-u", args.module], "unexpected-candidate-operation")
        tooling = out / "validator"
        tooling.mkdir(mode=0o755, exist_ok=True)
        mount_at = argv.index("--proc")
        argv[mount_at:mount_at] = ["--ro-bind", str(Path(__file__).resolve().parent), str(tooling)]
        argv[-1] = str(tooling / "load_sys_payroll_cohort.py")
        argv.extend(["--database", db, "--runtime", str(core), "--plan", str(guarded_plan(args)),
                     "--config", "/etc/odoo18-sys.conf", "--data-dir", str(out / "data"),
                     "--addons-path", ",".join(map(str, addons)), "--upgrade-module", args.module,
                     "--logfile", str(out / "data" / (log.stem + "-odoo.log"))])
        with log.open("xb") as handle:
            return subprocess.run(argv, stdout=handle, stderr=handle).returncode
    argv.extend(["-c", "/etc/odoo18-sys.conf", "-d", db, "--db-filter=^" + db + "$", "--db_host=/var/run/postgresql",
                 "--data-dir=" + str(out / "data"), "--addons-path=" + ",".join(map(str, addons)),
                 "--no-http", "--workers=0", "--max-cron-threads=0", "--stop-after-init", "--without-demo=all", "--load=base,web",
                 "--logfile=" + str(out / "data" / (log.stem + "-odoo.log")), *options])
    if loopback:
        require(mode == "shell" and db.endswith("U41MW"), "private-fiscal-report-shell-required")
        tooling = out / "validator"
        require(tooling.is_dir(), "protected-installer-mount-required")
        position = argv.index("--proc")
        argv[position:position] = ["--ro-bind", str(Path(__file__).resolve().parent), str(tooling)]
        position = argv.index("sudo")
        require(argv[position:position + 4] == ["sudo", "-n", "-u", "odoo"], "unexpected-odoo-report-user")
        argv[position:position + 4] = ["/usr/bin/python3.10", str(tooling / "original_report_loopback.py"), "sudo", "-u", "odoo"]
        argv[3:3] = ["bash", "-c", 'set -e; ip link set lo up; exec "$@"', "bash"]
    with log.open("xb") as handle:
        return subprocess.run(argv, input=stdin, stdout=handle, stderr=handle).returncode


def original_aliases(db, max_id):
    return json.loads(query(db, f"""SELECT json_build_array(count(*), md5(string_agg(md5(
        json_build_array(id,module,name,model,res_id,noupdate)::text),'' ORDER BY id)))
        FROM ir_model_data WHERE id<={int(max_id)}"""))


def journal_domain(db):
    return json.loads(query(db, """SELECT json_build_object('purchase', count(*),
        'latam', count(*) FILTER (WHERE l10n_latam_use_documents),
        'migration_domain', count(*) FILTER (WHERE l10n_latam_use_documents AND restrict_mode_hash_table))
        FROM account_journal WHERE type='purchase'"""))


def forms(args):
    out = args.output
    require(json.loads((out / "restored.json").read_bytes())["database"] == args.database, "wrong-target")
    code = Path(__file__).with_name("probe_sys_module_upgrade_forms.py").read_text()
    code += "\nimport json\nassert env.cr.dbname == " + repr(args.database)
    code += "\nprint('SIX_FORMS='+json.dumps(run(env)),flush=True)\n"
    log = out / (args.label + ".log")
    if log.exists():
        require(not (out / (args.label + ".json")).exists(), "form-already-certified")
        log = out / (args.label + "-retry-" + str(len(list(out.glob(args.label + "*.log")))) + ".log")
    result = odoo(args, "shell", [], log, code.encode())
    lines = [line.split("=", 1)[1] for line in log.read_text().splitlines() if line.startswith("SIX_FORMS=")]
    require(result == 0 and len(lines) == 1, "original-role-form-probe-failed")
    save(out / (args.label + ".json"), json.loads(lines[0]))


def retained_release(args):
    require(args.database.endswith(("U41MQ", "U41MV", "U41MW")), "retained-sys-policy-scope-required")
    states = module_versions(args.database)
    require(all(states[m] == ["installed", MODULES[m][1]] for m in FORWARD), "forward-providers-not-yet-installed")
    probe = Path(__file__).with_name("probe_sys_retained_provider_release.py").read_text()
    native = PRIVATE / "community-sys-six-invoice-20261127U41MR2/receipt.json"
    require(digest(native) == "f377c74132a77b46b34b4f49f97539b49419b436da84f27267aa7c2436fdd008",
            "original-native-invoice-content-required")
    original = {(r["actor"], r["ref"]): r["text_sha256"] for r in json.loads(native.read_bytes())[0]}
    require(len(original) == 12, "native-reference-document-coverage")
    probe += "\nimport json\nassert env.cr.dbname==" + repr(args.database)
    probe += "\nprint('PINNED_RELEASE='+json.dumps(run(env,Path(" + repr(str(args.output)) + ")," + repr(original) + ")),flush=True)"
    log = args.output / ("retained-release-" + str(len(list(args.output.glob("retained-release-*.log")))) + ".log")
    status = odoo(args, "shell", [], log, probe.encode())
    rows = [line.partition("=")[2] for line in log.read_text().splitlines() if line.startswith("PINNED_RELEASE=")]
    require(status == 0 and len(rows) == 1, "retained-policy-application-test-failed")
    save(args.output / "retained-release.json", json.loads(rows[0]))


def policy_impact(args):
    require(args.database.endswith(("U41M", "U41MP", "U41MQ", "U41MV", "U41MW")), "unexpected-impact-scope")
    code = Path(__file__).with_name("probe_sys_original_policy_impact.py").read_text()
    code += "\nimport json\nassert env.cr.dbname==" + repr(args.database)
    code += "\nprint('POLICY_IMPACT='+json.dumps(run(env,Path(" + repr(str(args.output / "runtime")) + "))),flush=True)"
    count = len(list(args.output.glob("policy-impact-*.log")))
    log = args.output / ("policy-impact-" + str(count) + ".log")
    status = odoo(args, "shell", [], log, code.encode())
    records = [l.partition("=")[2] for l in log.read_text().splitlines() if l.startswith("POLICY_IMPACT=")]
    require(status == 0 and len(records) == 1, "original-role-policy-comparison-failed")
    save(args.output / "policy-impact.json", json.loads(records[0]))


def journal_migration(args):
    script = args.sealed / "runtime/addons/l10n_latam_invoice_document/migrations/1.1/post-migration.py"
    require(digest(script) == "9b8db12f8dd82f88133dfa6299cfa432f10ba2aef170298fd2774e20efaeda7a",
            "unexpected-journal-migration")
    probe = Path(__file__).with_name("probe_latam_11_journal_migration.py").read_text()
    code = script.read_text() + "\n" + probe + "\nimport json\nprint('LATAM_SCRIPT='+json.dumps(check(env.cr," + repr(args.database) + ",migrate)))"
    root = args.output / "upgrade-l10n_latam_invoice_document"
    log = root / ("migration-probe-" + str(len(list(root.glob("migration-probe-*.log")))) + ".log")
    status = odoo(args, "shell", [], log, code.encode())
    result = [l.partition("=")[2] for l in log.read_text().splitlines() if l.startswith("LATAM_SCRIPT=")]
    require(status == 0 and len(result) == 1, "isolated-journal-migration-failed")
    return json.loads(result[0])


def final_receipt(args, proof, filename="final.json"):
    out, db = args.output, args.database
    restored = json.loads((out / "restored.json").read_bytes())
    require(restored["database"] == db and restored["sealed"] == str(args.sealed), "wrong-target")
    jobs = {}
    for name in (FORWARD if db.endswith(("U41MQ", "U41MV", "U41MW")) else MODULES):
        jobs[name] = json.loads((out / ("upgrade-" + name) / "receipt.json").read_bytes())
    original = json.loads(gzip.decompress((args.sealed / "source-snapshot.json.gz").read_bytes()))
    current = snapshot(db)
    delta = differences(original, current)
    source = proof["source"]
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9]+", source), "unexpected-source")
    max_alias = int(query(source, "SELECT max(id) FROM ir_model_data"))
    aliases = original_aliases(source, max_alias)
    require(aliases == original_aliases(db, max_alias), "original-xmlid-drift")
    require(guards(db) == restored["guards"], "original-guards-drift")
    store = out / "data" / "filestore" / db
    with tarfile.open(args.sealed / "filestore.tar", "r|") as archive:
        original_files = {}
        for member in archive:
            require(member.isfile() and re.fullmatch(r"[0-9a-f]{2}/[0-9a-f]{40}", member.name),
                    "unexpected-archive-object")
            original_files[member.name] = member.size
            obj = store / member.name
            require(obj.is_file() and obj.stat().st_size == member.size and digest(obj, "sha1") == obj.name,
                    "original-attachment-bytes-changed")
    attachment_sql = """SELECT json_build_array(count(*), md5(string_agg(md5(to_jsonb(a)::text),'' ORDER BY id)))
                        FROM ir_attachment a WHERE res_model='hr.payslip' AND mimetype='application/pdf'"""
    pdfs = json.loads(query(source, attachment_sql))
    require(pdfs == json.loads(query(db, attachment_sql)), "archived-payroll-documents-changed")
    proof_tables = ("account_move", "account_move_line", "account_journal", "account_analytic_line",
                    "project_project", "project_task", "sms_sms", "hr_employee", "hr_contract",
                    "hr_payslip", "hr_payslip_line", "hr_payslip_input", "hr_payslip_worked_days", "hr_payslip_run",
                    "hr_payroll_structure", "hr_salary_rule", "resource_calendar", "resource_calendar_attendance",
                    "res_groups", "ir_rule", "ir_model_access", "res_groups_users_rel", "res_groups_implied_rel", "rule_group_rel")
    require(all(name in original["public_tables"] for name in proof_tables), "missing-covered-table")
    if db.endswith("U41MW"):
        require("l10n_cl_account_invoice_reference" in original["public_tables"], "original-invoice-references-required")
    checks = set(proof_tables) | (set(original["public_tables"]) & {
        "hr_causal_contract_end", "hr_employee_movement_type", "hr_contract_type", "hr_work_entry_type",
        "hr_leave_type", "res_city", "res_country_state", "res_company", "ir_sequence", "ir_sequence_date_range",
        "res_bank", "account_account_tag", "account_report", "account_report_column", "account_report_expression",
        "account_report_line", "l10n_latam_document_type", "l10n_latam_identification_type", "l10n_cl_account_invoice_reference"})
    lost_required = [key for key, definition in original["columns"].items() if definition[1] and
                     (key not in current["columns"] or not current["columns"][key][1])]
    versions = module_versions(db)
    result = {"relaxed_original_required_columns": sorted(lost_required), "official_results": {m: entry["passed"] for m, entry in jobs.items()},
              "versions": {m: versions[m] for m in (*MODULES, "step_payroll_oca_sys_history")},
              "sealed_runtime": proof["runtime"]["archive_sha256"], "original_aliases": aliases,
              "guard_count": len(restored["guards"]), "original_files": len(original_files),
              "archived_payroll_pdfs": pdfs[0], "full_sql_delta": delta,
              "covered_table_changes": sorted(checks.intersection(delta["public_tables"])),
              "after_free": check_space(0)}
    if db.endswith(("U41MQ", "U41MV", "U41MW")):
        result["retained_source_providers"] = json.loads((out / "pinned-providers.json").read_bytes())
        require(all(versions[m] == ["installed", "18.0.1.0"] for m in TREES), "original-policy-version-drift")
    save(out / filename, result)
    return result


def upgrade(args, proof):
    db, out, module = args.database, args.output, args.module
    restored = json.loads((out / "restored.json").read_bytes())
    require(restored["database"] == db and restored["sealed"] == str(args.sealed) and
            restored["runtime"] == proof["runtime"]["archive_sha256"], "wrong-source")
    check_space(0)
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{db}'") == "0", "target-in-use")
    providers = json.loads((args.sealed / "effective-providers.json").read_bytes())
    old, expected = MODULES[module]
    require(providers[module][1] == expected, "manifest-version-mismatch")
    run = out / ("upgrade-" + module)
    run.mkdir(mode=0o700, exist_ok=True)
    require(not (run / "receipt.json").exists() and not (run / (module + ".log")).exists(), "upgrade-already-ran")
    before = snapshot(db)
    require(guards(db) == restored["guards"], "original-guards-changed-before-upgrade")
    initial = module_versions(db)
    journals = journal_domain(db)
    max_alias = int(query(db, "SELECT max(id) FROM ir_model_data"))
    aliases = original_aliases(db, max_alias)
    previous_stage = None
    if initial[module] == ["installed", expected]:
        for other in sorted(out.glob("upgrade-*/receipt.json")):
            prior = json.loads(other.read_bytes())
            if prior["all_module_state_changes"].get(module) == [["installed", old], ["installed", expected]]:
                previous_stage = prior["module"]
                break
        require(previous_stage, "version-advanced-outside-recorded-official-upgrade")
    else:
        require(initial[module] == ["installed", old], "unexpected-initial-module-state")
    migration_case = journal_migration(args) if module == "l10n_latam_invoice_document" else None
    code = odoo(args, None, ["-u", module], run / (module + ".log"))
    final = module_versions(db)
    after = snapshot(db)
    log = out / "data" / (module + "-odoo.log")
    raw = log.read_text() if log.is_file() else ""
    require(guards(db) == restored["guards"], "original-guards-changed-after-upgrade")
    delta = differences(before, after)
    original_aliases_after = original_aliases(db, max_alias)
    changed_tables = {table: [before["public_tables"].get(table), after["public_tables"].get(table)]
                      for table in delta["public_tables"]}
    result = {"module": module, "aliases": [aliases, original_aliases_after], "table_fingerprints": changed_tables, "old": initial[module], "new": final[module], "expected": expected,
              "journal_script_probe": migration_case, "previous_upgrade_as_dependency": previous_stage, "journal_domain": [journals, journal_domain(db)], "odoo_exit": code, "manifest": providers[module][1], "loaded": "Modules loaded." in raw,
              "log_sha256": digest(log) if log.exists() else None,
              "passed": code == 0 and "Modules loaded." in raw and final[module] == ["installed", expected],
              "all_module_state_changes": {k: [initial.get(k), final.get(k)] for k in initial.keys() | final.keys()
                                           if initial.get(k) != final.get(k)}, "delta": delta,
              "pg_errors": sorted(set(re.findall(r"psycopg2\.errors\.([A-Za-z_]+)", raw)))}
    if (out / "profile").is_dir():
        require(after["columns"]["resource_calendar.previred_workday_type"][1], "native-calendar-must-remain-required")
        original_contracts = json.loads((out / "cohort-guards.json").read_bytes())["mandatory_columns"]
        result["original_required_columns"] = {key: after["columns"][key][1] for key in original_contracts}
        require(all(result["original_required_columns"].values()), "candidate-dropped-an-original-not-null")
        result["official_cleanup_with_supplier_protection"] = "SYS_OFFICIAL_CLEANUP" in (run / (module + ".log")).read_text()
        result["passed"] = result["passed"] and result["official_cleanup_with_supplier_protection"]
    save(run / "receipt.json", result)
    print(json.dumps({k: result[k] for k in ("module", "new", "passed", "pg_errors")}), flush=True)


def payroll_exports(args, name="exports"):
    require(args.database in ("COMMUNITY_SYS_PREVIRED_MODULES_20261127U41M",
                              "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MP",
                              "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MQ",
                              "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MV",
                              "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MW"), "unapproved-export-rehearsal")
    out = args.output
    key = PRIVATE / "community-sys-payroll-exports-20261126U41X3/audit.key"
    code = Path(__file__).with_name("probe_sys_payroll_exports_all.py").read_text()
    code += "\nfrom pathlib import Path\nassert env.cr.dbname == " + repr(args.database)
    code += "\nprivate_key=Path(" + repr(str(out / "export-proof-key")) + ").read_bytes()"
    code += "\nprint('SIX_EXPORTS='+json.dumps(run(env,private_key)),flush=True)\n"
    log = out / (name + ".log")
    status = odoo(args, "shell", [], log, code.encode(), comparison_key=key)
    lines = [l.partition("=")[2] for l in log.read_text().splitlines() if l.startswith("SIX_EXPORTS=")]
    require(status == 0 and len(lines) == 1, "operator-export-probe-failed")
    observed = json.loads(lines[0])
    save(out / (name + ".json"), observed)


def compare_operator_exports(args, name="exports", comparison="complete-export-comparison"):
    out = args.output
    observed = json.loads((out / (name + ".json")).read_bytes())
    require(observed["database"] == args.database and not observed["enterprise"], "unexpected-export-origin")
    first = PRIVATE / "community-sys-payroll-exports-20261126U41X2/community/receipt.json"
    screen = PRIVATE / "community-sys-payroll-exports-20261126U41X3/community/receipt.json"
    require(digest(first) == "fb7f44d3ac8e2ba4e40e627a987dbfce34082d0ff771744652f5d83e64592f52"
            and digest(screen) == "7239988bd7c8c4339e1454545567d4d6e755464f087b75f8030f43c240bdcf1f",
            "unexpected-community-export-receipt")
    original = json.loads(first.read_bytes())
    companies, actors = index(original)
    screen_companies, screen_actors = index(json.loads(screen.read_bytes()))
    new_companies, new_actors = index(observed)
    require(len(companies) == 12 and companies.keys() == new_companies.keys() == screen_companies.keys()
            and len(actors) == 24 and actors.keys() == new_actors.keys() == screen_actors.keys(), "original-export-coverage-differs")
    scope_changes = [k for k in companies if any(not companies[k][field] == new_companies[k][field] == screen_companies[k][field]
                    for field in ("period", "closed", "closed_ids"))]
    # X2 contains the 1.5.0 TXT payloads and diagnostics. The next recorded run added the two screen signatures.
    for key, entry in actors.items():
        for field in ("validation_screen", "generation_screen"):
            require(field not in entry["previred"] and field in screen_actors[key]["previred"], "unexpected-screen-baseline")
            entry["previred"][field] = screen_actors[key]["previred"][field]
    mismatch = {str(k): changes(actors[k], new_actors[k]) for k in actors if actors[k] != new_actors[k]}
    result = {"reference": digest(first), "screen_reference": digest(screen),
        "companies": len(companies), "pairs": len(actors),
        "scope_differences": scope_changes, "full_result_differences": mismatch,
        "matches": not scope_changes and not mismatch, "originals_preserved": observed["originals_preserved"]}
    target = out / (comparison + ".json")
    if target.is_file():
        require(json.loads(target.read_bytes()) == result, "previous-export-comparison-differs")
    else:
        save(target, result)


def print_chilean_invoices(args, proof):
    out = args.output
    require(args.database.endswith("U41MW") and (out / "retained-release.json").is_file(), "original-invoice-render-required")
    name = "invoice-pdf-" + str(len(list(out.glob("invoice-pdf-*.log"))))
    script = Path(__file__).with_name("probe_sys_invoice_pdf.py").read_text()
    script += "\nprint('ORIGINAL_INVOICE_PDF='+json.dumps(run(env)),flush=True)\n"
    code = odoo(args, "shell", [], out / (name + ".log"), script.encode(), loopback=True)
    entries = [json.loads(l.partition("=")[2]) for l in (out / (name + ".log")).read_text().splitlines()
               if l.startswith("ORIGINAL_INVOICE_PDF=")]
    require(code == 0 and len(entries) == 1, "original-invoice-pdf-did-not-render")
    save(out / "invoice-pdf.json", entries[0])
    final = final_receipt(args, proof, "postflight-pdf.json")
    require(not final["covered_table_changes"] and not final["relaxed_original_required_columns"], "invoice-pdf-altered-history")


def candidate_batch(args, proof):
    require(args.database.endswith(("U41MP", "U41MQ", "U41MV", "U41MW")) and (args.output / "profile-proof.json").is_file(), "profile-required")
    require(not (args.output / "final.json").exists(), "finished-candidate")
    if args.database.endswith(("U41MQ", "U41MV", "U41MW")):
        verify_retained_profile(args)
    for label in ("forms-before", "forms-after"):
        if label == "forms-after":
            for module in (FORWARD if args.database.endswith(("U41MQ", "U41MV", "U41MW")) else MODULES):
                args.module = module
                receipt = args.output / ("upgrade-" + module) / "receipt.json"
                if not receipt.exists():
                    upgrade(args, proof)
        args.label = label
        if not (args.output / (label + ".json")).exists():
            try:
                forms(args)
            except ValueError as exc:
                if "original-role-form-probe-failed" not in str(exc):
                    raise
                print(label, "inspect-private-role-log", flush=True)
    final_receipt(args, proof)


def prepare_profile(args):
    identity = json.loads((args.output / "restored.json").read_bytes())
    require(args.database.endswith(("U41MP", "U41MQ", "U41MV", "U41MW")) and identity["database"] == args.database
            and identity["sealed"] == str(args.sealed), "separate-policy-profile-copy-required")
    versions = module_versions(args.database)
    require(all(versions[k] == ["installed", v[0]] for k, v in MODULES.items()), "profile-requires-original-versions")
    keep_original = args.database.endswith(("U41MQ", "U41MV", "U41MW"))
    fiscal = args.database.endswith(("U41MV", "U41MW"))
    selected = (*FORWARD, "step_payroll_engine_transition") if keep_original else MODULES
    if fiscal:
        selected = (*selected, "step_account_monthly_books")
    if keep_original:
        require((args.output / "pinned-providers.json").is_file(), "old-policy-providers-required")
    save(args.output / "profile-proof.json", build(args.database, args.sealed, args.output / "profile",
                                                  selected, original_admin_seeds=keep_original, original_fiscal=fiscal))


def package_profile(args, proof):
    directory, receipt = effective_profile(args.output)
    expected = json.loads(receipt.read_bytes())
    result = seal_profile(directory, args.output / "upgrade-profile.tar", expected)
    result.update(runtime=proof["runtime"]["archive_sha256"], guard_plan=digest(guarded_plan(args)))
    save(args.output / "upgrade-profile.json", result)


def restore_financial_actions(args, proof):
    out = args.output
    require(args.database.endswith("U41MW"), "private-financial-action-rehearsal-required")
    initial = json.loads((out / "final.json").read_bytes())
    constraints = ["account_move_line.account_move_line_account_id_fkey",
                   "account_reconcile_model_line_account_tax_rel.account_reconcile_model_line_account_tax_re_account_tax_id_fkey"]
    require(initial["full_sql_delta"]["constraints"] == constraints and not initial["covered_table_changes"]
            and all(initial["official_results"].values()), "unexpected-pre-repair-financial-delta")
    receipt = out / "tested-profile-proof.json"
    if not receipt.is_file():
        selected = (*FORWARD, "step_payroll_engine_transition", "step_account_monthly_books")
        save(receipt, build(args.database, args.sealed, out / "tested-profile", selected,
                           original_admin_seeds=True, original_fiscal=True))
    expected = json.loads(receipt.read_bytes())
    required = expected["modules"]["l10n_cl"]["invoice_reference_provider"]
    require(required["financial_relation_ids"] == [5963, 6077] and required["original_financial_delete_actions"] == "c,r",
            "original-financial-policies-not-in-package")
    if not (out / "finance-profile.json").is_file():
        package = seal_profile(out / "tested-profile", out / "finance-profile.tar", expected)
        package.update(runtime=proof["runtime"]["archive_sha256"], guard_plan=digest(guarded_plan(args)))
        save(out / "finance-profile.json", package)
    args.module = "l10n_latam_invoice_document"
    log = out / ("financial-actions-" + str(len(list(out.glob("financial-actions-*.log")))) + ".log")
    require(odoo(args, None, ["-u", args.module], log) == 0 and "SYS_OFFICIAL_CLEANUP" in log.read_text(),
            "official-financial-action-update-failed")
    final = final_receipt(args, proof, "financial-storage.json")
    require(not any(final["full_sql_delta"][name] for name in ("columns", "constraints", "relation_owner_and_acl",
            "sequence_definitions")) and not final["covered_table_changes"], "original-financial-storage-differs")
    require(query(args.database, "SELECT on_delete FROM ir_model_fields WHERE id=6077") == "cascade",
            "runtime-account-field-policy-differs")
    pairs = query(args.database, """SELECT conname,confdeltype FROM pg_constraint WHERE conname IN
        ('account_move_line_account_id_fkey', 'account_reconcile_model_line_account_tax_re_account_tax_id_fkey') ORDER BY conname""")
    require([row.rsplit("|", 1)[1] for row in pairs.splitlines()] == ["c", "r"], "historical-foreign-key-actions-required")
    actions = {"c": "CASCADE", "r": "RESTRICT"}
    ledger, tax = [actions[row.rsplit("|", 1)[1]] for row in pairs.splitlines()]
    trial = f"""BEGIN;
        CREATE TEMP TABLE steps_trial_accounts (id integer PRIMARY KEY);
        CREATE TEMP TABLE steps_trial_tax (id integer PRIMARY KEY);
        CREATE TEMP TABLE steps_trial_ledger (account_id integer REFERENCES steps_trial_accounts(id) ON DELETE {ledger});
        CREATE TEMP TABLE steps_trial_tax_rel (tax_id integer REFERENCES steps_trial_tax(id) ON DELETE {tax});
        INSERT INTO steps_trial_accounts VALUES(1); INSERT INTO steps_trial_ledger VALUES(1);
        INSERT INTO steps_trial_tax VALUES(1); INSERT INTO steps_trial_tax_rel VALUES(1);
        DELETE FROM pg_temp.steps_trial_accounts WHERE id=1;
        DO $$ BEGIN BEGIN DELETE FROM pg_temp.steps_trial_tax WHERE id=1;
            RAISE EXCEPTION 'Expected the original tax reference restriction'; EXCEPTION WHEN foreign_key_violation THEN NULL; END; END $$;
        SELECT (SELECT count(*) FROM pg_temp.steps_trial_ledger),(SELECT count(*) FROM pg_temp.steps_trial_tax_rel);
        ROLLBACK;"""
    exercise = pg("psql", "-XAtq", "-v", "ON_ERROR_STOP=1", args.database, "-c", trial,
                  text=True, stdout=subprocess.PIPE)
    require(exercise.stdout.strip() == "0|1", "native-financial-deletion-fixture-failed")
    save(out / "financial-delete-actions.json", {"actions": pairs.splitlines(), "original_field": 6077,
        "ledger_row_cascaded": True, "tax_row_retained": True, "temporary_rows_rolled_back": True})


def finish_financial_release(args, proof):
    out = args.output
    require(args.database.endswith("U41MW"), "final-financial-release-required")
    if not (out / "financial-storage.json").is_file():
        restore_financial_actions(args, proof)
    require((out / "financial-delete-actions.json").is_file(), "original-delete-policies-not-proven")
    if not (out / "retained-release.json").is_file():
        retained_release(args)
    if not (out / "release-exports.json").is_file():
        payroll_exports(args, "release-exports")
    compare_operator_exports(args, "release-exports", "release-export-comparison")
    result = json.loads((out / "release-export-comparison.json").read_bytes())
    require(result["originals_preserved"] and result["matches"], "final-financial-payroll-regression")
    if not (out / "invoice-pdf.json").is_file():
        print_chilean_invoices(args, proof)


def exercise_final(args, proof):
    require(args.database.endswith(("U41MV", "U41MW")) and not (args.output / "postflight.json").exists(),
            "fresh-final-rehearsal-required")
    out = args.output
    if not (out / "pinned-providers.json").is_file():
        pin_original_providers(args)
    if not (out / "profile-proof.json").is_file():
        prepare_profile(args)
    if not (out / "upgrade-profile.json").is_file():
        package_profile(args, proof)
    if not (out / "final.json").is_file():
        candidate_batch(args, proof)
    first = json.loads((out / "final.json").read_bytes())
    require(all(first["official_results"].values()) and not first["relaxed_original_required_columns"]
            and not first["covered_table_changes"], "primary-official-upgrade-checks-did-not-pass")
    if not (out / "retained-release.json").is_file():
        retained_release(args)
    if not (out / "exports.json").is_file():
        payroll_exports(args)
    if not (out / "complete-export-comparison.json").is_file():
        compare_operator_exports(args)
    exports = json.loads((out / "complete-export-comparison.json").read_bytes())
    require(exports["matches"] and exports["originals_preserved"], "operator-payroll-export-regression")
    final = final_receipt(args, proof, "postflight.json")
    require(not final["relaxed_original_required_columns"] and not final["covered_table_changes"],
            "economic-storage-changed-after-operator-tests")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sealed", type=Path, required=True)
    parser.add_argument("operation", choices=("restore", "upgrade", "forms", "policy", "policy-impact", "profile", "prepare-retained", "accept-retained", "pin-providers", "seal-profile", "candidate-batch", "exports", "exercise-final", "invoice-pdf", "financial-actions", "finish-financial", "final"))
    parser.add_argument("--module", choices=MODULES)
    parser.add_argument("--label", choices=("forms-before", "forms-after", "forms-checkpoint"))
    args = parser.parse_args()
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_MODULES_[A-Z0-9]+", args.database)
            and args.output.resolve() == args.output and args.output.parent == PRIVATE
            and args.output.name == "community-sys-six-upgrades-" + args.database.rsplit("_", 1)[1]
            and args.sealed.resolve() == args.sealed and args.sealed.is_relative_to(PRIVATE)
            and args.sealed.name == "sealed", "private-scope-required")
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proof = json.loads((args.sealed / "backup.json").read_bytes())
        if args.operation == "exercise-final":
            exercise_final(args, proof)
        elif args.operation == "invoice-pdf":
            print_chilean_invoices(args, proof)
        elif args.operation == "financial-actions":
            restore_financial_actions(args, proof)
        elif args.operation == "finish-financial":
            finish_financial_release(args, proof)
        elif args.operation == "restore":
            restore(args, proof)
        elif args.operation == "accept-retained":
            retained_release(args)
        elif args.operation == "policy-impact":
            policy_impact(args)
        elif args.operation == "pin-providers":
            pin_original_providers(args)
        elif args.operation == "seal-profile":
            require(args.database.endswith(("U41MP", "U41MQ", "U41MV", "U41MW")), "separate-policy-profile-copy-required")
            package_profile(args, proof)
        elif args.operation == "exports":
            if not (args.output / "exports.json").is_file():
                payroll_exports(args)
            compare_operator_exports(args)
        elif args.operation == "candidate-batch":
            candidate_batch(args, proof)
        elif args.operation == "profile":
            prepare_profile(args)
        elif args.operation == "prepare-retained":
            require(args.database.endswith(("U41MQ", "U41MV", "U41MW")), "retained-policy-scope-required")
            if not (args.output / "pinned-providers.json").exists():
                pin_original_providers(args)
            prepare_profile(args)
        elif args.operation == "final":
            final_receipt(args, proof)
        elif args.operation == "policy":
            identity = json.loads((args.output / "restored.json").read_bytes())
            require(identity["database"] == args.database and identity["sealed"] == str(args.sealed), "wrong-target")
            save(args.output / "policy.json", audit(args.database, args.sealed / "runtime", MODULES))
        elif args.operation == "forms":
            require(args.label, "form-label-required")
            forms(args)
        else:
            require(args.module, "module-required")
            upgrade(args, proof)
