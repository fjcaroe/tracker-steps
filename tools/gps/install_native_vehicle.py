"""Odoo shell: native real-vehicle fields and explicit existing GPS link.
Facts/results stay private. QA patches only the remote lookup for its own copy.
"""
import html,json,os,re
from pathlib import Path
from unittest.mock import patch
facts=json.loads(Path(os.environ['INSTALLATION_FACTS']).read_text());qa=env.cr.dbname.startswith('INSTALLATION_NATIVE_QA_');assert qa or env.cr.dbname=='CERRO_EL_PLOMO'
norm=lambda value:re.sub('[^A-Z0-9]','',(value or '').upper())
company=env['res.company'].browse(facts['company_id']);assert norm(company.vat).endswith(norm(facts['company_vat']))
ctx=dict(allowed_company_ids=company.ids,mail_create_nosubscribe=True,tracking_disable=True,mail_notrack=True,mail_notify_force_send=False,mail_notify_noemail=True,mail_auto_subscribe_no_notify=True,no_reset_password=True)
driver=None
if facts.get('driver_login'):
 driver=env['res.users'].with_context(**ctx).search([('login','=',facts['driver_login']),('active','=',True),('share','=',False)])
 assert len(driver)==1 and driver.id==facts['driver_user_id'] and company in driver.company_ids,'Driver identity or company differs'
Brands=env['fleet.vehicle.model.brand'].with_context(**ctx,active_test=False)
brands=Brands.search([]).filtered(lambda b:norm(b.name)==norm(facts['brand']));assert len(brands)<=1
brand=brands or Brands.create({'name':facts['brand']})
Models=env['fleet.vehicle.model'].with_context(**ctx,active_test=False)
models=Models.search([('brand_id','=',brand.id)]).filtered(lambda m:norm(m.name)==norm(facts['model']));assert len(models)<=1
model=models or Models.create({'name':facts['model'],'brand_id':brand.id})
Vehicle=env['fleet.vehicle'].with_context(**ctx,active_test=False)
vehicles=Vehicle.search([]).filtered(lambda v:norm(v.license_plate)==facts['plate'] or (v.vin_sn and norm(v.vin_sn)==facts['vin']));assert len(vehicles)<=1
assert not vehicles or vehicles.company_id==company,'Existing vehicle belongs to another legal company; do not move it silently'
assert not vehicles or not vehicles.vin_sn or norm(vehicles.vin_sn)==facts['vin'],'VIN differs; review the existing native record'
notes='<p>Datos proporcionados por el usuario durante la instalación del GPS.</p><ul>'+''.join('<li>'+html.escape(label)+': '+html.escape(facts[key])+'</li>' for label,key in [('Tipo','vehicle_class'),('Número de motor','engine_number'),('Procedencia','origin'),('Fabricante','manufacturer'),('Dígito verificador de patente','registration_check_digit')])+'</ul>'
values=dict(model_id=model.id,company_id=company.id,license_plate=facts['plate'],model_year=facts['year'],color=facts['color'],vin_sn=facts['vin'])
if driver:
 assert not vehicles or not vehicles.driver_id or vehicles.driver_id==driver.partner_id,'Existing native driver differs; do not replace silently'
 values['driver_id']=driver.partner_id.id
new=not bool(vehicles)
if new:
 values['description']=notes;vehicle=Vehicle.create(values)
else:
 vehicle=vehicles;vehicle.write(values)
 if facts['engine_number'] not in (vehicle.description or ''):vehicle.write({'description':(vehicle.description or '')+notes})
Link=env['step.tracker.asset.link'].with_context(**ctx,active_test=False)
existing=Link.search([('company_id','=',company.id),('asset_id','=',facts['asset_id'])]);assert len(existing)<=1
def associate():
 if existing:
  assert existing.vehicle_id==vehicle and existing.active;return existing
 return Link.create(dict(company_id=company.id,asset_id=facts['asset_id'],vehicle_id=vehicle.id,note='Asociación de GPS y vehículo real confirmada por el usuario durante la instalación. Sin lectura física inicial informada.'))
if qa:
 with patch.object(type(Link),'_remote_asset',lambda self,c,a:dict(asset_id=a,name=facts['plate'],plate=facts['plate'],source_id='manual:validated-installation')):link=associate()
else:link=associate()
assert vehicle.tracker_asset_id==facts['asset_id'] and vehicle.vin_sn==facts['vin'] and vehicle.model_year==facts['year'] and vehicle.color==facts['color']
if facts.get('configure_user'):
 assert driver and 'tracker_vehicle_ids' in driver._fields
 def profiles():
  return {u.id:(u.tracker_restricted,u.tracker_starter_control,u.tracker_control_preview,tuple(sorted(u.tracker_vehicle_ids.ids)),tuple(sorted(u.groups_id.ids)),u.company_id.id,tuple(sorted(u.company_ids.ids))) for u in env['res.users'].with_context(active_test=False).search([('id','!=',driver.id)])}
 others=profiles();old_groups=set(driver.groups_id.ids)
 driver.with_context(**ctx).write(dict(tracker_restricted=True,tracker_vehicle_ids=[(6,0,vehicle.ids)],tracker_starter_control=True,tracker_control_preview=False,groups_id=[(4,env.ref('step_tracker_vehicle_access.group_vehicle_operator').id)],action_id=env.ref('step_tracker_portal.action_home').id))
 access=driver._tracker_portal_access(company)
 assert access['asset_ids']==[facts['asset_id']] and access['role']=='operator' and access['manage_protection'] and access['starter_control'] and not access['control_preview']
 assert old_groups<=set(driver.groups_id.ids) and profiles()==others,'Unrelated permissions changed'
 assert env['fleet.vehicle'].with_user(driver).with_context(**ctx).search([]).ids==vehicle.ids
 assert env['step.tracker.asset.link'].with_user(driver).with_context(**ctx).search([]).ids==link.ids
 assert vehicle.driver_id==driver.partner_id
if new:assert not env['fleet.vehicle.odometer'].search_count([('vehicle_id','=',vehicle.id)]),'No physical odometer reading was supplied'
result=dict(vehicle_id=vehicle.id,model_id=model.id,brand_id=brand.id,link_id=link.id,asset_id=link.asset_id,company_id=company.id,native_fields_verified=True,new_vehicle=new,odometer_not_invented=True)
if driver:result.update(driver_user_id=driver.id,driver_partner_id=driver.partner_id.id,user_scope_verified=bool(facts.get('configure_user')))
Path(os.environ['INSTALLATION_RESULT']).write_text(json.dumps(result));env.cr.commit();env.registry.signal_changes();print('INSTALLATION_NATIVE_VEHICLE_OK qa='+str(qa))
