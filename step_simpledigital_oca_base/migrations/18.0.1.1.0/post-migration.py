from odoo.addons.step_simpledigital_oca_base.hooks import mark_existing_history


def migrate(cr,version):
    mark_existing_history(cr)
