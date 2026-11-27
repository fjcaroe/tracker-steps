"""Seal the final Steps expense, credit-note and helpdesk copy as a new checkpoint over the accepted 166."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from admit_steps_credit_note_draft import DB, ROOT, STAGE, PAYMENTS, evidence, frozen
from custody_sys_previred_filestore import digest
from restore_converted_sys_cohort import check_modules, save
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import resolve_providers
from verify_converted_sql_schema import schema
from verify_steps_expense_credit_backup import MODULES, PARENT, PIECES, REQUIRED, archive_tree, verify
from verify_steps_support_backup import canonical, strong


BASE = ROOT.parent
PREVIOUS_HOST = PAYMENTS.parent.parent
H3 = BASE/"steps-sales-support-20261127U44H3/final-checkpoint"
FISCAL = BASE/"steps-integrated-20261127U46A/final-checkpoint"
FOUNDATION = BASE/"recovery-community_steps_crm_recovery_20261127u44r"


def read(path):
    return json.loads(path.read_bytes())


def roots(argv):
    value, = [arg.split("=",1)[1] for arg in argv if arg.startswith("--addons-path=")]
    return [Path(p) for p in value.split(",")]


def sources(active):
    before = read(PREVIOUS_HOST/"private-args.json")
    argv = read(ROOT/"private-args.json")
    require(argv[argv.index("-d")+1]==DB and "--net" in argv and "--no-http" in argv,"wrong-168-runtime")
    base_roots=roots(before)
    current=roots(argv)
    engine=FOUNDATION/"sealed/runtime"
    require(current[2:]==base_roots and str(engine/"odoo-bin") in argv,"168-runtime-precedence-drift")
    parent=frozen("providers.json")
    check_code="from seal_steps_payment_release import code\nimport json,sys\ncode(json.load(sys.stdin))"
    subprocess.run(["python3","-B","-c",check_code],input=json.dumps(parent).encode(),
                   cwd=PREVIOUS_HOST/"code",stdout=subprocess.DEVNULL,check=True)
    previous=resolve_providers(engine,base_roots,PREVIOUS_HOST/"data",parent)
    effective=resolve_providers(engine,current,ROOT/"data",active)
    require(all(effective[k]==row for k,row in previous.items()),"earlier-166-providers-changed")
    files={"step_expense_documents":ROOT/"expense-documents"/(MODULES["step_expense_documents"][2]+".tar"),
           "step_cl_credit_note_draft":STAGE/"package.tar"}
    for name,archive in files.items():
        version,license_,sha=MODULES[name]
        require(digest(archive)==sha and effective[name][1:]==[version,license_],
                "incorrect-168-provider-version-or-license")
        expected=archive_tree(archive,name)
        source=Path(effective[name][0])
        require(source==current[0 if name=="step_cl_credit_note_draft" else 1]/name and
                {str(p.relative_to(source.parent)):digest(p) for p in source.rglob("*") if p.is_file()}==expected,
                "effective-168-provider-files-differ-"+name)
    return files


def seal(evidence_sha):
    require(Path(__file__).resolve().parent==ROOT/"code" and digest(PAYMENTS/"checkpoint.json")==PARENT,
            "wrong-168-release-environment")
    inputs=STAGE/"final-evidence"
    path=inputs/"manifest.json"
    require(digest(path)==evidence_sha,"wrong-168-business-input")
    receipts=read(path)
    require(REQUIRED<=receipts.keys() and all(Path(n).name==n and n.endswith(".json") and digest(inputs/n)==v
            for n,v in receipts.items()),"wrong-168-business-receipt")
    final=STAGE/"final-checkpoint"
    if final.is_dir():
        require(read(final/"checkpoint.json")["evidence"]==receipts,"alternate-168-release")
        return verify(FOUNDATION,H3,FISCAL,PAYMENTS,final,digest(final/"checkpoint.json"))
    # Only the final database dump and the two new release files are written on this volume.
    expected_bytes=2*sum(v[0] for v in read(PAYMENTS/"checkpoint.json")["files"].values())+sum((inputs/n).stat().st_size for n in receipts)
    main=Path(query("postgres","SHOW data_directory")).resolve(strict=True)
    require(shutil.disk_usage(main).free>5*GIB and shutil.disk_usage(ROOT).free>5*GIB+expected_bytes and
            query("postgres","SELECT count(*) FROM pg_stat_activity WHERE datname='"+DB+"'")=="0",
            "168-checkpoint-capacity-or-active-session")
    active=check_modules(DB,"hr_expense")
    require(active=={**frozen("providers.json"), **{name:list(spec[:2]) for name,spec in MODULES.items()}},
            "wrong-168-providers")
    packages=sources(active)
    before=evidence()
    sql=before["sql"]
    ddl=before["objects"]
    tree=before["filestore"]
    require(ddl==frozen("sql-objects.json.gz"),"unexpected-168-SQL-change")
    previous=frozen("filestore.json.gz")
    delta=sorted(n for n,v in tree.items() if previous.get(n)!=v)
    parents=read(PAYMENTS/"checkpoint.json")
    roles=json.loads(query(DB,"""SELECT json_agg(name ORDER BY name) FROM (
       SELECT DISTINCT pg_get_userbyid(refobjid) AS name FROM pg_shdepend
       WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND refclassid='pg_authid'::regclass
       UNION SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) r"""))
    require(roles==parents["required_roles"],"168-original-owners-changed")
    with TemporaryDirectory(dir=STAGE) as temporary:
        out=Path(temporary)/"sealed"
        out.mkdir()
        for name,archive in packages.items():
            shutil.copyfile(archive,out/(name+".tar"))
        with (out/"source.dump").open("xb") as handle:
            pg("pg_dump","-Fc","--no-tablespaces",DB,readonly=True,stdout=handle)
        stored=schema(subprocess.check_output(["pg_restore","--schema-only","--no-tablespaces","--file=-",str(out/"source.dump")]))
        current_schema=schema(pg("pg_dump","--schema-only","--no-tablespaces",DB,readonly=True,stdout=subprocess.PIPE).stdout)
        require(stored==current_schema==parents["schema_sha256"],"168-full-dump-schema-drift")
        save(out/"providers.json",active)
        for name,values in (("snapshot.json.gz",sql),("sql-objects.json.gz",ddl),("filestore.json.gz",tree)):
            (out/name).write_bytes(gzip.compress(canonical(values),mtime=0))
        with tarfile.open(out/"filestore-delta.tar","x") as archive:
            for name in delta:
                archive.add(ROOT/"data/filestore"/DB/name,arcname=name,recursive=False)
        with tarfile.open(out/"functional-evidence.tar","x") as archive:
            for name in sorted(receipts):
                archive.add(inputs/name,arcname=name,recursive=False)
        require(evidence()==before and check_modules(DB,"hr_expense")==active,"168-source-moved-while-sealing")
        index={"source":DB,"parent":PARENT,"required_roles":roles,"schema_sha256":current_schema,
               "rows":sum(v[0] for v in sql["public_tables"].values()),"tables":len(sql["public_tables"]),
               "sequences":len(sql["sequence_values"]),"sql_objects":len(ddl),"tree_sha256":strong(tree),
               "changed_files":delta,"removed_files":sorted(previous.keys()-tree.keys()),"evidence":receipts,
               "files":{name:[(out/name).stat().st_size,digest(out/name)] for name in PIECES}}
        save(out/"checkpoint.json",index)
        result=verify(FOUNDATION,H3,FISCAL,PAYMENTS,out,digest(out/"checkpoint.json"))
        out.rename(final)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-sha256",required=True)
    os.umask(0o077)
    with open(LOCK,"rb") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        print(json.dumps(seal(parser.parse_args().evidence_sha256)))
