"""Transfer only the five Enterprise launchers; never replace their records."""
from odoo.exceptions import UserError

CORE = 'step_account_treasury'
BRIDGE = 'step_account_treasury_reports'
MENUS = (
    'menu_treasury_bank_reconciliation', 'menu_treasury_partner_ledger',
    'menu_treasury_cash_flow_statement', 'menu_treasury_aged_receivable',
    'menu_treasury_aged_payable',
)


def preserve_menus(env, require_bridge=False):
    data = env['ir.model.data']
    legacy = data.search([('module', '=', CORE), ('name', 'in', MENUS)])
    if require_bridge and legacy and not env['ir.module.module'].search_count([
        ('name', 'in', (BRIDGE, 'step_treasury_community_reports')), ('state', 'in', ('installed', 'to install', 'to upgrade')),
    ]):
        raise UserError('Actualice Tesorería instalando también step_account_treasury_reports '
                        'para conservar los cinco accesos de informes existentes.')
    for name in MENUS:
        entries = data.search([('module', 'in', (CORE, BRIDGE)), ('name', '=', name)])
        if not entries:
            continue
        targets = {(entry.model, entry.res_id) for entry in entries}
        if len(targets) != 1 or entries[0].model != 'ir.ui.menu':
            raise UserError('Identificador de menú de Tesorería en conflicto: ' + name)
        if not env['ir.ui.menu'].browse(entries[0].res_id).exists():
            raise UserError('Menú de Tesorería inexistente: ' + name)
        for namespace in (CORE, BRIDGE):
            if not entries.filtered(lambda entry: entry.module == namespace):
                data.create({'module': namespace, 'name': name, 'model': 'ir.ui.menu',
                             'res_id': entries[0].res_id, 'noupdate': True})
        # Keep old API aliases and all operator customizations, including groups,
        # parent, sequence, active flag and action. XML is only for new installs.
        entries.write({'noupdate': True})
