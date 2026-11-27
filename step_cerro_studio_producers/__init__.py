from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'agricultural_products': 'odoo_studio_product__7c4802d0-f548-4122-91db-5127d64bf173',
    'export_estimates': 'odoo_studio_step_exp_8af10a63-c072-4c4e-87df-7a85ca28489c',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_producers', __file__, LEGACY)
