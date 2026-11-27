"""Read historic Steps sales and opportunity attachments through their original user permissions."""
from hashlib import sha1
import re

from lxml import etree
from odoo.exceptions import AccessError
from odoo.tests import Form

from probe_steps_crm_pipeline import digest


def salesperson(env):
    if not __debug__ or not re.fullmatch(r'(?:COMMUNITY|MANAGEMENT_QA)_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Use the private Steps CRM pair.')
    leads = env['crm.lead'].with_user(7).with_context(allowed_company_ids=[1], active_test=False)
    assert not leads.env.su and leads.env.company.id == 1 and not leads.env.user.has_group('base.group_system')
    return leads


def quote_trial(env):
    leads = salesperson(env).with_context(mail_notify_force_send=False)
    scope = leads.env
    orders = scope['sale.order']
    historical = orders.search([], order='id')
    line = historical.mapped('order_line').filtered(lambda row: not row.display_type and row.product_id.active
                                                    and row.product_id.sale_ok and row.product_uom_qty > 0)[:1]
    lead = leads.search([('active','=',True),('user_id','=',scope.uid),('partner_id','!=',False),
                         ('order_ids','=',False)], order='id', limit=1)
    assert lead and line
    with env.cr.savepoint() as trial:
        action = lead.action_sale_quotations_new()
        assert action['res_model'] == 'sale.order'
        form_view = next((ident for ident, kind in action['views'] if kind == 'form'), False)
        form = Form(orders.with_context(**action['context']), view=form_view or None)
        assert form.partner_id == lead.partner_id
        with form.order_line.new() as entry:
            entry.product_id = line.product_id
            entry.product_uom_qty = line.product_uom_qty
        quote = form.save()
        assert quote.id not in historical.ids and quote.state == 'draft'
        assert (quote.opportunity_id,quote.partner_id,quote.user_id) == (lead,lead.partner_id,scope.user)
        assert quote.order_line.product_id == line.product_id and quote.order_line.product_uom_qty == line.product_uom_qty
        link = lead.action_view_sale_quotation()
        assert link['res_model'] == 'sale.order' and link['res_id'] == quote.id
        result = [lead.id, quote.partner_id.id, quote.user_id.id, quote.pricelist_id.id, quote.currency_id.id,
                  quote.order_line.product_id.id, quote.order_line.product_uom_qty, quote.order_line.price_unit,
                  quote.order_line.tax_id.ids, quote.amount_untaxed, quote.amount_tax, quote.amount_total]
        trial.rollback()
        assert orders.search([], order='id') == historical
    env.cr.rollback()
    return {'database': env.cr.dbname, 'created_from_action': action['id'], 'reopened_from_action': link['id'],
            'original_orders': len(historical), 'state': 'draft', 'terms_and_amounts': digest(result),
            'saved_and_reopened': True, 'rolled_back': True}


def attachment_access(env, opportunity_ids):
    env.cr.execute("""SELECT id FROM ir_attachment WHERE res_model='crm.lead'
                      AND res_id=ANY(%s) AND store_fname IS NOT NULL ORDER BY id""", [opportunity_ids])
    ids = [row[0] for row in env.cr.fetchall()]
    result = {}
    for role, uid in [('sales', 7), ('public', env.ref('base.public_user').id)]:
        model = env['ir.attachment'].with_user(uid).with_context(allowed_company_ids=[1], bin_size=False)
        assert not model.env.su
        decisions, checked = [], []
        for item in model.browse(ids):
            try:
                item.check_access('read')
            except AccessError:
                decisions.append([item.id, False])
                continue
            decisions.append([item.id, True])
            if role == 'sales' and len(checked) < 12 and 0 < item.file_size <= 2_000_000:
                raw = item.raw
                checksum = sha1(raw).hexdigest()
                assert len(raw) == item.file_size and checksum == item.checksum
                checked.append([item.id, len(raw), checksum])
        result[role] = {'scope': len(ids), 'allowed': sum(ok for _, ok in decisions),
                        'decisions': digest(decisions), 'sample': len(checked), 'bytes': digest(checked)}
    return result


def run(env):
    leads = salesperson(env)
    env.cr.execute('SHOW transaction_read_only')
    assert env.cr.fetchone() == ('on',)
    scope = leads.env
    visible = leads.search([], order='id')
    orders = scope['sale.order'].search([], order='id')
    fields = ('state','partner_id','partner_invoice_id','partner_shipping_id','opportunity_id','user_id',
              'team_id','company_id','currency_id','pricelist_id','date_order','amount_untaxed','amount_tax','amount_total')
    linespec = {name: {} for name in ('id','order_id','product_id','product_uom','product_uom_qty',
                                      'price_unit','discount','tax_id','price_subtotal','price_total')}
    specification = {'id': {}, **{k: {} for k in fields}, 'order_line': {'fields': linespec}}
    rows = orders.web_read(specification)
    assert [row['id'] for row in rows] == orders.ids
    links = []
    for lead in orders.mapped('opportunity_id').sorted('id'):
        assert lead in visible
        action = lead.action_view_sale_order()
        assert action['res_model'] == 'sale.order'
        linked = orders.filtered(lambda order: order.opportunity_id == lead and order.state == 'sale')
        if action.get('res_id'):
            assert linked.ids == [action['res_id']]
        else:
            selected = scope['sale.order'].search(action['domain'], order='id')
            assert selected == linked
        links.append([lead.id, action['id'], linked.ids])
    lead = visible.filtered(lambda item: item.active and item.user_id == scope.user and item.partner_id)[:1]
    assert lead
    action = lead.action_sale_quotations_new()
    assert action['res_model'] == 'sale.order'
    context = action['context']
    assert (context['default_opportunity_id'], context['default_partner_id']) == (lead.id, lead.partner_id.id)
    view_id = next((vid for vid, kind in action['views'] if kind == 'form'), False)
    order_view = scope['sale.order'].with_context(**context).get_view(view_id=view_id, view_type='form')
    view_fields = sorted(set(etree.fromstring(order_view['arch'].encode()).xpath('.//field/@name')))
    assert {'partner_id','order_line','pricelist_id','currency_id'} <= set(view_fields)
    return {'database': env.cr.dbname, 'orders': len(rows), 'order_lines': sum(len(row['order_line']) for row in rows),
            'historic_sales': digest(rows), 'linked_opportunities': len(links), 'order_routes': digest(links),
            'new_quote_action': action['id'], 'new_quote_view': order_view['id'], 'new_quote_context': digest(context),
            'quote_form_fields': view_fields, 'attachments': attachment_access(env, visible.ids)}
