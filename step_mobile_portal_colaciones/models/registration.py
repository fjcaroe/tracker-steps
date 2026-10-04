from odoo import fields, models


class StepColacionRegistration(models.Model):
    _inherit = "step.colacion.registration"

    app_operator_id = fields.Many2one(
        "step.app.person", string="Operador (app Steps)", readonly=True, copy=False, index=True,
        help="Persona autenticada en la app que registró la entrega. Vacío cuando proviene de un tótem o ingreso manual.")
    app_device_id = fields.Many2one("step.app.device", string="Dispositivo (app Steps)", readonly=True, copy=False)
