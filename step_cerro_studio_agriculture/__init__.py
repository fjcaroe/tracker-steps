from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'analytic_centres': 'odoo_studio_account__ec6c7448-e7d8-4401-a784-09466939543a',
    'farms': 'odoo_studio_step_fun_05371f67-0dae-476d-8fe8-d7eb8da9926f',
    'analytic_centre_form': 'odoo_studio_analytic_cc021bb8-d8f0-4373-9aef-d76b909fee21',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_agriculture', __file__, LEGACY)
