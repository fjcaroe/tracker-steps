from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    step_expense_vehicle_mode = fields.Selection(
        [
            ("optional", "Opcional (lo decide el usuario en cada rendición)"),
            ("always", "Siempre visible"),
            ("never", "Oculto"),
        ],
        string="Uso de vehículo en rendiciones",
        default="optional",
        required=True,
    )
