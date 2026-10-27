"""Append to the agricultural native check; no persistent business writes."""
from lxml import etree

try:
    if MODE == 'community':
        assert not env['ir.module.module'].search_count([
            ('name', 'in', ['web_gantt', 'web_map', 'hr_payroll', 'step_hr']), ('state', '=', 'installed')])
        assert scoped['res.partner']._fields['duplicate_bank_partner_ids'].type == 'many2many'
    with Form(scoped['res.partner'], view='step_agriculture_core.step_view_res_partner_form') as contact:
        contact.name = 'Private Community producer verification'
        contact.is_productor = True
        contact.cod_csg = 'MIGRATION-TEST'
    assert contact.record.is_productor and contact.record.cod_csg == 'MIGRATION-TEST'
    report_checks = []
    for module, model, date_field in [
        ('step_producer_contract_report', 'step.producer.contract.report', 'date_due'),
        ('step_producer_estimate_report', 'step.producer.estimate.report', 'week_start'),
    ]:
        action = scoped.ref(module + '.report_action')
        view = scoped.ref(module + '.report_gantt')  # Original public ID retained.
        assert action.res_model == model and action.view_mode == 'calendar,pivot,list'
        assert view.type == 'calendar'
        assert [(v.view_mode, v.view_id.id) for v in action.view_ids] == [
            ('calendar', view.id), ('pivot', scoped.ref(module + '.report_pivot').id),
            ('list', scoped.ref(module + '.report_list').id)]
        for kind, target in [('calendar', view), ('pivot', scoped.ref(module + '.report_pivot')),
                             ('list', scoped.ref(module + '.report_list'))]:
            arch = etree.fromstring(scoped[model].get_view(target.id, kind)['arch'])
            assert arch.tag == kind
            if kind == 'calendar':
                assert arch.get('date_start') == date_field
                assert arch.get('date_stop') == 'calendar_end'
                assert all(arch.get(flag) == 'false' for flag in ('create', 'edit', 'delete', 'quick_create'))
        domain = [('company_id', '=', company.id)]
        events = scoped[model].with_context(active_test=False).search_read(
            domain + [('calendar_end', '>=', '2026-01-01')],
            [date_field, 'calendar_end', 'amount_usd', 'producer_id', 'company_id'], limit=100)
        assert all(row['company_id'][0] == company.id for row in events)
        totals = scoped[model].with_context(active_test=False).read_group(domain, ['amount_usd:sum'], [])
        assert scoped.ref(module + '.report_menu').action == action
        report_checks.append({'model': model, 'action': action.id, 'calendar': view.id,
                              'events_read': len(events), 'totals': totals})
    print('PRODUCERS_NATIVE_OK ' + json.dumps({'uid': scoped.uid, 'company_id': company.id,
          'su': scoped.su, 'producer_form': True, 'reports': report_checks}, default=str))
finally:
    env.cr.rollback()
