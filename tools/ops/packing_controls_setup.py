"""Company-scoped T122 plan configuration; never changes journals or memberships."""
import json
from pathlib import Path
import subprocess


def configure(base, options, database, source, opts, stage):
    script="import sys\nsys.path.insert(0,%r)\n"%str(Path(__file__).resolve().parent)
    script+='''
import json
from native_business_profile import scoped_business_environment
scoped=scoped_business_environment(env)
company=scoped.company
Plan=env['account.analytic.plan']
Rule=env['step.packing.analytic.rule'].with_company(company)
existing=Rule.search([('company_id','=',company.id)])
ot_plan=Plan.search([('parent_id','=',False),('name','=ilike','OT Packing')])
assert len(ot_plan)<=1,'Ambiguous OT Packing plans'
if not ot_plan and not existing:
    ot_plan=Plan.create({'name':'OT Packing','default_applicability':'optional'})
origins={'temporada':'season','centro de costos':'species','ot packing':'ot'}
for plan in Plan.search([('parent_id','=',False)]):
    if Rule.search_count([('company_id','=',company.id),('plan_id','=',plan.id)]):continue
    origin=origins.get(plan.name.strip().casefold()) if not existing else False
    Rule.create({'company_id':company.id,'plan_id':plan.id,'origin':origin,'apply':bool(origin)})
assert not env['res.groups'].search([('id','in',[env.ref('step_application_profiles.%s_%s'%(app,level)).id for app in ('packing','export','producers') for level in ('read','operation','manager')])]).users
env.cr.commit()
print('PACKING_CONTROLS_CONFIGURED '+json.dumps({'company':company.id,'plans':Rule.search_count([('company_id','=',company.id)]),'profiles':9,'memberships_changed':False}))
'''
    data=['--data-dir='+str(stage/'data')] if database.startswith('MANAGEMENT_QA_') else []
    result=subprocess.run(base+['shell']+options+data+['-d',database,'--addons-path='+str(source)+','+opts['addons_path'],'--log-level=error'],
                          input=script,text=True,capture_output=True)
    (stage/('controls-config-'+database+'.log')).write_text(result.stdout+result.stderr)
    assert result.returncode==0 and 'PACKING_CONTROLS_CONFIGURED ' in result.stdout,result.stderr[-3000:]
    print(next(line for line in result.stdout.splitlines() if line.startswith('PACKING_CONTROLS_CONFIGURED ')),flush=True)
