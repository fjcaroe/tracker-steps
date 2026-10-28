"""Read actual private configuration as a normal manager; never export formula bodies."""
import json
from pathlib import Path
import re
from odoo import api, Command


def inspect(env,output):
    assert re.fullmatch('(COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+',env.cr.dbname)
    path=Path(output);assert str(path.resolve()).startswith('/opt/steps-validation/')
    company=env.company
    actor=env['res.users'].with_context(no_reset_password=True).create({'name':'Private configuration inspector',
        'login':'private-payroll-configuration-inspector','company_id':company.id,
        'company_ids':[Command.set(company.ids)],'groups_id':[Command.set([
            env.ref('base.group_user').id,env.ref('payroll.group_payroll_manager').id])]})
    scope=api.Environment(env.cr,actor.id,dict(env.context,allowed_company_ids=company.ids,active_test=False),su=False)
    reports=[s._step_configuration_report() for s in scope['hr.payroll.structure'].search([],order='id')]
    chile=scope.ref('l10n_cl_simpledigital_payroll.structure_chile')
    result={'database':env.cr.dbname,'normal_actor':not scope.su,'read_only_configuration':True,
            'chile_structure_id':chile.id,'reports':reports,'financial_certified':False,
            'writes_to_source':False,'fixtures_rolled_back':True}
    env.cr.rollback()
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
