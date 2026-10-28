from odoo.exceptions import UserError


def pre_init_hook(env):
    if not env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_PAYROLL_API_'):
        raise UserError('Reference-only payroll test addon: private validation database required.')
