"""Run only through Odoo shell; private facts and receipts outside Git.
Modes: export Cerro facts, import into fresh Development copy/live, archive source.
No credentials or financial records are copied or changed. Existing target
access remains; source native-app groups can be mapped to the target user.
"""
import json,os
from pathlib import Path
from unittest.mock import patch
facts=Path(os.environ['PERSONAL_FACTS']);mode=os.environ['PERSONAL_MODE']
login=os.environ.get('PERSONAL_LOGIN')
ctx={'mail_create_nosubscribe':True,'tracking_disable':True,'mail_notify_force_send':False}
if mode=='export':
 assert env.cr.dbname=='CERRO_EL_PLOMO'
 user=env['res.users'].search([('login','=',login)]);assert len(user)==1
 asset=os.environ['PERSONAL_ASSET'];company=env['res.company'].browse(int(os.environ['PERSONAL_COMPANY']))
 link=env['step.tracker.asset.link'].search([('asset_id','=',asset),('company_id','=',company.id),('active','=',True)]);assert len(link)==1
 vehicle=link.vehicle_id
 assert not env['hr.expense'].search_count([('step_vehicle_id','=',vehicle.id)]),'Vehicle has expenses; requires financial migration'
 assert not vehicle.driver_id,'Existing driver relationship requires explicit migration'
 fields=['name','email','phone','mobile','lang','tz','image_1920'];profile=user.partner_id.read(fields)[0];profile.pop('id')
 if isinstance(profile.get('image_1920'),bytes):profile['image_1920']=profile['image_1920'].decode()
 groups=[x.module+'.'+x.name for x in env['ir.model.data'].search([('model','=','res.groups'),('res_id','in',user.groups_id.ids)]) if x.module in ('fleet','hr_expense','step_tracker_portal','step_management_costs')]
 value={'groups':groups,'source_user_id':user.id,'login':login,'profile':profile,'asset_id':asset,'source_company':company.id,'source_vehicle':vehicle.id,'source_link':link.id,'plate':vehicle.license_plate,'brand':vehicle.model_id.brand_id.name,'model':vehicle.model_id.name,'unit':vehicle.odometer_unit,'readings':[{'date':str(r.date),'value':r.value} for r in env['fleet.vehicle.odometer'].search([('vehicle_id','=',vehicle.id)],order='date,id')]}
 facts.write_text(json.dumps(value));facts.chmod(0o600);print('PERSONAL_NATIVE_EXPORTED')
else:
 data=json.loads(facts.read_text());qa=env.cr.dbname.startswith('PERSONAL_')
 if mode=='import':
  assert env.cr.dbname=='LAB_TAREAS' or qa
  user=env['res.users'].search([('login','=',data['login']),('active','=',True)]);assert len(user)==1 and user.has_group('base.group_system'),'Reuse existing authorized Development administrator'
  for xmlid in data.get('groups',[]):
   group=env.ref(xmlid,raise_if_not_found=False)
   if group and group not in user.groups_id:user.with_context(**ctx).write({'groups_id':[(4,group.id)]})
  company=user.company_id;assert company.id in user.company_ids.ids
  models=env['fleet.vehicle.model'].with_context(**ctx);brands=env['fleet.vehicle.model.brand']
  brand=brands.search([('name','=',data['brand'])]);assert len(brand)==1,'Reuse an unambiguous existing brand'
  model=models.search([('brand_id','=',brand.id),('name','=',data['model'])]);assert len(model)<=1
  if not model:model=models.create({'name':data['model'],'brand_id':brand.id})
  vehicles=env['fleet.vehicle'].with_context(**ctx,active_test=False)
  vehicle=vehicles.search([('company_id','=',company.id),('license_plate','=',data['plate'])]);assert len(vehicle)<=1
  if not vehicle:vehicle=vehicles.create({'company_id':company.id,'license_plate':data['plate'],'model_id':model.id,'odometer_unit':data['unit']})
  assert vehicle.model_id==model and vehicle.odometer_unit==data['unit'] and vehicle.active
  for r in data['readings']:
   rows=env['fleet.vehicle.odometer'].search([('vehicle_id','=',vehicle.id),('date','=',r['date']),('value','=',r['value'])]);assert len(rows)<=1
   if not rows:env['fleet.vehicle.odometer'].with_context(**ctx).create(dict(r,vehicle_id=vehicle.id))
  Link=env['step.tracker.asset.link'].with_user(user).with_context(**ctx,allowed_company_ids=[company.id])
  def associate():
   link=Link.with_context(active_test=False).search([('company_id','=',company.id),('asset_id','=',data['asset_id'])]);assert len(link)<=1
   if not link:link=Link.create({'company_id':company.id,'asset_id':data['asset_id'],'vehicle_id':vehicle.id,'note':'Traslado personal autorizado desde producción; GPS e historial conservados.'})
   assert link.active and link.vehicle_id.id==vehicle.id
   return link
  if qa:
   # Only a neutralized private copy; no outgoing bridge to a production tenant.
   with patch.object(type(Link),'_remote_asset',lambda self,c,a:{'asset_id':a,'name':'Personal migration fixture','plate':data['plate'],'source_id':'manual:migrated'}):link=associate()
  else:link=associate()
  profile=dict(data['profile']);user.partner_id.with_context(**ctx).write(profile)
  result={'user_id':user.id,'company_id':company.id,'vehicle_id':vehicle.id,'link_id':link.id,'asset_id':link.asset_id,'odometer':vehicle.odometer,'readings':len(data['readings']),'credentials_unchanged':True,'existing_user_reused':True}
  Path(os.environ['PERSONAL_RESULT']).write_text(json.dumps(result));env.cr.commit();print('PERSONAL_NATIVE_IMPORTED')
 elif mode=='archive':
  assert env.cr.dbname=='CERRO_EL_PLOMO' or qa
  vehicle=env['fleet.vehicle'].with_context(active_test=False).browse(data['source_vehicle']);link=env['step.tracker.asset.link'].with_context(active_test=False).browse(data['source_link'])
  assert vehicle.license_plate==data['plate'] and link.asset_id==data['asset_id']
  assert not env['hr.expense'].search_count([('step_vehicle_id','=',vehicle.id)])
  link.with_context(**ctx).write({'active':False});vehicle.with_context(**ctx).write({'active':False});env.cr.commit();print('PERSONAL_SOURCE_ARCHIVED')
 else:raise ValueError('Unknown migration mode')
