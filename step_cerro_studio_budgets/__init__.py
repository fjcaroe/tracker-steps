from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'product_category_accounts': 'odoo_studio_product__66d2ee7b-6e3f-4aab-a387-9c8e824d1b8d',
    'season_budget': 'odoo_studio_step_man_51361f75-75d9-4164-85d1-5d29ce09987d',
    'actual_costs': 'odoo_studio_step_man_7f7140fb-cec7-4dec-87a3-83e1f3617aef',
    'budget_summary': 'odoo_studio_budget_s_e170d116-d178-4e09-a365-c64fd403227d',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_budgets', __file__, LEGACY)
