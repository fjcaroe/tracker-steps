from odoo import api, models


class StepMoviRegistry(models.Model):
    _inherit = "step.movi.registry"

    @api.depends("passenger_event_ids.event_type", "passenger_event_ids.passenger_id", "passenger_event_ids.state", "capacity")
    def _compute_passenger_counts(self):
        """Corrección hallada al probar contra Odoo: el cálculo original no se recalcula cuando un evento pasa a «anulado»
        (no depende de `state`), así que anular una marca dejaba los contadores desactualizados. Se redeclara la dependencia
        completa; la lógica sigue siendo la del módulo base. Conviene llevar este cambio a step_mobilization."""
        return super()._compute_passenger_counts()
