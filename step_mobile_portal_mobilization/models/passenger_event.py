from odoo import fields, models


class StepMobilizationPassengerEvent(models.Model):
    _inherit = "step.mobilization.passenger.event"

    app_person_id = fields.Many2one(
        "step.app.person", string="Registrado por (app Steps)", readonly=True, copy=False, index=True,
        help="Persona autenticada que marcó el evento: conserva la autoría aunque cambie el teléfono.")
