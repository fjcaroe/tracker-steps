"""Black-box YTD observations on a private real payroll engine; fixtures roll back."""
import json
from pathlib import Path
import re


def exercise(env,output):
    from datetime import date
    from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
    assert re.fullmatch('MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+',env.cr.dbname)
    path=Path(output);assert str(path.resolve()).startswith('/opt/steps-validation/')
    class FixtureBase:
        @classmethod
        def setUpClass(cls):pass
    class Fixture(PayrollContractMixin,FixtureBase):
        payroll_group='payroll.group_payroll_manager'
    from unittest.mock import patch
    model=type(env['res.company']);original=model.create
    def ready(records,values):
        result=original(records,values);records.env.cr.flush();return result
    Fixture.env=env
    with patch.object(model,'create',ready):Fixture.setUpClass()
    case=Fixture()
    (case.structure.rule_ids-case.rule).unlink()
    case.structure.ytd_computation=True
    case.company.write({'ytd_reset_day':1,'ytd_reset_month':'1'})
    case.contract.date_start=date(2024,1,1)
    case.rule.amount_python_compute="result = inputs['PRIVATE_BONUS'].amount"
    def make(start,end,amount,closed=False):
        slip=case.slip(amount)
        slip.write({'date_from':date.fromisoformat(start),'date_to':date.fromisoformat(end)})
        slip.compute_sheet()
        if closed:slip.state='done'
        return slip
    previous=make('2025-12-01','2025-12-31',5,True)
    january=make('2026-01-01','2026-01-31',10,True)
    draft=make('2026-02-01','2026-02-28',20)
    february=make('2026-02-01','2026-02-28',30,True)
    current=make('2026-03-01','2026-03-31',40)
    result={'database':env.cr.dbname,'normal_actor':not case.scope.su,'synthetic_only':True,
        'writes_to_source':False,'fixtures_rolled_back':True,
        'observations':{name:{'total':slip.line_ids.total,'ytd':slip.line_ids.ytd,
            'api':slip._get_line_values(['LIQ'],['total','ytd'])['LIQ'][slip.id]} for name,slip in
            [('previous',previous),('january',january),('draft',draft),('february',february),('current',current)]}}
    result['extra']={}
    case.structure.ytd_computation=False;current.compute_sheet()
    result['extra']['disabled']=current.line_ids.ytd
    case.structure.ytd_computation=True
    case.company.ytd_reset_month='2';current.compute_sheet()
    result['extra']['february_reset']=current.line_ids.ytd
    case.company.ytd_reset_day=15;current.compute_sheet()
    result['extra']['february_15_reset']=current.line_ids.ytd
    case.company.write({'ytd_reset_day':1,'ytd_reset_month':'1'})
    future=make('2026-04-01','2026-04-30',50,True);current.compute_sheet()
    result['extra']['future_excluded']=current.line_ids.ytd
    overlapping=make('2026-02-15','2026-03-15',15,True);current.compute_sheet()
    result['extra']['overlapping']=current.line_ids.ytd
    spanning=make('2025-12-15','2026-01-15',7,True);current.compute_sheet()
    result['extra']['spanning_year']=current.line_ids.ytd
    same_period=make('2026-03-01','2026-03-31',9,True);current.compute_sheet()
    result['extra']['same_period']=current.line_ids.ytd
    credit=case.slip(11)
    credit.write({'date_from':date(2026,1,1),'date_to':date(2026,1,31),'credit_note':True})
    credit.compute_sheet();credit.state='done';current.compute_sheet()
    result['extra']['credit_note']=current.line_ids.ytd
    other=case.structure.copy({'name':'Private alternate YTD structure','code':'PRIVATE_OTHER_YTD'})
    from odoo import Command
    kind=case.scope['hr.payslip.input.type'].create({'name':'Private other input','code':'PRIVATE_BONUS','struct_ids':[Command.set(other.ids)]})
    alternate=case.slip(0);alternate.input_line_ids.unlink()
    alternate.write({'struct_id':other.id,'date_from':date(2026,2,1),'date_to':date(2026,2,28)})
    case.scope['hr.payslip.input'].create({'name':'Private other bonus','payslip_id':alternate.id,
        'contract_id':case.contract.id,'input_type_id':kind.id,'amount':60})
    alternate.compute_sheet();alternate.state='done';current.compute_sheet()
    result['extra']['other_structure']=current.line_ids.ytd
    result['field_metadata']={name:{key:getattr(case.scope[model]._fields[name],key) for key in ('type','store','compute','default') if key!='default'}
        for model,name in [('hr.payslip.line','ytd'),('hr.payslip','ytd_computation'),('hr.payroll.structure','ytd_computation')]}
    env.cr.rollback()
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
