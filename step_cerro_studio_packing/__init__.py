from odoo.addons.step_cerro_studio_adoption.ownership import adopt


LEGACY = {
    'process_types': 'odoo_studio_step_pac_97e5ba32-1ff6-4533-b129-64c9d7c2d13c',
    'packing_summary': 'odoo_studio_step_pac_30c94bad-4a0d-482d-9bf6-49393b7cd896',
    'package_tags': 'odoo_studio_packing__86a22479-165a-420c-90f8-8b94f530c935',
    'packing_orders': 'odoo_studio_step_pac_830a88ea-ec01-461a-bdae-fa936e0906d6',
    'external_receptions': 'odoo_studio_stock_pi_37167c21-3110-45c0-8fcd-9f89ded2bcc8',
    'process_reception_form': 'odoo_studio_packing__d8cb664b-e70c-4d56-a2a5-d190479677c9',
    'dispatch_types': 'odoo_studio_x_tipo_d_3250512b-69a9-4adb-bfed-cfaab2ff993e',
}


def adopt_views(env):
    adopt(env, 'step_cerro_studio_packing', __file__, LEGACY)
