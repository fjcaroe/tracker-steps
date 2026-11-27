"""Compare original SyS absences, generated work entries and payslip days in two private WSL restorations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from seal_local_sys_193 import DB as CONTROL, MEM, PORT, SOCKET, call, psql, sha, verify

U47 = Path("/dev/shm/sys-u47-leaves")
NATIVE = "MANAGEMENT_QA_SYS_LEAVES_20261127U47N"
TARGET = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U47C"
NATIVE_SHA = "669f58d3eb1f5240bcd248b2f2a905d52b76752274dfc5396d14b5ad118c17f0"


def restore(refs):
    if psql("SHOW data_directory", "postgres") != "/dev/shm/sys-fg-193/postgres/cluster" or shutil.disk_usage("/dev/shm").free < 1400*1024**2:
        raise ValueError("A dedicated memory-only cluster with sufficient room is required")
    U47.mkdir(mode=0o711,exist_ok=True)
    native=refs/"U30/u40-offhost"
    original = json.loads((native/"backup.json").read_bytes())
    assert original["source"]=="SyS" and original["sha256"] == NATIVE_SHA and sha(native/"sys.dump")==NATIVE_SHA
    sealed=MEM/"from-durable-kit"
    verify(sealed, refs/"U43C/fiscal-payroll-documents")
    for db,source in ((NATIVE,native/"sys.dump"),(TARGET,sealed/"source.dump")):
        if not psql("SELECT 1 FROM pg_database WHERE datname='"+db+"'", "postgres"):
            call("postgres",["createdb","-h",SOCKET,"-p",PORT,"-O","odoo","-T","template0","-E","UTF8",
                             "--lc-collate=C","--lc-ctype=C.UTF-8",db])
        if not psql("SELECT to_regclass('public.hr_leave')",db):
            if psql("SELECT count(*) FROM pg_tables WHERE schemaname='public'",db)!="0":
                raise ValueError("Expected a fresh private copy")
            with source.open("rb") as f:
                call("postgres",["pg_restore","-h",SOCKET,"-p",PORT,"-d",db,"--no-tablespaces","--single-transaction","--exit-on-error"],stdin=f)
    data = U47/"data"
    store = data/"filestore"/TARGET
    if not store.exists():
        shutil.copytree(MEM/"data/filestore"/CONTROL,store)
        for base,dirs,files in os.walk(data):
            os.chown(base,61018,61018)
            for name in files:
                os.chown(Path(base)/name,61018,61018)
    print("Restored native source and final product on the private memory filesystem")


PROJECTION = {
 "requests": """SELECT id,state,employee_id,company_id,holiday_status_id,request_date_from,request_date_to,
    date_from,date_to,number_of_days,first_approver_id,second_approver_id FROM hr_leave""",
 "entitlements": """SELECT id,state,employee_id,holiday_status_id,date_from,date_to,number_of_days FROM hr_leave_allocation""",
 "entry_types": """SELECT id,work_entry_type_id FROM hr_leave_type""",
 "work_entries": """SELECT id,employee_id,contract_id,leave_id,work_entry_type_id,state,date_start,date_stop FROM hr_work_entry""",
 "payslip_days": """SELECT id,payslip_id,work_entry_type_id,number_of_days,number_of_hours FROM hr_payslip_worked_days""",
 "without_entry": """SELECT l.id,l.employee_id,l.company_id,l.holiday_status_id,l.request_date_from,l.request_date_to
    FROM hr_leave l WHERE l.state='validate' AND NOT EXISTS(SELECT 1 FROM hr_work_entry w WHERE w.leave_id=l.id)""",
 "linked": """SELECT l.id AS leave_id,w.id AS work_id,p.id AS slip_id,d.id AS day_id
    FROM hr_leave l JOIN hr_work_entry w ON w.leave_id=l.id JOIN hr_payslip p ON p.employee_id=l.employee_id
    AND w.date_start::date<=p.date_to AND w.date_stop::date>=p.date_from AND p.state IN ('done','paid')
    JOIN hr_payslip_worked_days d ON d.payslip_id=p.id AND d.work_entry_type_id=w.work_entry_type_id
    WHERE l.state='validate'"""
}


def census(db):
    rows = {}
    for name,query in PROJECTION.items():
        q = """SELECT json_build_array(count(*),encode(sha256(convert_to(coalesce(string_agg(v,'' ORDER BY v),''),'UTF8')),'hex'))
               FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') v FROM ("""+query+") t) values"
        rows[name]=json.loads(psql(q,db))
    periods="""WITH s AS (SELECT id,company_id,employee_id,date_from,date_to,max(date_to) OVER (PARTITION BY company_id) latest
          FROM hr_payslip WHERE struct_id=4 AND state IN ('done','paid') AND date_from=date_trunc('month',date_from)::date
          AND date_to=(date_from+interval '1 month - 1 day')::date)
          SELECT json_build_array(count(DISTINCT l.id),count(DISTINCT s.id),count(DISTINCT s.company_id))
          FROM s JOIN hr_leave l ON l.employee_id=s.employee_id AND l.request_date_from<=s.date_to AND l.request_date_to>=s.date_from
          WHERE l.state='validate' AND s.date_to=s.latest"""
    rows["latest"]=json.loads(psql(periods,db))
    missing = """WITH absent AS (SELECT l.id,l.employee_id,l.request_date_from,l.request_date_to,t.work_entry_type_id
        FROM hr_leave l JOIN hr_leave_type t ON t.id=l.holiday_status_id WHERE l.state='validate' AND NOT EXISTS
        (SELECT 1 FROM hr_work_entry w WHERE w.leave_id=l.id)), kinds AS (SELECT work_entry_type_id IS NOT NULL typed,
        EXISTS(SELECT 1 FROM hr_contract c WHERE c.employee_id=a.employee_id AND c.date_start<=a.request_date_to
             AND coalesce(c.date_end,DATE '9999-12-31')>=a.request_date_from) employed, EXISTS(SELECT 1 FROM hr_work_entry w
             WHERE w.employee_id=a.employee_id AND w.date_start::date<=a.request_date_to AND w.date_stop::date>=a.request_date_from) has_work,
        EXISTS(SELECT 1 FROM hr_payslip p WHERE p.employee_id=a.employee_id AND p.state IN ('paid','done')
             AND p.date_from<=a.request_date_to AND p.date_to>=a.request_date_from) closed FROM absent a)
        SELECT json_agg(x) FROM (SELECT typed,employed,has_work,closed,count(*) FROM kinds GROUP BY 1,2,3,4 ORDER BY 1,2,3,4) x"""
    rows["absence_without_link_context"]=json.loads(psql(missing,db))
    menu = """SELECT json_build_array(m.id,a.id,m.action,a.res_model,v.id,
        encode(sha256(convert_to(v.arch_db::text,'UTF8')),'hex')) FROM ir_ui_menu m
        JOIN ir_act_window a ON m.action='ir.actions.act_window,'||a.id CROSS JOIN ir_ui_view v
        WHERE m.id=382 AND a.id=619 AND v.id=1781"""
    rows["approval_menu"]=json.loads(psql(menu,db))
    stats = {
        "requests_by_status":"SELECT json_object_agg(state,n) FROM (SELECT state,count(*) n FROM hr_leave GROUP BY state) s",
        "entitlements_by_status":"SELECT json_object_agg(state,n) FROM (SELECT state,count(*) n FROM hr_leave_allocation GROUP BY state) s",
        "work_links":"SELECT json_build_array(count(*),count(DISTINCT w.leave_id),count(DISTINCT l.employee_id),count(DISTINCT l.company_id)) FROM hr_work_entry w JOIN hr_leave l ON l.id=w.leave_id WHERE l.state='validate'",
        "worked_day_links":"""SELECT json_build_array(count(DISTINCT l.id),count(DISTINCT p.id),count(DISTINCT p.company_id),count(DISTINCT d.id))
          FROM hr_leave l JOIN hr_payslip p ON p.employee_id=l.employee_id AND p.state IN ('done','paid')
          AND l.request_date_from<=p.date_to AND l.request_date_to>=p.date_from JOIN hr_leave_type t ON t.id=l.holiday_status_id
          JOIN hr_payslip_worked_days d ON d.payslip_id=p.id AND d.work_entry_type_id=t.work_entry_type_id WHERE l.state='validate'"""
    }
    rows.update({key:json.loads(psql(query,db)) for key,query in stats.items()})
    return rows


def compare():
    native,product=census(NATIVE),census(TARGET)
    if native!=product:
        raise ValueError("An original absence relation differs: "+str([k for k in native if native[k]!=product[k]]))
    assert native["without_entry"][0]==6 and native["requests_by_status"]=={"validate":140,"refuse":8}
    proof={"source_sql":NATIVE_SHA,"final_release":sha(MEM/"from-durable-kit/release.json"),"all_projections_match":True,**native}
    (U47/"native-and-product.json").write_text(json.dumps(proof,sort_keys=True))
    print(json.dumps({k:v for k,v in proof.items() if k not in PROJECTION},sort_keys=True))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action",choices=("restore","compare","post"))
    p.add_argument("references",type=Path)
    args=p.parse_args()
    if args.action=="restore":
        restore(args.references)
    elif args.action=="compare":
        compare()
    else:
        from seal_local_sys_193 import capture
        import gzip
        folder=U47/"after"
        folder.mkdir(exist_ok=True)
        measured=capture(TARGET,SOCKET,PORT,folder)
        frozen=json.loads(gzip.decompress((MEM/"from-durable-kit/snapshot.json.gz").read_bytes()))
        assert measured["catalogue"]==frozen["catalogue"]
        for key,rows in frozen["snapshot"].items():
            if key=="sequence_values":
                continue
            assert measured["snapshot"][key]==rows,key
        old=frozen["snapshot"]["sequence_values"]
        new=measured["snapshot"]["sequence_values"]
        changes={k:[v,new[k]] for k,v in old.items() if v!=new[k]}
        assert old.keys()==new.keys() and all(a[0]<=b[0] and b[1] for a,b in changes.values())
        receipt={"source_rows":sum(v[0] for v in frozen["snapshot"]["public_tables"].values()),
                 "source_tables":len(frozen["snapshot"]["public_tables"]),"all_rows_unchanged":True,
                 "schema_unchanged":True,"advanced_sequences":changes,
                 "native_equivalence_sha256":sha(U47/"native-and-product.json"),"approvals_sha256":sha(U47/"functional.json")}
        (U47/"after.json").write_text(json.dumps(receipt,sort_keys=True))
        print(sha(U47/"after.json"))
