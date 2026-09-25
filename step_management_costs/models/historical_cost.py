from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .exchange_rate import default_conversion_currency


class StepManagementHistoricalCost(models.Model):
    _name = "step.management.historical.cost"
    _description = "Costo histórico operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Descripción", required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    date = fields.Date(string="Mes / fecha", required=True, index=True)
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", required=True,
        index=True, check_company=True,
    )
    group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuestario", index=True,
        check_company=True,
    )
    origin = fields.Selection(
        [("external", "Gasto externo previo al ERP"),
         ("adjustment", "Ajuste manual justificado"),
         ("unreviewed", "Sin clasificar (heredado)")],
        string="Procedencia", required=True, default="external", tracking=True,
        help="El gasto real corriente se lee de la contabilidad analítica. "
             "Este modelo queda reservado para gasto externo previo a la puesta "
             "en marcha y para ajustes. Los registros 'sin clasificar' se "
             "excluyen de los comparativos hasta que se revise su procedencia.",
    )
    source_reference = fields.Char(string="Referencia de origen")
    source_file = fields.Binary(string="Respaldo", attachment=True)
    source_filename = fields.Char(string="Nombre del respaldo")
    locked = fields.Boolean(
        string="Bloqueado", default=False, copy=False, tracking=True,
        help="Un registro bloqueado no puede editarse ni borrarse salvo por un "
             "administrador de Gestión y Costos.",
    )
    indicator = fields.Char(string="Indicador / labor")
    quantity = fields.Float(string="Cantidad / jornadas", digits=(16, 4))

    # ------------------------------------------------------------------
    # Corte V2 B — hecho histórico normalizado (D-L, ADR_001 §D-L).
    # `dataset_kind` distingue una foto de presupuesto histórico de una de
    # real histórico; ambos son hechos de UNA fuente (una fila del archivo
    # oficial), no un documento operacional. Los registros manuales previos
    # a este corte dejan `dataset_kind` vacío y siguen funcionando como
    # comparación pareada (actual_amount + budget_amount en la misma fila).
    # ------------------------------------------------------------------
    dataset_kind = fields.Selection(
        [("budget", "Presupuesto histórico"), ("actual", "Real histórico")],
        string="Tipo de hecho",
        help="Vacío = registro manual pareado (comportamiento previo a V2 B). "
             "«Presupuesto»/«Real» = hecho normalizado de una carga oficial "
             "(Anexo 1.6.2.1 / 1.6.10.3): una fila = un registro fuente.",
    )
    import_batch_id = fields.Many2one(
        "step.management.historical.import.batch", string="Lote de carga",
        readonly=True, copy=False, ondelete="restrict",
    )
    record_type_label = fields.Char(
        string="Tipo de registro (archivo)",
        help="«Tipo registro» del real histórico (p. ej. «Externo»).",
    )
    budget_version = fields.Char(string="Versión de presupuesto (archivo)")
    season_code = fields.Char(
        string="Código de temporada (archivo)",
        help="Código tal cual el archivo (p. ej. «2425»). La temporada "
             "normalizada («2024/2025») se guarda en `season`.",
    )
    season = fields.Char(string="Temporada")
    year = fields.Integer(string="Año")
    month = fields.Integer(string="Mes (1-12)")
    farm = fields.Char(string="Fundo")
    species = fields.Char(string="Especie")
    variety = fields.Char(string="Variedad")
    cost_center_type_label = fields.Char(string="Tipo de centro (archivo)")
    center_label = fields.Char(string="Centro de costos (archivo)")
    origin_label = fields.Char(string="Origen (archivo)")
    budget_group_label = fields.Char(string="Grupo presupuesto (archivo)")
    activity_label = fields.Char(string="Actividad (archivo)")
    product_label = fields.Char(string="Producto-labor (archivo)")
    uom_label = fields.Char(string="UdM (archivo)")
    source_amount = fields.Float(
        string="Monto origen (archivo)", digits=(16, 2),
        help="Valor CLP tal cual el archivo, snapshot — nunca recalculado.",
    )
    source_exchange_rate = fields.Float(
        string="TC origen (archivo)", digits=(16, 6),
        help="Snapshot del tipo de cambio del archivo (fórmula resuelta en "
             "servidor para el real histórico, nunca ejecutada como fórmula "
             "arbitraria de Excel).",
    )
    source_amount_usd = fields.Float(
        string="Monto USD origen (archivo)", digits=(16, 2),
        help="Valor US$ tal cual el archivo, snapshot — nunca recalculado.",
    )
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Convertir a",
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    conversion_rate_type = fields.Selection(
        [("actual", "Real Odoo"), ("estimated", "Estimado mensual")],
        string="Tipo de conversión", default="actual", required=True,
    )
    actual_amount = fields.Monetary(string="Valor real", currency_field="currency_id")
    budget_amount = fields.Monetary(string="Valor presupuestado", currency_field="currency_id")
    variance = fields.Monetary(
        string="Desviación", compute="_compute_variance", store=True, currency_field="currency_id"
    )
    variance_percent = fields.Float(string="Desviación %", compute="_compute_variance", store=True)
    conversion_available = fields.Boolean(compute="_compute_conversion")
    conversion_factor = fields.Float(
        string="Factor origen → destino", compute="_compute_conversion", digits=(16, 10)
    )
    conversion_target_value = fields.Float(
        string="Valor moneda destino", compute="_compute_conversion", digits=(16, 6)
    )
    actual_amount_converted = fields.Monetary(
        string="Real convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    budget_amount_converted = fields.Monetary(
        string="Presupuestado convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    variance_converted = fields.Monetary(
        string="Desviación convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    notes = fields.Char(string="Observación")

    @api.depends("actual_amount", "budget_amount")
    def _compute_variance(self):
        for record in self:
            record.variance = record.actual_amount - record.budget_amount
            # La variación porcentual se recalcula desde los totales; nunca se
            # obtiene sumando porcentuales de las líneas.
            record.variance_percent = (
                record.variance * 100.0 / record.budget_amount if record.budget_amount else 0.0
            )

    def _is_management_manager(self):
        return self.env.user.has_group(
            "step_management_costs.group_management_manager"
        )

    def write(self, vals):
        if not self._is_management_manager():
            locked = self.filtered(
                lambda record: record.locked and set(vals) - {"message_ids", "message_follower_ids"}
            )
            # Permitir sólo desbloquear no está autorizado para no administradores.
            if locked and not (set(vals) <= {"message_ids", "message_follower_ids"}):
                raise UserError(_(
                    "El costo histórico %s está bloqueado. Solicite a un "
                    "administrador de Gestión y Costos que lo desbloquee."
                ) % ", ".join(locked.mapped("name")))
        return super().write(vals)

    def unlink(self):
        if not self._is_management_manager():
            locked = self.filtered(lambda record: record.locked)
            if locked:
                raise UserError(_(
                    "No puede eliminar costos históricos bloqueados: %s"
                ) % ", ".join(locked.mapped("name")))
        return super().unlink()

    @api.depends(
        "actual_amount", "budget_amount", "variance", "currency_id",
        "conversion_currency_id", "conversion_rate_type", "date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            actual_result = service.get_conversion(
                record.actual_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            budget_result = service.get_conversion(
                record.budget_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            variance_result = service.get_conversion(
                record.variance, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            record.conversion_available = actual_result["available"]
            record.conversion_factor = actual_result["factor"]
            record.conversion_target_value = actual_result["target_value"]
            record.actual_amount_converted = actual_result["amount"]
            record.budget_amount_converted = budget_result["amount"]
            record.variance_converted = variance_result["amount"]
