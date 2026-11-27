"""Compare the real market and receiver directories for the native Cerro operator in every company."""
import hashlib
import json

from odoo.exceptions import AccessError, ValidationError


FIELDS = ('step_export', 'step_export_receiver', 'step_export_market_id', 'step_export_generic_receiver',
          'step_export_carrier', 'step_export_consignee','step_export_notify','step_export_customs_agent',
          'step_export_forwarder','step_export_default_notify_id','step_export_default_consignee_id')


def digest(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def capture(env):
    actor = env['res.users'].browse(6)
    partners = env['res.partner'].with_user(actor)
    markets = env['step.fruit.market'].with_user(actor)
    assert not partners.env.su and env.ref('base.view_partner_tree').id == 123
    assert env.ref('studio_customization.odoo_studio_res_part_47b48baf-5b77-4192-857b-fed73051f3c7').id == 5192
    result = {}
    partitions = [[n] for n in actor.company_ids.ids] + [actor.company_ids.ids]
    for companies in partitions:
        contacts = partners.with_context(allowed_company_ids=companies)
        entries = contacts.search([], order='id')
        readings = entries.read(FIELDS,load=None)
        master = markets.with_context(allowed_company_ids=companies).search([],order='id')
        result[','.join(map(str,companies))] = {
            'partners':len(readings), 'roles_and_relations':digest(readings),
            'markets':len(master),'market_values':digest(master.read(['code','name','abbreviation','active'],load=None)),
        }
    return result


def exercise(env):
    actor = env['res.users'].browse(6)
    ctx = dict(allowed_company_ids=actor.company_ids.ids)
    partners = env['res.partner'].with_user(actor).with_context(**ctx)
    markets = env['step.fruit.market'].with_user(actor).with_context(**ctx)
    assert not partners.env.su and markets.search_count([])==4
    assert env.ref('step_producer_daily_estimate.market_read').id==2220
    assert env.ref('step_producer_daily_estimate.market_manage').id==2221
    try:
        markets.with_user(env.ref('base.public_user')).check_access('read')
    except AccessError:
        pass
    else:
        raise AssertionError('Public access to the market catalogue changed')
    market = markets.search([],limit=1)
    fixture = partners.create({'name':'Prueba privada directorio exportación','step_export_notify':True})
    assert fixture.step_export
    target = partners.create({'name':'Prueba privada roles de exportación'})
    for invalid in [{'step_export_generic_receiver':True},{'step_export_default_consignee_id':fixture.id}]:
        try:
            with env.cr.savepoint():
                target.write(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError('Invalid native receiver role was accepted')
    target.write({'step_export_market_id':market.id,'step_export_generic_receiver':True,
                  'step_export_default_notify_id':fixture.id,'step_export_forwarder':True})
    assert target.step_export and target.step_export_default_notify_id==fixture and target.step_export_market_id==market
    env.cr.rollback()
    env.invalidate_all(flush=False)
