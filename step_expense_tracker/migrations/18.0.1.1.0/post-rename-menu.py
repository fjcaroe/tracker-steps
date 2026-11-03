"""Preserve the requested application name for existing Spanish sessions."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref('hr_expense.menu_hr_expense_root')
    for code, _name in env['res.lang'].get_installed():
        if code.startswith('es_'):
            menu.with_context(lang=code).name = 'Rendiciones'
