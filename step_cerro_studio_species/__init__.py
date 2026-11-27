from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'species': 'odoo_studio_step_esp_6fc7303b-023d-4232-9b1d-b68ec52aed91',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_species', __file__, LEGACY)
