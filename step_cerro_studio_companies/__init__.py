from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'company_directory': 'odoo_studio_res_comp_082adeb5-66a8-4dc8-8992-cbf944bb4a04',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_companies', __file__, LEGACY)
