"""Odoo shell: native real-vehicle fields and explicit existing GPS link.
Facts/results stay private. QA patches only the remote lookup for its own copy.
"""
import html,json,os,re
from pathlib import Path
from unittest.mock import patch
facts=json.loads(Path(os.environ['INSTALLATION_FACTS']).read_text());qa=env.cr.dbname.startswith('INSTALLATION_NATIVE_QA_');assert qa or env.cr.dbname=='CERRO_EL_PLOMO'
norm=lambda value:re.sub('[^A-Z0-9]','',(value or '').upper())
company=env['res.company'].browse(facts['company_id']);assert norm(company.vat).endswith(norm(facts['company_vat']))
ctx=dict(allowed_company_ids=company.ids,mail_create_nosubscribe=True,tracking_disable=True,mail_notrack=True,mail_notify_force_send=False)
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
if new:assert not env['fleet.vehicle.odometer'].search_count([('vehicle_id','=',vehicle.id)]),'No physical odometer reading was supplied'
result=dict(vehicle_id=vehicle.id,model_id=model.id,brand_id=brand.id,link_id=link.id,asset_id=link.asset_id,company_id=company.id,native_fields_verified=True,new_vehicle=new,odometer_not_invented=True)
Path(os.environ['INSTALLATION_RESULT']).write_text(json.dumps(result));env.cr.commit();print('INSTALLATION_NATIVE_VEHICLE_OK qa='+str(qa))
