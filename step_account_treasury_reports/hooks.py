from odoo.addons.step_account_treasury.report_ownership import BRIDGE, preserve_menus

# Own integration metadata, not an implementation of Enterprise reports.
LAUNCHERS = (
    ('menu_treasury_bank_reconciliation', 'Conciliación bancaria', 'menu_treasury_bank',
     'action_account_report_bank_reconciliation', 20),
    ('menu_treasury_partner_ledger', 'Cuentas corrientes', 'menu_treasury_reports',
     'action_account_report_partner_ledger', 10),
    ('menu_treasury_cash_flow_statement', 'Estado de flujo de efectivo', 'menu_treasury_reports',
     'action_account_report_cs', 20),
    ('menu_treasury_aged_receivable', 'Cuentas por cobrar vencidas', 'menu_treasury_reports',
     'action_account_report_ar', 30),
    ('menu_treasury_aged_payable', 'Cuentas por pagar vencidas', 'menu_treasury_reports',
     'action_account_report_ap', 40),
)


def pre_init_reports(env):
    preserve_menus(env)


def post_init_reports(env):
    # XML noupdate does not prevent writes in init mode. Explicitly create only
    # missing launchers so installing this bridge never rewrites an adopted menu.
    preserve_menus(env)
    for name, label, parent, action_name, sequence in LAUNCHERS:
        if env.ref(BRIDGE + '.' + name, raise_if_not_found=False):
            continue
        action = env.ref('account_reports.' + action_name)
        menu = env['ir.ui.menu'].create({
            'name': label, 'parent_id': env.ref('step_account_treasury.' + parent).id,
            'action': '%s,%s' % (action._name, action.id), 'sequence': sequence,
        })
        env['ir.model.data'].create({'module': BRIDGE, 'name': name,
                                     'model': 'ir.ui.menu', 'res_id': menu.id, 'noupdate': True})
    preserve_menus(env)
