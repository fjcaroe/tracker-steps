"""Execute with Odoo shell ONLY in a fresh, neutralized TRACKER_OPS_QA_* copy.

Exercises the existing native models used by the frontend. No new models,
permissions, schema or production data. All fixture writes are rolled back.
"""
import uuid
from unittest.mock import patch
from odoo.exceptions import AccessError, ValidationError

assert env.cr.dbname.startswith('TRACKER_OPS_QA_')
assert not env['ir.cron'].search_count([('active','=',True)])
company=env['res.company'].browse(2).exists();assert company
users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),('company_ids','in',company.ids)],order='id')
user=users.filtered(lambda u:u.has_group('base.group_system') and env['fleet.vehicle'].with_user(u).check_access_rights('create',raise_exception=False) and env['fleet.vehicle.model.brand'].with_user(u).check_access_rights('read',raise_exception=False))[:1];assert user
current=env(user=user.id,context={'allowed_company_ids':company.ids,'tracking_disable':True,'mail_create_nosubscribe':True,'no_reset_password':True})
try:
    brand=current['fleet.vehicle.model.brand'].search([],limit=1);assert brand
    model=current['fleet.vehicle.model'].create({'name':'Private operation copy test','brand_id':brand.id})
    vehicle=current['fleet.vehicle'].create({'model_id':model.id,'license_plate':'QA-OPS','company_id':company.id})
    Link=current['step.tracker.asset.link']
    asset=str(uuid.uuid4())
    with patch.object(type(Link),'_remote_asset',return_value={'name':'Private copy vehicle','plate':'QA-OPS'}):
        link=Link.create({'company_id':company.id,'asset_id':asset,'vehicle_id':vehicle.id})
    assert link.vehicle_id==vehicle and Link.search([('company_id','=',company.id),('asset_id','=',asset)]).id==link.id
    assert vehicle.tracker_asset_id==asset
    Odometer=current['fleet.vehicle.odometer']
    assert Odometer.check_access_rights('create',raise_exception=False)
    one=Odometer.create({'vehicle_id':vehicle.id,'date':'2026-10-31','value':10000})
    two=Odometer.create({'vehicle_id':vehicle.id,'date':'2026-11-01','value':10025.5})
    assert vehicle.odometer==10025.5 and one.unit==vehicle.odometer_unit
    logs=Odometer.search_read([('vehicle_id','=',vehicle.id)],['id','date','value','unit'],order='date desc,id desc')
    assert [r['id'] for r in logs]==[two.id,one.id]
    assert current['ir.ui.view'].search_count([('model','=','fleet.vehicle.odometer'),('type','=','form'),('active','=',True)])
    assert current['ir.ui.view'].search_count([('model','=','fleet.vehicle'),('type','=','form'),('active','=',True)])
    normal=current['res.users'].with_context(no_reset_password=True).create({'name':'Private copy reader','login':'copy-reader-'+uuid.uuid4().hex,'company_id':company.id,'company_ids':[(6,0,company.ids)],'groups_id':[(6,0,[env.ref('base.group_user').id])]})
    assert not Odometer.with_user(normal).check_access_rights('create',raise_exception=False)
    try:
        with env.cr.savepoint():
            Link.with_user(normal).create({'company_id':company.id,'asset_id':str(uuid.uuid4()),'vehicle_id':vehicle.id})
    except AccessError:pass
    else:raise AssertionError('Unprivileged link allowed')
    other=current['res.company'].sudo().search([('id','!=',company.id)],limit=1);assert other
    foreign=current['fleet.vehicle'].sudo().create({'model_id':model.id,'license_plate':'QA-OTHER','company_id':other.id})
    try:
        with env.cr.savepoint(),patch.object(type(Link),'_remote_asset',return_value={'name':'copy','plate':'copy'}):
            Link.create({'company_id':company.id,'asset_id':str(uuid.uuid4()),'vehicle_id':foreign.id})
    except (ValidationError,AccessError):pass
    else:raise AssertionError('Cross-company vehicle allowed')
    print('OPERATIONS_ODOO_COPY_OK native_link=True native_odometer=True readings_verified=True forms=True permissions=True company_isolation=True fixtures_rolled_back=True')
finally:
    env.cr.rollback()
