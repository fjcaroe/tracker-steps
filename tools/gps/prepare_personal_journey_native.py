"""Odoo shell: archive confirmed old QA cars and connect existing Tracker mirrors."""
import json,os
from pathlib import Path
plan=json.loads(Path(os.environ['JOURNEY_PLAN']).read_text());ids=json.loads(Path(os.environ['JOURNEY_IDS']).read_text())
assert env.cr.dbname=='LAB_TAREAS' or env.cr.dbname.startswith('PERSONAL_JOURNEY_NATIVE_QA_')
ctx={'mail_create_nosubscribe':True,'tracking_disable':True,'mail_notify_force_send':False,'allowed_company_ids':[plan['company_id']]}
Vehicle=env['fleet.vehicle'].with_context(**ctx,active_test=False)
vehicle=Vehicle.browse(plan['vehicle_id']);assert vehicle.exists() and vehicle.company_id.id==plan['company_id'] and vehicle.license_plate==plan['plate'] and vehicle.active
link=env['step.tracker.asset.link'].browse(plan['link_id']);assert link.asset_id==plan['asset_id'] and link.vehicle_id==vehicle and link.active
old=Vehicle.browse(plan['retire_vehicle_ids']);assert len(old.exists())==len(old) and all(v.company_id.id==plan['company_id'] for v in old) and vehicle not in old
before={v.id:(v.odometer,[(r.id,r.value,str(r.date)) for r in env['fleet.vehicle.odometer'].search([('vehicle_id','=',v.id)])]) for v in old|vehicle}
old.write({'active':False})
employee=env['hr.employee'].browse(plan['employee_id']);assert employee.user_id.id==plan['user_id'] and employee.company_id==vehicle.company_id
account=env['account.analytic.account'].browse(plan['analytic_id']);assert account.company_id==vehicle.company_id
values={'driver_id':employee.work_contact_id.id,'seats':plan['passenger_capacity']+1}
for field in ('cost_id','analytic_id'):
 if field in vehicle._fields:values[field]=account.id
if 'step_max_pass' in vehicle._fields:values['step_max_pass']=plan['passenger_capacity']
vehicle.write(values)
def upsert(model,tracker_id,values):
 Model=env[model].with_context(**ctx,active_test=False);row=Model.search([('tracker_id','=',tracker_id),('company_id','=',plan['company_id'])]);assert len(row)<=1
 values=dict(values,tracker_id=tracker_id,company_id=plan['company_id'])
 if row and model=='step.tracker.machine':assert not row.vehicle_id or row.vehicle_id==vehicle,'Do not reuse an old machine identity'
 if row and model=='step.tracker.driver':assert not row.employee_id or row.employee_id==employee,'Do not reuse another driver identity'
 if row:row.write(values)
 else:row=Model.create(values)
 return row
if 'step.tracker.machine' in env:
 others=env['step.tracker.machine'].with_context(**ctx,active_test=False).search([('company_id','=',plan['company_id']),('tracker_id','!=',ids['machine_id'])]);others.write({'active':False})
 machine=upsert('step.tracker.machine',ids['machine_id'],dict(name=plan['machine_name'],plate=plan['plate'],external_id=plan['machine_external_id'],vehicle_id=vehicle.id,active=True))
 driver=upsert('step.tracker.driver',ids['driver_id'],dict(name=plan['driver_name'],employee_id=employee.id,active=True))
 # Native field mirrors are not fabricated: the analytic account relationship is
 # retained in the private plan and external ID, not represented as a fake field.
 assert machine.vehicle_id==vehicle and driver.employee_id==employee
for v in old|vehicle:
 assert (v.odometer,[(r.id,r.value,str(r.date)) for r in env['fleet.vehicle.odometer'].search([('vehicle_id','=',v.id)])])==before[v.id]
assert Vehicle.search([('active','=',True),('company_id','=',plan['company_id'])]).ids==vehicle.ids
env.cr.commit();print('PERSONAL_JOURNEY_NATIVE_READY archived='+str(len(old))+' historic_readings_preserved=True')
