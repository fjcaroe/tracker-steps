from odoo import fields, models


class StepAppMobilizationIncident(models.Model):
    """Incidencia de un servicio reportada por el conductor desde la app Steps (extensión v1 del contrato de Movilización).

    Es una extensión coherente con el dominio existente: no toca el costeo ni los eventos de pasajero. Idempotente por (viaje, clave).
    """
    _name = "step.app.mobilization.incident"
    _description = "Incidencia de servicio (app Steps)"
    _order = "device_datetime desc, id desc"

    trip_id = fields.Many2one("step.movi.registry", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="trip_id.company_id", store=True, index=True)
    key = fields.Char(required=True, index=True)
    person_id = fields.Many2one("step.app.person", string="Reportada por", required=True, index=True)
    category = fields.Selection(
        [("breakdown", "Falla del vehículo"), ("delay", "Atraso"), ("passenger", "Pasajero"), ("safety", "Seguridad"), ("other", "Otra")],
        required=True, default="other")
    text = fields.Text(required=True)
    device_datetime = fields.Datetime(required=True)
    server_datetime = fields.Datetime(default=fields.Datetime.now, readonly=True)

    _sql_constraints = [("trip_key_unique", "unique(trip_id, key)", "Esta incidencia ya fue recibida.")]
