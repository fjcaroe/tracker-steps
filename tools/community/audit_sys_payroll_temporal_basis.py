"""Read-only temporal provenance metadata for the approved private SyS capsule.

No salary, employee identifier or formula is exported. A tracking event or an
early write_date alone never certifies the wage actually used by a closed slip.
"""
import argparse
import configparser
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capsule',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert all(str(path.resolve()).startswith('/opt/steps-validation/') for path in (a.capsule,a.output))
    capsule=json.loads(a.capsule.read_text())
    assert capsule['reference']=='sys_user_approved' and capsule['read_only']
    cfg=configparser.ConfigParser(interpolation=None)
    assert cfg.read('/etc/odoo18-sys.conf') and cfg['options']['db_name']=='SyS'
    def query(sql):
        return subprocess.check_output(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
            'psql','-XAt','-v','ON_ERROR_STOP=1','-d','SyS','-c',sql],text=True).strip()
    assert query('SHOW default_transaction_read_only')=='on'
    case=capsule['selected_case'];ident=int(case['basis']['contract_id']);slip=int(case['id'])
    # Recheck identity and period only; never load an ORM computed wage property.
    actual=json.loads(query("SELECT jsonb_build_object('state',state,'date_from',date_from,'date_to',date_to,'contract_id',contract_id) FROM hr_payslip WHERE id="+str(slip)))
    assert all(actual[key]==case[key] for key in ('state','date_from','date_to'))
    assert actual['contract_id']==ident and actual['state'] in ('done','paid')
    current=query('SELECT write_date::date FROM hr_contract WHERE id='+str(ident))
    events=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('field',f.name,'date',m.date) ORDER BY m.date,t.id),'[]'::jsonb) FROM mail_tracking_value t JOIN mail_message m ON m.id=t.mail_message_id JOIN ir_model_fields f ON f.id=t.field_id WHERE m.model='hr.contract' AND m.res_id="+str(ident)+" AND f.model='hr.contract' AND f.name IN ('wage','hourly_wage','wage_type','schedule_pay')"))
    period=date.fromisoformat(case['date_to'])
    counts={name:sum(row['field']==name for row in events) for name in ('wage','hourly_wage','wage_type','schedule_pay')}
    result={'read_only':True,'orm_reads':False,'payroll_computed':False,'financial_certified':False,
        'historical_wage_proven':False,'private_payroll_amounts_exported':False,
        'direct_employee_identifiers_exported':False,'formula_bodies_exported':False,
        'capsule_sha256':hashlib.sha256(a.capsule.read_bytes()).hexdigest(),
        'auditor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'selected_period':case['date_to'][:7],
        'current_contract_modified_after_period':date.fromisoformat(current)>period,
        'contract_history_relation_kind':query("SELECT relkind FROM pg_class WHERE oid=to_regclass('hr_contract_history')"),
        'tracking_event_counts':counts,
        'tracking_events_after_period':sum(date.fromisoformat(str(row['date'])[:10])>period for row in events),
        'absence_of_tracking_proves_no_change':False,
        'history_relation_is_an_immutable_snapshot':False}
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
