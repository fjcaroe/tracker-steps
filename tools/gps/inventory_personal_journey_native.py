"""Odoo shell, private factual inventory only. No native writes or login secrets."""
import json,os
from pathlib import Path
assert env.cr.dbname=='LAB_TAREAS' or env.cr.dbname.startswith('PERSONAL_JOURNEY_NATIVE_QA_')
facts=json.loads(Path(os.environ['PERSONAL_FACTS']).read_text())
link=env['step.tracker.asset.link'].with_context(active_test=False).search([('asset_id','=',facts['asset_id'])]);assert len(link)==1
company=link.company_id;vehicle=link.vehicle_id;user=env['res.users'].browse(facts['source_user_id'])
output={'company_id':company.id,'user_id':user.id,'partner_id':user.partner_id.id,'user_name':user.name,'asset_id':link.asset_id,'link_id':link.id,'vehicle_id':vehicle.id,'plate':vehicle.license_plate,'odometer':vehicle.odometer,'unit':vehicle.odometer_unit}
for model,fields,domain in [
 ('fleet.vehicle',['name','license_plate','active','company_id','model_id','driver_id','seats','odometer','odometer_unit'],[('company_id','=',company.id)]),
 ('step.tracker.asset.link',['asset_id','active','vehicle_id','company_id'],[('company_id','=',company.id)]),
 ('account.analytic.account',['name','code','company_id'],[('company_id','in',[False,company.id])]),
 ('hr.employee',['name','user_id','company_id','work_contact_id'],[('user_id','=',user.id)]),
]:
 fields=[f for f in fields if f in env[model]._fields]
 output[model]=env[model].with_context(active_test=False).search(domain).read(fields)
Path(os.environ['PERSONAL_RESULT']).write_text(json.dumps(output,default=str,ensure_ascii=False,indent=2));print('PERSONAL_JOURNEY_NATIVE_INVENTORY_OK');env.cr.rollback()
