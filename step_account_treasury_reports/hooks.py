from odoo.addons.step_account_treasury.report_ownership import preserve_menus


def pre_init_reports(env):
    preserve_menus(env)


def post_init_reports(env):
    preserve_menus(env)
