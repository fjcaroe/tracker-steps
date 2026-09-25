"""Corte V2 A — recursos configurables del plan de cosecha.

`Anexo 1.6.9 plan de cosecha V2.xlsx` (hechos verificados por el cliente)
muestra una cadena de relaciones encadenadas, no valores maestros
universales: cajas = kg / kg-por-caja; unidad de traslado = cajas / cajas-
por-unidad; jornales = kg / rendimiento-kg-por-jornada; cosecheros/día =
jornales/días; cargos de apoyo (supervisor, jefe de cuadrilla, anotadores,
tractoristas, cargador) = cosecheros/día / tamaño de cuadrilla; pallets/día
= unidad de traslado / días; viajes/día = pallets/día / pallets-por-viaje;
maquinaria/día = viajes/día / viajes-por-máquina. Los factores del anexo
(4, 60, 55, 5, 30, 2, 10) son **ejemplos**, nunca constantes del código: cada
recurso guarda su propio factor, editable por plan.

Un `step.management.harvest.resource` es un nodo de esa cadena: su fuente es
o bien los kilos semanales del plan (`source_type='harvest_kg'`, sumados por
semana entre todos los centros — igual que la fila "TOTAL" del anexo) o bien
otro recurso del mismo plan (`source_type='resource'`). `_compute_weeks()`
resuelve la cadena en orden topológico y congela cada valor semanal en
`step.management.harvest.resource.week` (snapshot; nunca se edita a mano).

Los envases reutilizables (C4, respuesta del cliente) son el mismo modelo
con `is_reusable_container=True`: no se mezclan con
`step.management.stock.requirement` (consumibles) ni generan compras. Sólo
muestran necesidad semanal/máxima de temporada, un inventario objetivo
(multiplicador configurable, default 3, nunca escondido) y la existencia real
si hay un producto vinculado.
"""

import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round

RESOURCE_KEYS = [
    ("boxes", "Cajas cosecheras"),
    ("pallet_unit", "Unidad de traslado / pallet"),
    ("harvest_workers", "Cosecheros"),
    ("supervisor", "Supervisor"),
    ("crew_chief", "Jefe de cuadrilla"),
    ("recorders", "Anotadores"),
    ("tractor_drivers", "Tractoristas"),
    ("loader", "Cargador"),
    ("pallets_day", "Pallets con fruta por día"),
    ("trips_day", "Viajes por día"),
    ("machinery", "Tractor / coloso / maquinaria equivalente"),
    ("other", "Otro"),
]
SOURCE_TYPES = [
    ("harvest_kg", "Kilos de cosecha semanales del plan"),
    ("resource", "Otro recurso del plan"),
]
ROUNDING_POLICIES = [
    ("precision", "Precisión de la UdM"),
    ("ceil", "Hacia arriba (recurso indivisible)"),
    ("none", "Sin redondeo"),
]


class StepManagementHarvestResource(models.Model):
    _name = "step.management.harvest.resource"
    _description = "Recurso configurable del plan de cosecha"
    _order = "harvest_plan_id, sequence, id"
    _check_company_auto = True

    harvest_plan_id = fields.Many2one(
        "step.management.harvest.plan", string="Plan de cosecha", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="harvest_plan_id.company_id", string="Empresa", store=True, index=True,
    )
    sequence = fields.Integer(default=10)
    resource_key = fields.Selection(RESOURCE_KEYS, string="Recurso", required=True)
    label = fields.Char(string="Etiqueta", required=True)
    source_type = fields.Selection(
        SOURCE_TYPES, string="Fuente", required=True, default="harvest_kg",
    )
    source_resource_id = fields.Many2one(
        "step.management.harvest.resource", string="Recurso de origen",
        domain="[('harvest_plan_id', '=', harvest_plan_id), ('id', '!=', id)]",
        ondelete="restrict", check_company=True,
    )
    factor = fields.Float(
        string="Factor (divisor)", digits=(16, 6), required=True,
        help="Ejemplo del anexo: kg por caja, cajas por unidad de traslado, "
             "kg por jornada, tamaño de cuadrilla, días de trabajo, pallets "
             "por viaje, viajes por máquina/día. Editable por plan; nunca "
             "hardcodeado.",
    )
    rounding_policy = fields.Selection(
        ROUNDING_POLICIES, string="Redondeo", required=True, default="precision",
        help="Política visible por recurso — nunca se redondean personas, "
             "pallets o máquinas en silencio.",
    )
    uom_id = fields.Many2one(
        "uom.uom", string="UdM",
        help="Usada por la política «Precisión de la UdM»; también "
             "informativa para el resto.",
    )
    is_reusable_container = fields.Boolean(
        string="Envase reutilizable", default=False,
        help="C4: va en un listado aparte de las necesidades de stock "
             "consumible; no genera compras automáticas.",
    )
    product_id = fields.Many2one(
        "product.product", string="Producto / equipo vinculado", check_company=True,
        help="Opcional. Si existe, se lee su existencia real (sólo lectura "
             "agregada) para calcular la brecha contra el inventario objetivo.",
    )
    coverage_multiplier = fields.Float(
        string="Multiplicador de cobertura", digits=(16, 2), default=3.0,
        help="C4: el cliente referencia inventario ≥ 3× la necesidad. Política "
             "configurable, no un multiplicador escondido.",
    )
    week_ids = fields.One2many(
        "step.management.harvest.resource.week", "resource_id", string="Semanas",
        copy=False,
    )
    weekly_max_value = fields.Float(
        string="Necesidad semanal máxima", compute="_compute_container_summary",
        store=True, digits=(16, 4),
    )
    target_inventory = fields.Float(
        string="Inventario objetivo", compute="_compute_container_summary",
        store=True, digits=(16, 4),
    )
    on_hand_quantity = fields.Float(
        string="Existencia actual", compute="_compute_container_summary",
        store=True, digits=(16, 4),
    )
    inventory_gap = fields.Float(
        string="Brecha vs. objetivo", compute="_compute_container_summary",
        store=True, digits=(16, 4),
    )

    @api.depends(
        "is_reusable_container", "week_ids.value", "coverage_multiplier", "product_id",
    )
    def _compute_container_summary(self):
        for resource in self:
            if not resource.is_reusable_container:
                resource.weekly_max_value = 0.0
                resource.target_inventory = 0.0
                resource.on_hand_quantity = 0.0
                resource.inventory_gap = 0.0
                continue
            weekly_max = max(resource.week_ids.mapped("value") or [0.0])
            target = weekly_max * (resource.coverage_multiplier or 0.0)
            on_hand = 0.0
            if resource.product_id:
                # Lectura agregada de sólo consulta; sudo() por el mismo
                # motivo que `stock_requirement.py` (el rol de Gestión y
                # Costos no tiene por qué tener acceso a Inventario).
                on_hand = resource.product_id.sudo().with_company(
                    resource.company_id
                ).qty_available
            resource.weekly_max_value = weekly_max
            resource.target_inventory = target
            resource.on_hand_quantity = on_hand
            resource.inventory_gap = max(0.0, target - on_hand)

    @api.constrains("factor")
    def _check_factor(self):
        for resource in self:
            if float_round(resource.factor, precision_digits=6) == 0.0:
                raise ValidationError(_(
                    "El factor de «%s» no puede ser cero (división por cero)."
                ) % resource.label)

    @api.constrains("source_type", "source_resource_id")
    def _check_source(self):
        for resource in self:
            if resource.source_type == "resource" and not resource.source_resource_id:
                raise ValidationError(_(
                    "«%s» usa otro recurso como fuente pero no lo indicó."
                ) % resource.label)
            if resource.source_type == "harvest_kg" and resource.source_resource_id:
                raise ValidationError(_(
                    "«%s» no puede tener recurso de origen si su fuente son "
                    "los kilos del plan."
                ) % resource.label)
            # Detección de ciclos en la cadena.
            seen = set()
            current = resource
            while current.source_type == "resource" and current.source_resource_id:
                if current.id and current.id in seen:
                    raise ValidationError(_(
                        "La cadena de recursos de «%s» tiene un ciclo."
                    ) % resource.label)
                seen.add(current.id)
                current = current.source_resource_id
                if current == resource:
                    raise ValidationError(_(
                        "«%s» no puede depender (directa o indirectamente) de "
                        "sí mismo."
                    ) % resource.label)

    # ------------------------------------------------------------------
    # Cálculo encadenado (orden topológico)
    # ------------------------------------------------------------------
    def _round_value(self, raw):
        self.ensure_one()
        if self.rounding_policy == "ceil":
            return float(math.ceil(raw - 1e-9)) if raw > 0 else 0.0
        rounding = self.uom_id.rounding if self.uom_id else 0.0001
        if self.rounding_policy == "none":
            return raw
        return float_round(raw, precision_rounding=rounding)

    def _compute_weeks(self):
        """Recalcula `week_ids` para cada recurso del/de los plan(es), en
        orden topológico (una fuente siempre se resuelve antes que quien
        depende de ella). No se llama sobre un plan confirmado (el estado
        del plan ya lo impide en `action_generate`)."""
        resources = self
        if not resources:
            return
        plans = resources.mapped("harvest_plan_id")
        for plan in plans:
            plan_resources = resources.filtered(lambda r: r.harvest_plan_id == plan)
            kg_by_week = {}
            for line in plan.line_ids:
                kg_by_week[line.week_number] = kg_by_week.get(line.week_number, 0.0) + line.kg
            week_numbers = sorted(kg_by_week)
            week_labels = {
                line.week_number: line.week_label for line in plan.line_ids
            }

            resolved = {}  # resource.id -> {week_number: value}
            pending = list(plan_resources)
            guard = len(pending) + 1
            while pending and guard > 0:
                guard -= 1
                progressed = False
                still_pending = []
                for resource in pending:
                    if resource.source_type == "harvest_kg":
                        source_by_week = kg_by_week
                        source_ready = True
                    else:
                        source_ready = resource.source_resource_id.id in resolved
                        source_by_week = resolved.get(resource.source_resource_id.id, {})
                    if not source_ready:
                        still_pending.append(resource)
                        continue
                    values = {}
                    for week_number in week_numbers:
                        source_value = source_by_week.get(week_number, 0.0)
                        raw = source_value / resource.factor if resource.factor else 0.0
                        values[week_number] = resource._round_value(raw)
                    resolved[resource.id] = values
                    resource.week_ids.unlink()
                    resource.write({"week_ids": [
                        (0, 0, {
                            "week_number": week_number,
                            "week_label": week_labels.get(week_number, "W%02d" % week_number),
                            "source_value": source_by_week.get(week_number, 0.0),
                            "factor_snapshot": resource.factor,
                            "value": values[week_number],
                        })
                        for week_number in week_numbers
                    ]})
                    progressed = True
                pending = still_pending
                if not progressed and pending:
                    raise UserError(_(
                        "No se pudo resolver la cadena de recursos (posible "
                        "ciclo o recurso de origen de otro plan): %s"
                    ) % ", ".join(r.label for r in pending))


class StepManagementHarvestResourceWeek(models.Model):
    _name = "step.management.harvest.resource.week"
    _description = "Valor semanal congelado de un recurso del plan de cosecha"
    _order = "resource_id, week_number, id"
    _check_company_auto = True

    resource_id = fields.Many2one(
        "step.management.harvest.resource", string="Recurso", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="resource_id.company_id", string="Empresa", store=True, index=True,
    )
    harvest_plan_id = fields.Many2one(
        related="resource_id.harvest_plan_id", string="Plan", store=True,
    )
    week_number = fields.Integer(string="Semana")
    week_label = fields.Char(string="Semana")
    source_value = fields.Float(string="Valor de la fuente", digits=(16, 4))
    factor_snapshot = fields.Float(string="Factor aplicado", digits=(16, 6))
    value = fields.Float(string="Resultado", digits=(16, 4))

    _sql_constraints = [
        ("harvest_resource_week_unique", "unique(resource_id, week_number)",
         "No puede repetirse la misma semana para un recurso."),
    ]

    def write(self, vals):
        raise UserError(_(
            "El valor semanal de un recurso es un cálculo del sistema; no se "
            "edita a mano. Ajuste el factor del recurso y regenere el plan."
        ))

    def unlink(self):
        # `_compute_weeks()` sí necesita poder borrar/recrear (usa
        # `sudo()`-like privilegio implícito de ser llamado desde el propio
        # modelo); se permite el unlink normal, sólo se bloquea `write`.
        return super().unlink()
