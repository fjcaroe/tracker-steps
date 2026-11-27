"""Exercise failed calculation, invalid historical writes and the SQL catalogue of the U49 derivative."""
import gzip
import json
from pathlib import Path
import subprocess
import tempfile

import prepare_sys_payslip_form_trial as trial
from prepare_sys_negative_net import DB, SOURCE, WORK
from seal_local_sys_193 import PORT, SOCKET, capture, inventory, psql


def failures():
    probe = """
import json
from odoo.exceptions import UserError
from psycopg2 import IntegrityError
from datetime import date
assert env.cr.dbname in ('COMMUNITY_SYS_PREVIRED_COHORT_20261127U49D','COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E',
                         'COMMUNITY_SYS_PREVIRED_COHORT_20261127U49F')
scope=env(user=2,su=False,context={'allowed_company_ids':[7],'lang':'es_CL','tracking_disable':True,'mail_notify_force_send':False})
s=scope['hr.payslip'].browse(157)
assert s.state=='done' and s.has_negative_net_to_report and not s.negative_net_to_report_display
buttons=scope['hr.payslip'].get_view(view_type='form')['arch']
assert 'action_report_negative_amount' in buttons and 'action_sys_open_negative_activities' in buttons
rejected=[]
for label,q in [('clear', 'UPDATE hr_payslip SET has_negative_net_to_report=false WHERE id=157'),
                ('amount','UPDATE hr_payslip SET net_wage=net_wage+1 WHERE id=157'),
                ('delete','DELETE FROM hr_payslip WHERE id=157')]:
    try:
        with env.cr.savepoint():env.cr.execute(q)
    except IntegrityError as exc:
        assert exc.pgcode=='23514'
        rejected.append(label)
    else:raise AssertionError(label)
try:
    s.action_report_negative_amount()
except UserError:rejected.append('closed_button')
else:raise AssertionError('closed_button')
p=scope['hr.payslip'].create({'name':'Control de reversión de neto','employee_id':s.employee_id.id,
        'company_id':s.company_id.id,'contract_id':s.contract_id.id,'struct_id':s.struct_id.id,
        'date_from':date(2036,12,1),'date_to':date(2036,12,31)})
assert p.negative_net_to_report_display and not p.input_line_ids
env.cr.execute('SELECT last_value FROM hr_payslip_input_id_seq');seq=env.cr.fetchone()[0]
try:
    p.action_report_negative_amount()
except UserError as exc:
    failed_type=type(exc).__name__
else:raise AssertionError('missing future payroll configuration')
env.invalidate_all(flush=False)
env.cr.execute('SELECT last_value FROM hr_payslip_input_id_seq');after=env.cr.fetchone()[0]
assert after>seq and not p.input_line_ids and not p.move_id and p.state=='draft' and s.has_negative_net_to_report
assert p.negative_net_to_report_display
env.cr.rollback()
print('SYS '+json.dumps({'rejected':rejected,'calculation_failed_after_deduction_insert':failed_type,'financial_changes_rolled_back':True}),flush=True)
"""
    trial.DB,trial.WORK=DB,WORK
    try:
        response=trial.odoo(["shell"],probe.encode())
    except subprocess.CalledProcessError as exc:
        (WORK/"protection-error.log").write_bytes(exc.stderr)
        raise
    result,=[json.loads(x[4:]) for x in response.stdout.splitlines() if x.startswith(b"SYS ")]
    return result


def storage():
    source=json.loads(gzip.decompress((WORK/"source/snapshot.json.gz").read_bytes()))
    final=capture(DB,SOCKET,PORT,Path(tempfile.mkdtemp(prefix="final-",dir=WORK)))
    assert source["catalogue"]==final["catalogue"]
    before,after=source["snapshot"],final["snapshot"]
    assert all(before[k]==after[k] for k in ("columns","constraints","relation_owner_and_acl","sequence_definitions"))
    changed={k:[before["public_tables"][k][0],data[0]] for k,data in after["public_tables"].items() if data!=before["public_tables"][k]}
    assert changed.keys()<={"ir_model_data","ir_model_fields","ir_module_module","ir_ui_view","ir_cron_trigger"}
    sql="""SELECT json_object_agg(p.oid::regprocedure::text,encode(sha256(convert_to(pg_get_functiondef(p.oid),'UTF8')),'hex'))
           FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prokind IN ('f','p')"""
    old,new=(json.loads(psql(sql,d)) for d in (SOURCE,DB))
    assert old.keys()==new.keys()
    names=[k for k in old if old[k]!=new[k]]
    assert names==["steps_sys_history_guard_hr_payslip()"]
    triggers="""SELECT encode(sha256(convert_to(string_agg(pg_get_triggerdef(t.oid)||t.tgenabled::text,chr(10) ORDER BY
            t.tgrelid::regclass::text,t.tgname),'UTF8')),'hex') FROM pg_trigger t WHERE NOT t.tgisinternal"""
    assert psql(triggers,SOURCE)==psql(triggers,DB)
    original_store = inventory(Path("/dev/shm/sys-u48-payslip-final/data/filestore") / SOURCE)
    current_store = inventory(WORK / "data/filestore" / DB)
    assert original_store == current_store and len(current_store) == 2708
    assert psql("SELECT count(*) FROM ir_module_module WHERE state='installed'", DB) == "193"
    assert psql("SELECT latest_version FROM ir_module_module WHERE name='step_payroll_oca_sys_history'", DB) == "18.0.1.6.3"
    return {"tables":len(before["public_tables"]),"metadata_changes":changed,"catalogue":final["catalogue"],
            "changed_functions":names,"all_trigger_definitions_and_enablement_identical":True,
            "unchanged_physical_files":len(current_store),"installed_modules":193,"payroll_history_version":"18.0.1.6.3",
            "advanced_sequences":sum(v!=before["sequence_values"][k] for k,v in after["sequence_values"].items())}


if __name__=="__main__":
    result={"workflow":failures(),"preservation":storage()}
    (WORK/"protection.json").write_text(json.dumps(result,sort_keys=True))
    print("Rollback, direct-write denials and original database protection verified")
