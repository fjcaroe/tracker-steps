"""Corte V2 E — tarifa hora/máquina desde los modelos reales de `step_machinery`.

Auditoría (sólo lectura, `step_machinery` 18.0.22.0.0 en `odoo-new`):

* ``fleet.vehicle`` (extendido por `step_machinery`) trae `consumption_line`
  y `radio_line` (O2M a `monthly.consumption.line`/`monthly.radio.line`),
  cada línea con `service_machinery_id` (M2o `type.service.machinery`,
  catálogo canónico de 8 conceptos: combustible, aceites y lubricantes,
  repuestos, mantención correctiva, mano de obra, arriendo, mantención
  preventiva, depreciación mensual — códigos "01".."08") y `concept_amount`/
  `cost_hr_amount`. `step_total_hrs_mes` es la base de horas mensuales.
* El propio `step_machinery` ya calcula el costo/hora estándar del vehículo
  completo (`fleet.vehicle._compute_costo` → `step_cost_hrmq_standar`) con
  la misma guarda de cero horas que se replica aquí
  (``sum(...) / horas if horas else 0.0``, jamás división por cero) y con
  el mismo criterio de `step.hrs.machinery.line._hourly_cost_by_code()`
  para resolver el costo por hora de un concepto: usa `cost_hr_amount` si
  está informado, si no reparte `concept_amount` entre las horas del mes.
* No se modifica `step_machinery`: este módulo sólo *lee* esos campos
  reales (por código de concepto, nunca por nombre/ID fijo) y agrega, en
  este puente, el desglose por componente y la variación de tarifa por
  labor que el core de maquinaria no ofrece.
"""

from odoo import api, fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    def mc_standard_hourly_components(self):
        """Costo/hora estándar por concepto real (código → monto), nunca
        división por cero: con `step_total_hrs_mes` en cero el resultado es
        0.0 para todos los conceptos, aunque existan montos mensuales
        informados (cero horas es un estado válido — inactividad,
        mantención o receso)."""
        self.ensure_one()
        result = {}
        for source in (self.consumption_line, self.radio_line):
            for item in source:
                code = item.service_machinery_id.cod
                if not code:
                    continue
                hourly = item.cost_hr_amount
                if not hourly and self.step_total_hrs_mes:
                    hourly = item.concept_amount / self.step_total_hrs_mes
                result[code] = result.get(code, 0.0) + hourly
        return result

    def mc_standard_hourly_rate(self):
        """Suma de todos los componentes — costo/hora estándar del vehículo."""
        self.ensure_one()
        return sum(self.mc_standard_hourly_components().values())


class StepManagementMachineryLaborRate(models.Model):
    _name = "step.management.machinery.labor.rate"
    _description = "Tarifa hora/máquina por labor (excepción a la tarifa estándar del vehículo)"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    vehicle_id = fields.Many2one(
        "fleet.vehicle", string="Maquinaria", required=True,
        check_company=True, index=True, ondelete="cascade",
    )
    labor_id = fields.Many2one(
        "step.labor", string="Labor", required=True, index=True, ondelete="cascade",
        help="La tarifa puede variar por labor: esta fila reemplaza, para "
             "esta combinación de maquinaria y labor, la tarifa estándar "
             "calculada desde los conceptos reales del vehículo.",
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    hourly_rate = fields.Monetary(
        string="Tarifa hora/máquina", currency_field="currency_id", required=True,
    )
    notes = fields.Char(string="Observación")

    _sql_constraints = [
        ("machinery_labor_rate_unique", "unique(company_id, vehicle_id, labor_id)",
         "Ya existe una tarifa para esta maquinaria y esta labor."),
    ]


def get_effective_rate(env, vehicle, labor=None):
    """Tarifa efectiva y desglose de componentes para `vehicle` (+ `labor`
    opcional). Si existe una tarifa específica por labor, ésta reemplaza la
    tarifa estándar del vehículo completa (no se mezclan ambas fuentes,
    para que el desglose por componente siga siendo trazable: cuando hay
    excepción por labor, el desglose es un único componente "labor_rate").
    Nunca lanza por horas en cero: la tarifa estándar ya viene protegida
    desde `mc_standard_hourly_components`."""
    if labor:
        override = env["step.management.machinery.labor.rate"].sudo().search([
            ("vehicle_id", "=", vehicle.id), ("labor_id", "=", labor.id),
        ], limit=1)
        if override:
            return override.hourly_rate, {"labor_rate": override.hourly_rate}
    components = vehicle.mc_standard_hourly_components()
    return vehicle.mc_standard_hourly_rate(), components
