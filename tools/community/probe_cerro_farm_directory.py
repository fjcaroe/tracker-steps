"""Exercise the original producer/farm inverse, aliases and cross-company contact search as the inventory user."""
import hashlib
import json

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
        scoped = contacts.with_context(allowed_company_ids=[company.id])
        rows = scoped.search([('is_productor', '=', True)], order='id').web_read(
            {'id': {}, 'is_productor': {}, 'step_export_fundo_ids': {}})
        for row in rows:
            linked = scoped.env['step.fundo'].browse(row['step_export_fundo_ids'])
            assert all(farm.partner_id.id == row['id'] and company in farm.company_ids for farm in linked)
        encoded = json.dumps(rows, sort_keys=True, default=str).encode()
        partitions[company.id] = {'producers': len(rows), 'farms': sum(len(x['step_export_fundo_ids']) for x in rows),
                                  'values_sha256': hashlib.sha256(encoded).hexdigest()}
    return {'uid': actor.id, 'rule': rule.id, 'field': field.id, 'delegated': delegated.id, 'partitions': partitions}
