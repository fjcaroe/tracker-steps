"""Connect existing launchers without deleting menus or shared native actions."""
from odoo.exceptions import UserError
from odoo.addons.step_account_treasury.report_ownership import preserve_menus

MODULE = 'step_treasury_community_reports'
LAUNCHERS = (
    ('menu_treasury_bank_reconciliation', 'bank', 'Conciliación bancaria', 'menu_treasury_bank', 20),
    ('menu_treasury_partner_ledger', 'ledger', 'Cuentas corrientes', 'menu_treasury_reports', 10),
    ('menu_treasury_cash_flow_statement', 'cash', 'Estado de flujo de efectivo', 'menu_treasury_reports', 20),
    ('menu_treasury_aged_receivable', 'receivable', 'Cuentas por cobrar vencidas', 'menu_treasury_reports', 30),
    ('menu_treasury_aged_payable', 'payable', 'Cuentas por pagar vencidas', 'menu_treasury_reports', 40),
)


def post_init_reports(env):
    # A conflict in the fifth menu must not leave four launchers converted when
    # a Python caller handles the error inside its existing transaction.
    with env.cr.savepoint():
        _adopt_launchers(env)


def _adopt_launchers(env):
    data = env['ir.model.data']
    for name, kind, label, parent, sequence in LAUNCHERS:
        entries = data.search([('module', 'in', ('step_account_treasury', 'step_account_treasury_reports', MODULE)), ('name', '=', name)])
        if entries and (len({(entry.model, entry.res_id) for entry in entries}) != 1 or entries[0].model != 'ir.ui.menu'):
            raise UserError('Identificadores en conflicto: ' + name)
        action = env.ref(MODULE + '.action_' + kind)
        if entries:
            menu = env['ir.ui.menu'].browse(entries[0].res_id).exists()
            if not menu:
                raise UserError('Menú inexistente: ' + name)
            # Preserve native action IDs and custom targets. Only the known
            # Enterprise launcher or our own action is an authorized conversion.
            expected = {'bank': 'bank_reconciliation', 'ledger': 'partner_ledger',
                        'cash': 'cs', 'receivable': 'ar', 'payable': 'ap'}[kind]
            legacy = env.ref('account_reports.action_account_report_' + expected, raise_if_not_found=False)
            if menu.action != action and (not legacy or menu.action != legacy):
                raise UserError('El menú tiene una acción personalizada; requiere migración explícita: ' + name)
            if menu.action != action:
                menu.action = '%s,%s' % (action._name, action.id)
        else:
            menu = env['ir.ui.menu'].create({'name': label, 'parent_id': env.ref('step_account_treasury.' + parent).id,
                                             'action': '%s,%s' % (action._name, action.id), 'sequence': sequence})
        for namespace in ('step_account_treasury', MODULE):
            if not entries.filtered(lambda entry: entry.module == namespace):
                data.create({'module': namespace, 'name': name, 'model': 'ir.ui.menu', 'res_id': menu.id, 'noupdate': True})
    preserve_menus(env)
