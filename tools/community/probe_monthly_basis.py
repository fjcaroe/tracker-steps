"""BASIC-only real-engine draft replay with preserved documentary wage/worked rows."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


def exercise(case,inputs,output):
    from odoo.tests import TransactionCase
    from odoo.addons.step_payroll_contracts.basis import monthly_worked_day_basis
    from odoo.addons.step_payroll_contracts.history import stored_payslip_line_components
    assert isinstance(case,TransactionCase),'Run only inside the Odoo transactional test framework'
    env=case.env
    assert re.fullmatch('(COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+',env.cr.dbname)
    path=Path(output);assert str(path.resolve()).startswith('/opt/steps-validation/')
    assert inputs['read_only_source'] and not inputs['source_payroll_computed']
    assert hashlib.sha256(inputs['formula'].encode()).hexdigest()==inputs['formula_sha256']
    assert monthly_worked_day_basis(inputs['formula'])==inputs['basis']
    (case.structure.rule_ids-case.rule).unlink()
    case.chile_rounding_structure()
    case.contract.wage=float(Decimal(inputs['printed_contract_wage']))
    case.rule.write({'code':'BASIC','amount_python_compute':inputs['formula']})
    slip=case.slip();slip.input_line_ids.unlink();slip.worked_days_line_ids.unlink()
    mappings=[]
    for row in inputs['worked_days']:
        kind=case.scope['hr.work.entry.type'].search([('code','=',row['code'])])
        assert len(kind)==1,'Require existing unambiguous worked-day master; do not invent it'
        case.scope['hr.payslip.worked_days'].create({'name':'Private observed worked-day snapshot','payslip_id':slip.id,
            'contract_id':case.contract.id,'work_entry_type_id':kind.id,
            'number_of_days':float(Decimal(row['days'])),'number_of_hours':float(Decimal(row['hours']))})
        mappings.append({'source_id':row['type_id'],'target_id':kind.id,'code':row['code']})
    slip.compute_sheet();env.flush_all()
    env.cr.execute("SELECT total::text FROM hr_payslip_line WHERE slip_id=%s AND code='BASIC'",(slip.id,))
    rows=env.cr.fetchall();assert len(rows)==1
    assert Decimal(rows[0][0])==Decimal(inputs['expected_basic']),'Original BASIC snapshot differs from new draft'
    components=stored_payslip_line_components(slip,'BASIC')
    assert len(components)==1 and components[0]['salary_rule_id']==case.rule.id
    matched={key:Decimal(str(components[0][key]))==Decimal(inputs['expected_components'][key]) for key in ('amount','quantity','rate','total')}
    assert all(matched.values()),'Original BASIC components differ from the new draft'
    result={'database':env.cr.dbname,'normal_actor':not case.scope.su,'real_engine':True,'new_fixture_only':True,
        'transaction_case':True,'fixtures_rolled_back':False,'source_payroll_computed':False,'source_written':False,
        'basic_matches_original_snapshot':True,'financial_certified':False,'master_timeline_certified':False,
        'full_payroll_replay':False,'identity_conversion':False,'worked_day_master_mapping':mappings,
        'component_matches':matched,'stored_component_reader':True,
        'capsule_sha256':inputs['capsule_sha256'],'pdf_sha256':inputs['pdf_sha256'],'formula_sha256':inputs['formula_sha256'],
        'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    path.write_text(json.dumps(result,indent=2))
