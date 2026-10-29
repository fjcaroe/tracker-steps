"""Prepare private BASIC-only replay inputs from user-approved SyS data, read-only.

This exports one configured rule expression, not Enterprise source files. The
strict non-executing recognizer must accept it before a real-engine replay.
Never publish the output, which contains the expression and payroll amounts.
"""
import argparse
import configparser
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capsule',type=Path,required=True)
    p.add_argument('--documentary-proof',type=Path,required=True)
    p.add_argument('--basis-helper',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert all(str(path.resolve()).startswith('/opt/steps-validation/') for path in (a.capsule,a.documentary_proof,a.basis_helper,a.output))
    cfg=configparser.ConfigParser(interpolation=None);assert cfg.read('/etc/odoo18-sys.conf') and cfg['options']['db_name']=='SyS'
    capsule=json.loads(a.capsule.read_text());document=json.loads(a.documentary_proof.read_text())
    assert capsule['reference']=='sys_user_approved' and document['documentary_wage_observed']
    assert document['basic_matches_stored'] and document['net_matches_stored']
    assert document['capsule_sha256']==hashlib.sha256(a.capsule.read_bytes()).hexdigest()
    selected=capsule['selected_case'];rows=selected['concepts']['BASIC'];ids={row['salary_rule_id'] for row in rows}
    assert len(rows)==1 and len(ids)==1,'Component replay requires one original BASIC line'
    ident=int(next(iter(ids)))
    def query(sql):
        return subprocess.check_output(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
            'psql','-XAt','-v','ON_ERROR_STOP=1','-d','SyS','-c',sql],text=True).strip()
    assert query('SHOW default_transaction_read_only')=='on'
    state=query('SELECT state FROM hr_payslip WHERE id='+str(int(selected['id'])))
    assert state==selected['state'] and state in ('done','paid')
    components=json.loads(query("SELECT jsonb_build_object('id',id,'slip_id',slip_id,'salary_rule_id',salary_rule_id,'code',code,'amount',amount::text,'quantity',quantity::text,'rate',rate::text,'total',total::text,'write_date',write_date) FROM hr_payslip_line WHERE id="+str(int(rows[0]['id']))+' AND slip_id='+str(int(selected['id']))))
    assert components['salary_rule_id']==ident and components['code']=='BASIC'
    assert components['write_date']==rows[0]['write_date'],'Original BASIC line changed since the preserved capsule'
    from decimal import Decimal
    assert all(components[key] is not None and Decimal(components[key]).is_finite() for key in ('amount','quantity','rate','total'))
    assert Decimal(components['total'])==Decimal(selected['stored_totals']['BASIC'])
    rule=json.loads(query("SELECT jsonb_build_object('id',id,'code',code,'body',amount_python_compute,'write_date',write_date,'active',active,'amount_select',amount_select,'condition_select',condition_select) FROM hr_salary_rule WHERE id="+str(ident)))
    origin=next(row for row in capsule['essential_rule_origins'] if row['id']==ident)
    digest=hashlib.sha256(rule['body'].encode()).hexdigest()
    assert digest==origin['body_sha256'] and rule['code']=='BASIC' and rule['active']
    assert rule['amount_select']=='code' and rule['condition_select']=='none'
    spec=importlib.util.spec_from_file_location('basis',a.basis_helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    recognized=module.monthly_worked_day_basis(rule['body']);assert recognized,'Unverified original BASIC expression'
    result={'read_only_source':True,'orm_reads':False,'source_payroll_computed':False,'enterprise_source_files_copied':False,
        'contains_private_formula_and_payroll_data':True,'financial_certified':False,'master_timeline_certified':False,
        'auditor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'basis_helper_sha256':hashlib.sha256(a.basis_helper.read_bytes()).hexdigest(),
        'capsule_sha256':document['capsule_sha256'],'pdf_sha256':document['pdf_sha256'],
        'formula_sha256':digest,'formula':rule['body'],'basis':recognized,
        'rule_write_date_precedes_period':str(rule['write_date'])[:10]<selected['date_from'],
        'printed_contract_wage':document['printed_contract_wage'],
        'worked_days':selected['basis']['worked_days'],'expected_basic':selected['stored_totals']['BASIC'],
        'expected_components':components,'components_read_only_sql':True}
    a.output.write_text(json.dumps(result,indent=2));os.chmod(a.output,0o600)
    print(json.dumps({'read_only_source':True,'recognized':recognized,'financial_certified':False}))


if __name__=='__main__':main()
