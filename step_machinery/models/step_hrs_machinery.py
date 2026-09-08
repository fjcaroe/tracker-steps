# -*- coding: utf-8 -*-

from collections import defaultdict
import json

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError

#: Código de la secuencia que entrega el correlativo "Número OT".
OT_SEQUENCE_CODE = "step.hrs.machinery.ot"

#: Formato de fecha usado dentro del nombre compuesto (dd/MM/yyyy).
NAME_DATE_FORMAT = "%d/%m/%Y"

#: Separador entre los segmentos opcionales del nombre compuesto.
NAME_SEGMENT_SEPARATOR = " – "

#: Marcador temporal mientras el nombre compuesto todavía no se calcula.
NAME_PLACEHOLDER = "/"


class StepHrsMachinery(models.Model):
    _name = "step.hrs.machinery"
    _description = "Registro de horas máquina"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True
    # El nombre histórico se mantiene buscable: referencias como "OT W35"
    # sólo existen ahí después de la normalización de nombres.
    _rec_names_search = ["name", "ot_number", "folio", "legacy_name"]

    ot_number = fields.Char(
        string="Número OT", copy=False, index=True, readonly=True, tracking=True,
        help="Correlativo interno asignado automáticamente al guardar. No se edita ni se reutiliza en copias.",
    )
    name = fields.Char(
        string="Nombre", index=True, copy=False, readonly=True,
        help="Nombre compuesto generado por el sistema: Número OT, fecha, orden de trabajo y folio BPA.",
    )
    legacy_name = fields.Char(
        string="Nombre histórico", copy=False, readonly=True,
        help="Valor que tenía el nombre antes de la normalización, o el nombre enviado por una integración antigua.",
    )
    date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True, tracking=True)
    week_number = fields.Integer(string="Semana", compute="_compute_calendar", store=True)
    responsable_id = fields.Many2one("hr.employee", string="Responsable", tracking=True)
    temp_id = fields.Many2one("step.temporada", string="Temporada", compute="_compute_calendar", store=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    folio = fields.Char(
        string="Orden de Trabajo", index=True,
        help="Referencia operacional de la labor (por ejemplo W35). Es independiente del Folio BPA.",
    )
    fundo_id = fields.Many2one("step.fundo", string="Fundo", ondelete="restrict", copy=True)
    user_id = fields.Many2one("hr.employee", string="Autoriza", tracking=True)
    note = fields.Text(string="Notas")
    hrs_machinery_line = fields.One2many(
        "step.hrs.machinery.line", "machinery_id", string="Registros", copy=True, auto_join=True
    )
    progress_cost = fields.Boolean(string="Procesado", default=False, copy=False)
    state = fields.Selection(
        [("draft", "Nuevo"), ("progress", "En progreso"), ("done", "Listo"),
         ("costed", "Costeado"), ("accounted", "Contabilizado"), ("cancel", "Anulado")],
        string="Estado", required=True, default="draft", copy=False, tracking=True, index=True,
    )
    invoice_id = fields.Many2one("account.move", string="Comprobante contable", copy=False, readonly=True)
    total_hours = fields.Float(string="Horas totales", compute="_compute_totals", store=True)
    total_cost = fields.Monetary(string="Costo total", compute="_compute_totals", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)

    _sql_constraints = [
        ("ot_number_company_uniq", "unique(company_id, ot_number)",
         "El Número OT ya existe en esta empresa."),
    ]

    @api.depends("date", "company_id")
    def _compute_calendar(self):
        Season = self.env["step.temporada"]
        for record in self:
            record.week_number = record.date.isocalendar().week if record.date else 0
            record.temp_id = Season.search(
                [("start_date", "<=", record.date), ("end_date", ">=", record.date)], limit=1
            ) if record.date else False

    @api.depends("hrs_machinery_line.hrs_maquina", "hrs_machinery_line.total_machine_cost")
    def _compute_totals(self):
        for record in self:
            record.total_hours = sum(record.hrs_machinery_line.mapped("hrs_maquina"))
            record.total_cost = sum(record.hrs_machinery_line.mapped("total_machine_cost"))

    def action_draft(self):
        self.filtered(lambda r: r.state != "accounted").write({"state": "draft"})

    def action_progress(self):
        self.write({"state": "progress"})

    def action_listo(self):
        for record in self:
            if not record.hrs_machinery_line:
                raise UserError(_("Agregue al menos una línea de horas máquina."))
        self.write({"state": "done"})

    def action_cost(self):
        for record in self:
            if record.state not in ("done", "costed"):
                raise UserError(_("El registro debe estar Listo antes de costear."))
            if not record.hrs_machinery_line:
                raise UserError(_("No hay líneas para costear."))
            for line in record.hrs_machinery_line:
                line._apply_standard_cost()
            record.write({"state": "costed", "progress_cost": True})
        return True

    @staticmethod
    def _distribution(*accounts):
        """Arma la distribución al 100 % con una cuenta por plan analítico.

        Odoo rechaza una distribución con dos cuentas del mismo plan raíz. Hay
        registros antiguos cuyo "Centro de costos" apunta a una cuenta de otro
        plan (Temporada o Project), así que gana la primera cuenta recibida y
        las que repiten plan se descartan en vez de reventar la
        contabilización.
        """
        ids = []
        plans = set()
        for account in accounts:
            if not account or account.id in ids:
                continue
            plan = account.root_plan_id or account.plan_id
            if plan.id in plans:
                continue
            plans.add(plan.id)
            ids.append(account.id)
        return {",".join(str(item) for item in ids): 100.0} if ids else False

    def _debit_analytic_distribution(self, line):
        """Distribución analítica del cargo, un segmento por plan analítico.

        Los planes definidos en la contabilidad son Temporada, Centro de costos
        y Actividad, y cada uno se toma de donde el usuario lo captura:

        * **Temporada**: encabezado del registro de horas máquina.
        * **Centro de costos**: línea de detalle.
        * **Actividad**: línea de detalle, a través de la labor.

        En los tres casos lo que va al apunte es la *cuenta analítica* asociada
        al maestro, nunca el id del maestro. La cuenta de pasivo (el abono) no
        lleva analítica: eso lo resuelve :meth:`action_conta`.
        """
        self.ensure_one()
        return self._distribution(
            self.temp_id.cost_id,
            line.cost_id,
            line.actividad_id.cost_id,
        )

    def action_conta(self):
        Service = self.env["type.service.machinery"]
        for record in self:
            if record.state != "costed":
                raise UserError(_("Primero debe ejecutar el costeo."))
            if record.invoice_id:
                raise UserError(_("Este registro ya tiene un comprobante contable."))
            journal = record.company_id.step_journal_machinery
            if not journal:
                raise UserError(_("Configure el Diario de Maquinarias en Ajustes."))

            services = {}
            candidates = Service.search([
                ("company_id", "in", [False, record.company_id.id])
            ], order="company_id")
            for service in candidates:
                services[service.cod] = service
            grouped = defaultdict(float)
            for line in record.hrs_machinery_line:
                for code, amount in line._cost_components().items():
                    if not amount:
                        continue
                    service = services.get(code)
                    debit_account = service.cargo_account_id if service else False
                    credit_account = (service.abono_account_id if service else False) or journal.default_account_id
                    if not debit_account or not credit_account:
                        raise UserError(_("Faltan cuentas contables para el concepto %s.") % code)
                    debit_distribution = record._debit_analytic_distribution(line)
                    # La cuenta de pasivo no lleva cuenta analítica: sólo los gastos.
                    credit_distribution = False
                    grouped[("debit", debit_account.id, json.dumps(debit_distribution, sort_keys=True))] += amount
                    grouped[("credit", credit_account.id, json.dumps(credit_distribution, sort_keys=True))] += amount

            if not grouped:
                raise UserError(_("El costeo no contiene importes contabilizables."))
            commands = []
            for (side, account_id, distribution_json), amount in sorted(grouped.items()):
                amount = record.currency_id.round(amount)
                commands.append(Command.create({
                    "name": _("Costeo maquinaria %s") % record.name,
                    "account_id": account_id,
                    "debit": amount if side == "debit" else 0.0,
                    "credit": amount if side == "credit" else 0.0,
                    "analytic_distribution": json.loads(distribution_json) or False,
                }))
            move = self.env["account.move"].create({
                "ref": record.name, "date": record.date, "move_type": "entry",
                "journal_id": journal.id, "company_id": record.company_id.id, "line_ids": commands,
            })
            record.write({"invoice_id": move.id, "state": "accounted"})
        return True

    def action_open_account_move(self):
        self.ensure_one()
        if not self.invoice_id:
            return False
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "res_id": self.invoice_id.id, "view_mode": "form", "target": "current"}

    # ------------------------------------------------------------------
    # Correlativo "Número OT" y nombre compuesto
    # ------------------------------------------------------------------
    @api.model
    def _next_ot_number(self, company=None):
        """Entrega el siguiente Número OT para ``company``.

        Se apoya siempre en ``ir.sequence`` (nunca en MAX(id) o conteos) para
        que dos usuarios simultáneos no obtengan el mismo correlativo. Si
        existe una secuencia con el mismo código asociada a la empresa, ésta
        tiene prioridad sobre la secuencia global.
        """
        company = company or self.env.company
        Sequence = self.env["ir.sequence"].sudo().with_company(company)
        return Sequence.next_by_code(OT_SEQUENCE_CODE)

    @api.model
    def _name_trigger_fields(self):
        """Campos que, al cambiar, obligan a recomponer el nombre visible.

        Los módulos que aporten segmentos al nombre extienden esta lista.
        """
        return {"date", "folio", "ot_number", "company_id"}

    def _name_segments(self):
        """Segmentos opcionales del nombre compuesto.

        Cada módulo que aporte un dato al nombre extiende este método; los
        segmentos vacíos simplemente no se agregan, de modo que nunca queden
        textos ``False``/``None``, guiones huérfanos ni dobles espacios.
        """
        self.ensure_one()
        segments = []
        folio = (self.folio or "").strip()
        if folio:
            segments.append("OT %s" % folio)
        return segments

    def _compose_name(self):
        """Construye el nombre visible: ``{Número OT} {dd/MM/yyyy} OT {OT} – OT_BPA {folio}``."""
        self.ensure_one()
        head = [(self.ot_number or "").strip()]
        if self.date:
            head.append(self.date.strftime(NAME_DATE_FORMAT))
        segments = [segment.strip() for segment in self._name_segments() if segment and segment.strip()]
        parts = [" ".join(part for part in head if part)]
        if segments:
            parts.append(NAME_SEGMENT_SEPARATOR.join(segments))
        return " ".join(part for part in parts if part)

    def _name_is_frozen(self):
        """Un registro costeado o contabilizado conserva su identidad histórica."""
        self.ensure_one()
        return self.state in ("costed", "accounted") or bool(self.invoice_id)

    def _sync_composed_name(self):
        """Recalcula ``name`` en servidor evitando recursión en create/write."""
        for record in self:
            has_name = bool(record.name) and record.name != NAME_PLACEHOLDER
            if has_name and record._name_is_frozen():
                continue
            composed = record._compose_name()
            if composed and composed != record.name:
                super(StepHrsMachinery, record).write({"name": composed})
        return True

    @staticmethod
    def _pop_supplied_name(vals):
        """Acepta ``name`` de cargas antiguas sin dejar que suplante al correlativo."""
        supplied = vals.pop("name", False)
        if isinstance(supplied, str):
            supplied = supplied.strip()
        if supplied and supplied != NAME_PLACEHOLDER and not vals.get("legacy_name"):
            vals["legacy_name"] = supplied
        return supplied

    def _check_company_change(self, company_id):
        """Política de cambio de empresa: sólo antes de confirmar el registro."""
        for record in self:
            if not company_id or record.company_id.id == company_id:
                continue
            if record.state != "draft" or record.invoice_id:
                raise UserError(_(
                    "No es posible cambiar la empresa del registro %s: sólo se permite "
                    "mientras está en estado Nuevo y sin comprobante contable."
                ) % (record.name or record.ot_number or record.id))

    def _reissue_ot_number(self):
        """Reemite el correlativo tras un cambio de empresa aún permitido."""
        for record in self:
            new_number = record._next_ot_number(record.company_id)
            if new_number:
                super(StepHrsMachinery, record).write({"ot_number": new_number})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._pop_supplied_name(vals)
            # El correlativo lo asigna siempre el servidor: formulario, importación,
            # RPC, BPA o Steps Tracker obtienen el mismo tratamiento.
            vals.pop("ot_number", None)
            company_id = vals.get("company_id")
            company = self.env["res.company"].browse(company_id) if company_id else self.env.company
            vals["ot_number"] = self._next_ot_number(company)
            vals["name"] = NAME_PLACEHOLDER
        records = super().create(vals_list)
        records._sync_composed_name()
        return records

    def write(self, vals):
        vals = dict(vals)
        self._pop_supplied_name(vals)
        vals.pop("ot_number", None)
        company_id = vals.get("company_id")
        moved = self.browse()
        if company_id:
            self._check_company_change(company_id)
            moved = self.filtered(lambda record: record.company_id.id != company_id)
        result = super().write(vals)
        # El correlativo pertenece a la empresa: si el registro cambia de empresa
        # mientras sigue en Nuevo, se emite un número de la secuencia destino.
        moved._reissue_ot_number()
        if not self._name_trigger_fields().isdisjoint(vals):
            self._sync_composed_name()
        return result
