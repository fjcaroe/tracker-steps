"""Hide obsolete Studio navigation after the code menus have loaded."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in (
        "studio_customization.fletes_configuracion_7d810445-2ebc-40bb-a8e9-1b5bf4f4a041",
        "studio_customization.fletes_informes_f7f78fdd-08f1-4672-b71e-2073eda3533f",
    ):
        menu = env.ref(xmlid, raise_if_not_found=False)
        if menu and menu.parent_id == env.ref(
                "step_operations_ui.fletes_7a210622-1359-4a28-a824-530c3f9e78a7"):
            menu.active = False
