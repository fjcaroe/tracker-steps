"""A clean CE provider is not permission to convert an existing native registry."""
from odoo import _
from odoo.exceptions import UserError


def require_clean_provider(env):
    env.cr.execute("SELECT name FROM ir_module_module WHERE name IN "
        "('account_batch_payment','account_accountant_batch_payment') AND state IN ('installed','to upgrade','to remove')")
    if env.cr.fetchone():
        raise UserError(_('No instale este proveedor junto al motor nativo. La conversión fría aún no está certificada.'))
    env.cr.execute("SELECT to_regclass('account_batch_payment')")
    if env.cr.fetchone()[0]:
        env.cr.execute("SELECT 1 FROM ir_module_module WHERE name='step_batch_payment_core' AND state IN ('installed','to upgrade')")
        if not env.cr.fetchone():
            raise UserError(_('Existe almacenamiento de lotes previo. Se requiere una migración de identidad certificada.'))
