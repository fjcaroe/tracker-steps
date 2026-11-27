from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'stock_transfers': 'odoo_studio_stock_pi_9c7343b2-f76b-4e92-a062-e7dc0e3dc55b',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_transfers', __file__, LEGACY)
