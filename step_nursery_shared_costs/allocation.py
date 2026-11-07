import hashlib
import json
from datetime import timedelta

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .masters import OPERATION, OPERATION_KEY, last_closed_week


class CostRun(models.Model):
    _name = "step.nursery.cost.run"
    _description = "Redistribución semanal del vivero"
    _check_company_auto = True
    _order = "week_start desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(related="parent_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    parent_id = fields.Many2one("account.analytic.account", string="Supra centro", required=True,
                                ondelete="restrict", domain="[('step_cost_pool', '=', True)]")
    week_start = fields.Date(string="Semana desde", required=True, default=last_closed_week)
    week_end = fields.Date(string="Hasta", compute="_compute_week_end", store=True)
    state = fields.Selection([("draft", "Borrador"), ("done", "Confirmado"), ("reversed", "Revertido")],
                             default="draft", required=True, copy=False, index=True)
    fingerprint = fields.Char(copy=False)
    line_ids = fields.One2many("step.nursery.cost.run.line", "run_id", string="Detalle del reparto", copy=False)
    item_ids = fields.One2many("account.analytic.line", "step_cost_run_id", string="Movimientos generados", copy=False)
    cost_total = fields.Monetary(string="Costo a distribuir", compute="_compute_cost_total", store=True)
    confirmed_by_id = fields.Many2one("res.users", string="Confirmó", copy=False)
    confirmed_at = fields.Datetime(string="Confirmado el", copy=False)
    reversed_by_id = fields.Many2one("res.users", string="Revirtió", copy=False)
    reversed_at = fields.Datetime(string="Revertido el", copy=False)

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS step_nursery_cost_week_confirmed
            ON step_nursery_cost_run (parent_id, week_start) WHERE state = 'done'
        """)

    @api.depends("parent_id.name", "week_start")
    def _compute_name(self):
        for run in self:
            run.name = f"{run.parent_id.name or ''} · {run.week_start or ''}"

    @api.depends("week_start")
    def _compute_week_end(self):
        for run in self:
            run.week_end = run.week_start + timedelta(days=6) if run.week_start else False

    @api.depends("line_ids.amount")
    def _compute_cost_total(self):
        for run in self:
            run.cost_total = sum(run.line_ids.mapped("amount"))

    @api.constrains("week_start", "parent_id")
    def _check_period(self):
        for run in self:
            if not run.parent_id.step_cost_pool or not run.company_id or run.week_start.weekday() != 0:
                raise ValidationError(_("Seleccione un supra centro y el lunes de la semana."))

    @api.model_create_multi
    def create(self, vals_list):
        protected = {"fingerprint", "line_ids", "item_ids", "confirmed_by_id", "confirmed_at",
                     "reversed_by_id", "reversed_at"}
        for vals in vals_list:
            if protected & vals.keys() or vals.get("state", "draft") != "draft":
                raise AccessError(_("Cree el reparto en borrador y utilice sus acciones."))
        clean_context = {key: value for key, value in self.env.context.items()
                         if key not in {f"default_{field}" for field in protected | {"state"}}}
        return super(CostRun, self.with_context(clean_context)).create(vals_list)

    def write(self, vals):
        if self.env.context.get(OPERATION_KEY) is OPERATION:
            return super().write(vals)
        if self.filtered(lambda run: run.state != "draft") or set(vals) - {"parent_id", "week_start"}:
            raise AccessError(_("El detalle y el estado se gestionan desde las acciones del reparto."))
        result = super().write(vals)
        if vals:
            self.with_context({OPERATION_KEY: OPERATION}).write({
                "fingerprint": False, "line_ids": [Command.clear()],
            })
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_only_drafts(self):
        if self.filtered(lambda run: run.state != "draft"):
            raise UserError(_("Conserve el historial y revierta el reparto si corresponde."))

    def _check_manager(self):
        self.ensure_one()
        self.check_access("write")
        if not self.env.user.has_group("account.group_account_manager"):
            raise AccessError(_("Solo un responsable de Contabilidad puede gestionar el reparto."))

    def _sources(self, column):
        return self.env["account.analytic.line"].search([
            ("company_id", "=", self.company_id.id), (column, "=", self.parent_id.id),
            ("date", ">=", self.week_start), ("date", "<=", self.week_end),
            ("step_cost_run_id", "=", False), ("amount", "!=", 0),
            "|", ("move_line_id", "=", False),
            "&", ("move_line_id.parent_state", "=", "posted"),
            ("general_account_id.account_type", "in", ["expense", "expense_direct_cost", "expense_depreciation"]),
        ], order="id")

    def _driver_weights(self, driver, children):
        if not driver.active or (driver.company_id and driver.company_id != self.company_id):
            raise UserError(_("Revise la empresa y vigencia del driver %s.") % driver.display_name)
        measures = self.env["step.nursery.cost.measure"].search([
            ("week_start", "=", self.week_start), ("center_id", "in", children.ids),
            ("driver_id", "=", driver.id), ("company_id", "=", self.company_id.id),
        ])
        missing = children - measures.center_id
        if missing:
            raise UserError(_("Falta cargar %(driver)s para %(centers)s. Registre cero cuando no haya participación.",
                              driver=driver.display_name, centers=", ".join(missing.mapped("display_name"))))
        quantities = {measure.center_id.id: measure.quantity for measure in measures}
        total = sum(quantities.values())
        if not total:
            raise UserError(_("El total semanal de %s debe ser mayor que cero.") % driver.display_name)
        return [(child.id, quantities[child.id]) for child in children if quantities[child.id]], total

    def _plan(self):
        if not self.parent_id.active or not self.parent_id.step_cost_pool:
            raise UserError(_("Seleccione un supra centro activo."))
        if self.search_count([("parent_id", "=", self.parent_id.id), ("week_start", "=", self.week_start),
                              ("state", "=", "done"), ("id", "!=", self.id)], limit=1):
            raise UserError(_("Esta semana ya tiene un reparto confirmado. Reviértalo para recalcular."))
        children = self.parent_id.step_cost_child_ids.sorted("id")
        if not children:
            raise UserError(_("Asocie al menos un centro hijo al supra centro."))
        column = self.parent_id.plan_id._column_name()
        sources = self._sources(column)
        if not sources:
            raise UserError(_("No hay cargos del supra centro en esta semana."))
        rules = {rule.labor_id.id: rule.driver_id for rule in self.parent_id.step_cost_rule_ids}
        by_driver, rows, source_snapshot = {}, [], []
        for source in sources:
            labor = source.step_cost_labor_id or source.product_id.product_tmpl_id
            driver = rules.get(labor.id)
            if not driver:
                raise UserError(_("Asigne una labor con driver al cargo «%s» antes de repartir.") % source.display_name)
            if driver.id not in by_driver:
                by_driver[driver.id] = self._driver_weights(driver, children)
            weights, total = by_driver[driver.id]
            source_snapshot.append((source.id, source.name, str(source.date), source.amount, source.product_id.id,
                                    source.general_account_id.id, source.partner_id.id, source.move_line_id.id,
                                    [(field, source[field].id) for field in sorted(source._get_plan_fnames())]))
            # Cumulative rounding leaves each currency unit assigned exactly once.
            cumulative, assigned = 0.0, 0.0
            for index, (child_id, weight) in enumerate(weights):
                cumulative += weight
                target = (-source.amount if index == len(weights) - 1
                          else self.currency_id.round(-source.amount * cumulative / total))
                share = target - assigned
                assigned = target
                rows.append({
                    "source_id": source.id, "center_id": child_id, "labor_id": labor.id, "driver_id": driver.id,
                    "quantity": weight, "total_quantity": total, "amount": share,
                })
        fingerprint = hashlib.sha256(json.dumps([source_snapshot, rows], sort_keys=True).encode()).hexdigest()
        return sources, rows, fingerprint

    def action_preview(self):
        self._check_manager()
        if self.state != "draft":
            raise UserError(_("Solo puede calcular un reparto en borrador."))
        _sources, rows, fingerprint = self._plan()
        self.with_context({OPERATION_KEY: OPERATION}).write({
            "fingerprint": fingerprint,
            "line_ids": [Command.clear(), *(Command.create(row) for row in rows)],
        })

    def _analytic_values(self, item, center_id, amount, source_id, *, reverse=False):
        accounts = {field: item[field].id for field in item._get_plan_fnames()}
        if center_id:
            accounts[self.parent_id.plan_id._column_name()] = center_id
        label = _("Reversa de reparto") if reverse else _("Reparto semanal")
        return {
            **accounts, "name": f"{label} · {item.name}", "date": item.date,
            "company_id": self.company_id.id, "amount": amount, "unit_amount": 0,
            "partner_id": item.partner_id.id, "product_id": item.product_id.id,
            "general_account_id": item.general_account_id.id,
            "step_cost_run_id": self.id, "step_cost_source_id": source_id,
            "step_cost_is_reversal": reverse,
        }

    def _lock_parent(self):
        self.env.cr.execute("SELECT id FROM account_analytic_account WHERE id = %s FOR UPDATE", [self.parent_id.id])

    def action_confirm(self):
        self._check_manager()
        if self.state != "draft" or not self.fingerprint:
            raise UserError(_("Calcule y revise la vista previa antes de confirmar."))
        self._lock_parent()
        sources, rows, fingerprint = self._plan()
        if fingerprint != self.fingerprint:
            raise UserError(_("Cambió un cargo o una cantidad. Calcule nuevamente el reparto."))
        controlled = {OPERATION_KEY: OPERATION}
        values = [self._analytic_values(source, self.parent_id.id, -source.amount, source.id) for source in sources]
        by_id = {source.id: source for source in sources}
        for row in rows:
            if row["amount"]:
                source = by_id[row["source_id"]]
                values.append(self._analytic_values(source, row["center_id"], -row["amount"], source.id))
        self.with_context(controlled).write({
            "state": "done", "confirmed_by_id": self.env.uid, "confirmed_at": fields.Datetime.now(),
        })
        sources.with_context(controlled).write({"step_cost_active_run_id": self.id})
        self.env["account.analytic.line"].with_context(controlled).create(values)

    def action_reverse(self):
        self._check_manager()
        if self.state != "done":
            raise UserError(_("Solo puede revertir un reparto confirmado."))
        self._lock_parent()
        controlled = {OPERATION_KEY: OPERATION}
        original = self.item_ids
        self.env["account.analytic.line"].with_context(controlled).create([
            self._analytic_values(item, False, -item.amount, item.step_cost_source_id.id, reverse=True)
            for item in original
        ])
        self.line_ids.source_id.with_context(controlled).write({"step_cost_active_run_id": False})
        self.with_context(controlled).write({
            "state": "reversed", "reversed_by_id": self.env.uid, "reversed_at": fields.Datetime.now(),
        })

    def action_items(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window", "name": _("Movimientos del reparto"),
            "res_model": "account.analytic.line", "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("step_cost_run_id", "=", self.id)],
            "context": {"analytic_plan_id": self.parent_id.plan_id.id, "create": False},
        }


class CostRunLine(models.Model):
    _name = "step.nursery.cost.run.line"
    _description = "Detalle auditable del reparto semanal"
    _check_company_auto = True
    _order = "source_id, center_id"

    run_id = fields.Many2one("step.nursery.cost.run", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="run_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="run_id.currency_id")
    source_id = fields.Many2one("account.analytic.line", string="Cargo original", ondelete="set null",
                                check_company=True, index=True)
    center_id = fields.Many2one("account.analytic.account", string="Centro hijo", required=True,
                                ondelete="restrict", check_company=True)
    labor_id = fields.Many2one("product.template", string="Labor", required=True,
                               ondelete="restrict", check_company=True)
    driver_id = fields.Many2one("step.sawmill.costing.driver", string="Driver", required=True,
                                ondelete="restrict", check_company=True)
    quantity = fields.Float(string="Cantidad del hijo", digits=(16, 4))
    total_quantity = fields.Float(string="Total driver", digits=(16, 4))
    amount = fields.Monetary(string="Costo asignado")

    def _check_generated(self):
        if self.env.context.get(OPERATION_KEY) is not OPERATION:
            raise AccessError(_("El detalle se obtiene al calcular el reparto."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_generated()
        return super().create(vals_list)

    def write(self, vals):
        self._check_generated()
        return super().write(vals)

    def unlink(self):
        self._check_generated()
        return super().unlink()
