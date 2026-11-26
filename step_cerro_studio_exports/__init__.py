from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'payment_rates': 'odoo_studio_step_exp_190b5787-3bb7-4f94-b7cb-b1b9a20d75cd',
    'export_partners': 'odoo_studio_res_part_47b48baf-5b77-4192-857b-fed73051f3c7',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_exports', __file__, LEGACY)
