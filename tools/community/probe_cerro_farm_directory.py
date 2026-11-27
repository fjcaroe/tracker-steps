"""Exercise the original producer/farm inverse, aliases and cross-company contact search as the inventory user."""
import hashlib
import json

from odoo.exceptions import AccessError

from probe_cerro_shared_farms import capture as farm_snapshot


def capture(env):
    farm_snapshot(env)
    rule = env.ref('step_producers.rule_step_producer_fundo_company')
    field = env.ref('step_producers.field_res_partner__step_export_fundo_ids')
    delegated = env.ref('step_producers.field_res_users__step_export_fundo_ids')
    assert (field.id, delegated.id, rule.id) == (26219, 26726, 543)
    assert field == env.ref('step_export.field_res_partner__step_export_fundo_ids')
    assert (field.model, field.relation, field.relation_field) == ('res.partner', 'step.fundo', 'partner_id')
    assert delegated.related == 'partner_id.step_export_fundo_ids'
    assert rule.groups == env.ref('base.group_user') and rule.active
    assert all((rule.perm_read, rule.perm_create, rule.perm_write, rule.perm_unlink))
    actor = env['res.users'].browse(6)
    contacts = env['res.partner'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids)
    assert not contacts.env.su and contacts.env.user.has_group('stock.group_stock_user')
    partitions = {}
    for company in actor.company_ids:
        # Switching company in the client creates a new request with an empty record cache.
        env.invalidate_all()
        scoped = contacts.with_context(allowed_company_ids=[company.id])
        rows = scoped.search([('is_productor', '=', True)], order='id').web_read(
            {'id': {}, 'is_productor': {}, 'step_export_fundo_ids': {}})
        ids = {pk for row in rows for pk in row['step_export_fundo_ids']}
        scoped.env.cr.execute('SELECT id,partner_id FROM step_fundo WHERE id=ANY(%s)', [list(ids)])
        original_partner = dict(scoped.env.cr.fetchall())
        assert all(original_partner[pk] == row['id'] for row in rows for pk in row['step_export_fundo_ids'])
        farms = scoped.env['step.fundo']
        visible = farms.search([('id', 'in', list(ids))], order='id')
        assert all(company in farm.company_ids for farm in visible)
        hidden = ids - set(visible.ids)
        for pk in hidden:
            try:
                farms.browse(pk).read(['name'])
            except AccessError:
                continue
            raise AssertionError('A farm outside the original record rule could be read')
        encoded = json.dumps([rows, visible.ids], sort_keys=True, default=str).encode()
        partitions[company.id] = {'producers': len(rows), 'linked': len(ids), 'visible_farms': len(visible),
                                  'rejected_farms': len(hidden), 'values_sha256': hashlib.sha256(encoded).hexdigest()}
    return {'uid': actor.id, 'rule': rule.id, 'field': field.id, 'delegated': delegated.id, 'partitions': partitions}
