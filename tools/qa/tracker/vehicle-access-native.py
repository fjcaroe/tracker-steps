"""Native rules/form rehearsal (rollback), or explicit existing-user provisioning."""
import json, os
from pathlib import Path
from odoo import Command
from odoo.exceptions import AccessError
from lxml import etree

mode = os.environ['TRACKER_ACCESS_MODE']
facts = json.loads(Path(os.environ['TRACKER_ACCESS_FACTS']).read_text())
company = env['res.company'].browse(facts['company_id']).exists()
vehicle = env['fleet.vehicle'].browse(facts['vehicle_id']).exists()
if mode == 'qa' and facts.get('fixture'):
    assert env.cr.dbname.startswith('TRACKER_ACCESS_QA_')
    model = env['fleet.vehicle.model'].search([], limit=1)
    if not model:
        brand = env['fleet.vehicle.model.brand'].create({'name': 'QA scope fixture'})
        model = env['fleet.vehicle.model'].create({'name': 'QA scope fixture', 'brand_id': brand.id})
    vehicle = env['fleet.vehicle'].create(dict(model_id=model.id, company_id=company.id, license_plate='QA-OWN'))
    env['step.tracker.asset.link'].with_context(step_tracker_skip_remote=True).create(dict(
        company_id=company.id, vehicle_id=vehicle.id, asset_id=facts['asset_id']))
assert company and vehicle.company_id == company
group = env.ref('step_tracker_vehicle_access.group_vehicle_operator')
ctx = dict(no_reset_password=True, tracking_disable=True, mail_create_nosubscribe=True,
           mail_notrack=True, allowed_company_ids=company.ids)


def configure(login, name, password=None, existing=False):
    users = env['res.users'].with_context(**ctx)
    user = users.with_context(active_test=False).search([('login', '=', login)])
    assert len(user) <= 1
    if existing:
        assert user and user.active and not user.share
        assert company in user.company_ids
    values = dict(tracker_restricted=True, tracker_vehicle_ids=[Command.set(vehicle.ids)])
    if not user:
        assert password
        user = users.create(dict(name=name, login=login, password=password, company_id=company.id,
            company_ids=[Command.set(company.ids)], groups_id=[Command.set(group.ids)], **values))
    else:
        # Never reset an existing password or replace unrelated business groups.
        user.write(dict(groups_id=[Command.link(group.id)], **values))
    return user


if mode == 'configure':
    assert env.cr.dbname in ('CERRO_EL_PLOMO', 'LAB_TAREAS')
    if facts.get('existing_login'):
        actual = configure(facts['existing_login'], '', existing=True)
    else:
        actual = None
    preview = configure(facts['preview_login'], facts['preview_name'], facts['preview_password'])
    access = preview._tracker_portal_access(company)
    assert access['asset_ids'] == [facts['asset_id']] and access['role'] == 'operator' and access['manage_protection']
    if actual:
        assert actual._tracker_portal_access(company) == access
    Path(os.environ['TRACKER_ACCESS_RESULT']).write_text(json.dumps(dict(
        preview_user_id=preview.id, actual_user_id=actual.id if actual else None,
        company_id=company.id, asset_ids=access['asset_ids'])))
    env.cr.commit()
    print('TRACKER_ACCESS_CONFIGURED')
elif mode == 'qa':
    assert env.cr.dbname.startswith('TRACKER_ACCESS_QA_')
    limited = configure('qa.tracker.assigned', 'QA assigned operator', 'qa-copy-only')
    link = env['step.tracker.asset.link'].sudo().search([
        ('company_id', '=', company.id), ('vehicle_id', '=', vehicle.id), ('active', '=', True)])
    assert len(link) == 1 and link.asset_id == facts['asset_id']
    hidden = env['fleet.vehicle'].with_context(**ctx).create(dict(model_id=vehicle.model_id.id,
        company_id=company.id, license_plate='QA-HIDDEN'))
    hidden_link = env['step.tracker.asset.link'].with_context(**ctx, step_tracker_skip_remote=True).create(dict(
        company_id=company.id, vehicle_id=hidden.id, asset_id='00000000-0000-0000-0000-000000000042'))
    access = limited._tracker_portal_access(company)
    assert access['asset_ids'] == [facts['asset_id']] and access['role'] == 'operator' and access['manage_protection']
    assert env['fleet.vehicle'].with_user(limited).with_context(**ctx).search([]).ids == vehicle.ids
    assert env['step.tracker.asset.link'].with_user(limited).with_context(**ctx).search([]).ids == link.ids
    try:
        hidden.with_user(limited).with_context(**ctx).read(['license_plate'])
        raise AssertionError('Guessed Fleet ID was readable')
    except AccessError:
        pass
    try:
        limited.with_user(limited).write({'tracker_restricted': False})
        raise AssertionError('Scope escalation succeeded')
    except AccessError:
        pass
    limited.write({'tracker_vehicle_ids': [Command.clear()]})
    assert limited._tracker_portal_access(company)['asset_ids'] == []
    assert not env['fleet.vehicle'].with_user(limited).with_context(**ctx).search([])
    limited.write({'tracker_vehicle_ids': [Command.set(vehicle.ids)]})
    arch = env['res.users'].get_view(env.ref('base.view_users_form').id, 'form')['arch']
    assert etree.fromstring(arch.encode()).xpath('//field[@name="tracker_vehicle_ids"]')
    assert env.ref('step_tracker_portal.menu_fleet').action.url.endswith('#live')
    assert not env.user._tracker_is_limited()
    env.cr.rollback()
    print('TRACKER_ACCESS_NATIVE_QA_OK scope=True denied_ids=True revocation=True form=True menu=True')
else:
    raise AssertionError('Unknown access operation')
