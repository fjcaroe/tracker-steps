"""Replace only the known Studio numbering automation with native create()."""
import ast

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'base.automation' not in env:
        return
    expected = ast.dump(ast.parse("if record:\n record['name'] = env['ir.sequence'].next_by_code('gastos.fletes') or '/'"))
    for rule in env['base.automation'].search([('model_name', '=', 'step.freight.order')]):
        actions = rule.action_server_ids
        if len(actions) == 1 and actions.state == 'code' and ast.dump(ast.parse(actions.code or '')) == expected:
            rule.active = False
