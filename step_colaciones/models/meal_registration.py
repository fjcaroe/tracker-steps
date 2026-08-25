from collections import defaultdict
from datetime import datetime
import json

import pytz
from dateutil.relativedelta import relativedelta

from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date


class StepColacionRegistration(models.Model):
    _name = "step.colacion.registration"
    _description = "Registro de colación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_datetime desc, id desc"

    name = fields.Char(string="Registro", required=True, copy=False, readonly=True, default="/", index=True)
    event_datetime = fields.Datetime(string="Fecha y hora", required=True, default=fields.Datetime.now, tracking=True, index=True)
    received_datetime = fields.Datetime(string="Recibido en servidor", required=True, default=fields.Datetime.now, readonly=True)
    meal_date = fields.Date(
        string="Día de colación",
        required=True,
        compute="_compute_meal_date",
        store=True,
        precompute=True,
        index=True,
    )
    employee_id = fields.Many2one("hr.employee", string="Trabajador", required=True, tracking=True, index=True)
    employee_name_snapshot = fields.Char(string="Nombre registrado", required=True, readonly=True)
    department_id = fields.Many2one("hr.department", string="Departamento", readonly=True, index=True)
    identifier_method = fields.Selection(
        [("manual", "Manual"), ("barcode", "Código de barras"), ("pin", "NIP"), ("nfc", "NFC")],
        string="Identificación",
        required=True,
        default="manual",
        readonly=True,
    )
    identifier_masked = fields.Char(string="Identificador utilizado", readonly=True, groups="step_colaciones.group_colaciones_manager")
    product_tmpl_id = fields.Many2one(
        "product.template", string="Producto", required=True, tracking=True,
        domain="[('is_meal', '=', True)]", index=True,
    )
    supplier_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, tracking=True,
        domain="[('is_meal_supplier', '=', True)]", index=True,
    )
    quantity = fields.Integer(default=1, required=True, readonly=True)
    totem_id = fields.Many2one("step.colacion.totem", string="Tótem", ondelete="restrict", index=True)
    source = fields.Selection(
        [("manual", "Ingreso manual"), ("totem_online", "Tótem en línea"), ("totem_offline", "Tótem sincronizado")],
        string="Origen", default="manual", required=True, readonly=True, index=True,
    )
    state = fields.Selection(
        [
            ("entered", "Ingresado"),
            ("validated", "Validado"),
            ("costed", "Costeado"),
            ("accounted", "Contabilizado"),
            ("cancelled", "Anulado"),
        ],
        string="Estado", default="entered", required=True, tracking=True, index=True,
    )
    tariff_line_id = fields.Many2one("step.colacion.tariff.line", string="Tarifa aplicada", readonly=True, ondelete="restrict")
    currency_id = fields.Many2one("res.currency", readonly=True)
    unit_cost = fields.Monetary(string="Costo unitario", currency_field="currency_id", readonly=True, tracking=True)
    total_cost = fields.Monetary(string="Costo total", currency_field="currency_id", readonly=True, tracking=True)
    expense_account_id = fields.Many2one(
        "account.account", string="Cuenta de gasto", readonly=True, check_company=True,
    )
    provision_account_id = fields.Many2one(
        "account.account", string="Cuenta de provisión", readonly=True, check_company=True,
    )
    provision_journal_id = fields.Many2one(
        "account.journal", string="Diario de provisión", readonly=True, check_company=True,
    )
    analytic_distribution = fields.Json(
        string="Distribución analítica aplicada", readonly=True, copy=False,
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get("Percentage Analytic"),
    )
    analytic_source = fields.Selection(
        [
            ("fixed", "Fija del trabajador"),
            ("dynamic", "Dinámica por horas"),
            ("fixed_fallback", "Fija por falta de horas"),
            ("none", "Sin distribución"),
        ],
        string="Origen analítico",
        readonly=True,
        copy=False,
    )
    analytic_fallback_used = fields.Boolean(
        string="Se utilizó respaldo fijo", readonly=True, copy=False,
    )
    analytic_warning = fields.Char(string="Advertencia analítica", readonly=True, copy=False)
    account_move_id = fields.Many2one(
        "account.move", string="Comprobante contable", readonly=True, copy=False, index=True,
        check_company=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True,
    )
    company_currency_amount = fields.Monetary(
        string="Costo en moneda compañía", currency_field="company_currency_id", readonly=True,
        copy=False,
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    client_uuid = fields.Char(string="ID de sincronización", copy=False, readonly=True, index=True)
    notes = fields.Text(string="Observaciones")
    legacy_ref = fields.Char(copy=False, index=True)

    _sql_constraints = [
        (
            "employee_product_day_unique",
            "unique(employee_id, product_tmpl_id, meal_date, company_id)",
            "El trabajador ya tiene registrada esta misma colación durante el día.",
        ),
        ("client_uuid_unique", "unique(client_uuid)", "Este registro del tótem ya fue sincronizado."),
        ("legacy_ref_unique", "unique(legacy_ref)", "El registro de origen ya fue migrado."),
        ("quantity_one", "check(quantity = 1)", "Cada registro debe representar exactamente una colación."),
    ]

    @api.model
    def _meal_date_for(self, event_datetime, company):
        event_datetime = fields.Datetime.to_datetime(event_datetime)
        if not event_datetime:
            return False
        timezone_name = company.resource_calendar_id.tz or company.partner_id.tz or "UTC"
        try:
            company_tz = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            company_tz = pytz.UTC
        aware = pytz.UTC.localize(event_datetime) if event_datetime.tzinfo is None else event_datetime.astimezone(pytz.UTC)
        return aware.astimezone(company_tz).date()

    @api.depends("event_datetime", "company_id")
    def _compute_meal_date(self):
        for record in self:
            record.meal_date = self._meal_date_for(record.event_datetime, record.company_id) if record.event_datetime and record.company_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            company = self.env["res.company"].browse(values.get("company_id")) if values.get("company_id") else self.env.company
            employee = self.env["hr.employee"].browse(values.get("employee_id"))
            if employee:
                values.setdefault("employee_name_snapshot", employee.name)
                values.setdefault("department_id", employee.department_id.id)
                values.setdefault("company_id", employee.company_id.id or company.id)
            if values.get("name", "/") == "/":
                values["name"] = self.env["ir.sequence"].next_by_code("step.colacion.registration") or "/"
        return super().create(vals_list)

    def write(self, vals):
        protected = {"employee_id", "product_tmpl_id", "supplier_id", "event_datetime", "company_id", "quantity"}
        if protected.intersection(vals) and any(record.state != "entered" for record in self):
            raise UserError(_("No puede modificar los datos principales de una colación validada o anulada."))
        if "employee_id" in vals:
            employee = self.env["hr.employee"].browse(vals["employee_id"])
            vals.setdefault("employee_name_snapshot", employee.name)
            vals.setdefault("department_id", employee.department_id.id)
        return super().write(vals)

    @api.constrains("employee_id", "company_id")
    def _check_employee_company(self):
        for record in self:
            if record.employee_id.company_id != record.company_id:
                raise ValidationError(_("El trabajador y el registro deben pertenecer a la misma empresa."))

    def action_validate(self):
        Tariff = self.env["step.colacion.tariff"]
        for record in self:
            if record.state != "entered":
                continue
            rate = Tariff.find_rate(record.product_tmpl_id, record.supplier_id, record.company_id, record.meal_date)
            if not rate:
                raise UserError(_(
                    "No existe una tarifa vigente para %(product)s, proveedor %(supplier)s, el %(date)s.",
                    product=record.product_tmpl_id.display_name,
                    supplier=record.supplier_id.display_name,
                    date=fields.Date.to_string(record.meal_date),
                ))
            record.write({
                "tariff_line_id": rate.id,
                "currency_id": rate.currency_id.id,
                "unit_cost": rate.price,
                "total_cost": rate.price * record.quantity,
                "state": "validated",
            })
        return True

    def _fixed_analytic_distribution(self):
        self.ensure_one()
        return dict(self.employee_id.meal_analytic_distribution or {})

    def _dynamic_analytic_distribution(self):
        """Distribuye por horas de Actividades sin exigir ese addon.

        Cuando `step_hr` está instalado se usan las tarjas autorizadas del día.
        Cada combinación conserva las dimensiones disponibles: temporada,
        centro de costos y actividad. Otros addons pueden heredar este método
        para registrar una fuente equivalente.
        """
        self.ensure_one()
        if "step.tarja.line" not in self.env.registry.models:
            return {}
        Line = self.env["step.tarja.line"].with_company(self.company_id)
        domain = [
            ("employee_id", "=", self.employee_id.id),
            ("date", "=", self.meal_date),
        ]
        if "company_id" in Line._fields:
            domain.append(("company_id", "=", self.company_id.id))
        if "state" in Line._fields:
            domain.append(("state", "in", ("auto", "costo", "conta")))
        lines = Line.search(domain)
        if not lines:
            return {}

        season_account = self.env["account.analytic.account"]
        if "step.temporada" in self.env.registry.models:
            Season = self.env["step.temporada"].with_company(self.company_id)
            season = Season.search([
                ("company_id", "=", self.company_id.id),
                ("start_date", "<=", self.meal_date),
                ("end_date", ">=", self.meal_date),
            ], order="start_date desc, id desc", limit=1)
            season_account = season.cost_id

        hours_by_key = defaultdict(float)
        for line in lines:
            hours = float(getattr(line, "hrs_total", 0.0) or 0.0)
            if not hours:
                hours = float(getattr(line, "hrs", 0.0) or 0.0) + float(
                    getattr(line, "hrs_extra", 0.0) or 0.0
                )
            if hours <= 0:
                continue
            accounts = season_account
            cost = getattr(line, "cost_id", self.env["account.analytic.account"])
            if cost:
                accounts |= cost
            labor = getattr(line, "labor_id", False)
            activity = labor and getattr(labor, "actividad_id", False)
            if activity:
                accounts |= activity
            accounts = accounts.filtered(
                lambda account: not account.company_id or account.company_id == self.company_id
            )
            if not accounts:
                continue
            key = ",".join(str(account_id) for account_id in sorted(accounts.ids))
            hours_by_key[key] += hours

        total_hours = sum(hours_by_key.values())
        if not total_hours:
            return {}
        distribution = {}
        keys = sorted(hours_by_key)
        assigned = 0.0
        for key in keys[:-1]:
            percent = round(hours_by_key[key] * 100.0 / total_hours, 2)
            distribution[key] = percent
            assigned += percent
        distribution[keys[-1]] = round(100.0 - assigned, 2)
        return distribution

    def _notify_dynamic_fallback(self):
        self.ensure_one()
        responsible = self.company_id.colaciones_accounting_responsible_id
        summary = _("Colación con distribución dinámica sin horas")
        note = _(
            "El registro %(registration)s no encontró horas de Actividades para "
            "el día %(date)s. Se utilizó la distribución fija del trabajador.",
            registration=self.name,
            date=fields.Date.to_string(self.meal_date),
        )
        if responsible and responsible.active:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=responsible.id,
                summary=summary,
                note=note,
            )
        else:
            self.message_post(body=note, message_type="notification")

    def _resolve_costing_values(self):
        self.ensure_one()
        company = self.company_id
        journal = company.colaciones_provision_journal_id
        if not journal:
            raise UserError(_(
                "Configure el diario de provisión en Colaciones > Configuración > Ajustes."
            ))
        provision_account = journal.default_account_id
        if not provision_account:
            raise UserError(_(
                "El diario %(journal)s no tiene cuenta predeterminada para el abono.",
                journal=journal.display_name,
            ))
        expense_account = self.product_tmpl_id.with_company(company).get_product_accounts().get("expense")
        if not expense_account:
            raise UserError(_(
                "Configure la cuenta de gastos en el producto %(product)s o en su categoría.",
                product=self.product_tmpl_id.display_name,
            ))
        if company not in expense_account.company_ids or company not in provision_account.company_ids:
            raise UserError(_("Las cuentas de cargo y abono deben estar habilitadas para la compañía."))

        mode = self.employee_id.meal_distribution_mode or "fixed"
        fallback = False
        if mode == "dynamic":
            distribution = self._dynamic_analytic_distribution()
            source = "dynamic"
            if not distribution:
                distribution = self._fixed_analytic_distribution()
                source = "fixed_fallback"
                fallback = True
                if not distribution:
                    raise UserError(_(
                        "No hay horas de Actividades ni una distribución fija configurada "
                        "para el trabajador."
                    ))
        else:
            distribution = self._fixed_analytic_distribution()
            source = "fixed" if distribution else "none"
        company_amount = self.currency_id._convert(
            self.total_cost,
            company.currency_id,
            company,
            self.meal_date,
        )
        return {
            "expense_account_id": expense_account.id,
            "provision_account_id": provision_account.id,
            "provision_journal_id": journal.id,
            "analytic_distribution": distribution or False,
            "analytic_source": source,
            "analytic_fallback_used": fallback,
            "analytic_warning": (
                _("Sin horas del día: se aplicó la distribución fija.") if fallback else False
            ),
            "company_currency_amount": company_amount,
        }

    def action_cost(self):
        if not self.env.su and not self.env.user.has_group("step_colaciones.group_colaciones_manager"):
            raise UserError(_("Sólo un Administrador de Colaciones puede costear registros."))
        for record in self:
            if record.state == "entered":
                record.action_validate()
            if record.state != "validated":
                continue
            values = record._resolve_costing_values()
            record.write({**values, "state": "costed"})
            if values["analytic_fallback_used"]:
                record._notify_dynamic_fallback()
        return True

    def _accounting_group_key(self):
        self.ensure_one()
        return (self.company_id, self.provision_journal_id, self.meal_date)

    def action_account(self):
        if not self.env.su and not self.env.user.has_group("step_colaciones.group_colaciones_manager"):
            raise UserError(_("Sólo un Administrador de Colaciones puede contabilizar registros."))
        if not self.env.su and not self.env.user.has_group("account.group_account_user"):
            raise UserError(_("También necesita permiso de Contabilidad para generar el comprobante."))
        if not self:
            return True
        self.env.cr.execute(
            "SELECT id FROM step_colacion_registration WHERE id = ANY(%s) FOR UPDATE",
            [self.ids],
        )
        self.invalidate_recordset()
        invalid = self.filtered(lambda record: record.state != "costed" or record.account_move_id)
        if invalid:
            raise UserError(_("Sólo se pueden contabilizar registros Costeados y sin comprobante previo."))

        moves = self.env["account.move"]
        grouped = defaultdict(lambda: self.env["step.colacion.registration"])
        for record in self:
            grouped[record._accounting_group_key()] |= record
        for (company, journal, meal_date), registrations in grouped.items():
            debit_groups = defaultdict(lambda: {"balance": 0.0, "amount_currency": 0.0, "records": self.env["step.colacion.registration"]})
            credit_groups = defaultdict(lambda: {"balance": 0.0, "amount_currency": 0.0, "records": self.env["step.colacion.registration"]})
            for record in registrations:
                distribution_json = json.dumps(record.analytic_distribution or {}, sort_keys=True)
                debit_key = (
                    record.expense_account_id.id,
                    distribution_json,
                    record.currency_id.id,
                )
                credit_key = (
                    record.provision_account_id.id,
                    record.supplier_id.id,
                    record.currency_id.id,
                )
                debit_groups[debit_key]["balance"] += record.company_currency_amount
                debit_groups[debit_key]["amount_currency"] += record.total_cost
                debit_groups[debit_key]["records"] |= record
                credit_groups[credit_key]["balance"] += record.company_currency_amount
                credit_groups[credit_key]["amount_currency"] += record.total_cost
                credit_groups[credit_key]["records"] |= record

            line_commands = []
            for (account_id, distribution_json, currency_id), values in debit_groups.items():
                currency = self.env["res.currency"].browse(currency_id)
                vals = {
                    "name": _("Colaciones %(date)s (%(count)s)", date=meal_date, count=len(values["records"])),
                    "account_id": account_id,
                    "debit": values["balance"],
                    "credit": 0.0,
                    "analytic_distribution": json.loads(distribution_json) or False,
                }
                if currency != company.currency_id:
                    vals.update({"currency_id": currency.id, "amount_currency": values["amount_currency"]})
                line_commands.append(Command.create(vals))
            for (account_id, supplier_id, currency_id), values in credit_groups.items():
                currency = self.env["res.currency"].browse(currency_id)
                vals = {
                    "name": _("Provisión colaciones %(date)s", date=meal_date),
                    "account_id": account_id,
                    "partner_id": supplier_id,
                    "debit": 0.0,
                    "credit": values["balance"],
                }
                if currency != company.currency_id:
                    vals.update({"currency_id": currency.id, "amount_currency": -values["amount_currency"]})
                line_commands.append(Command.create(vals))
            move = self.env["account.move"].with_company(company).create({
                "move_type": "entry",
                "journal_id": journal.id,
                "date": meal_date,
                "ref": _("Provisión de colaciones %(date)s", date=meal_date),
                "line_ids": line_commands,
            })
            registrations.write({"account_move_id": move.id, "state": "accounted"})
            for registration in registrations:
                registration.message_post(
                    body=_("Comprobante contable generado: %(move)s", move=move.display_name),
                    message_type="notification",
                )
            moves |= move
        if len(moves) == 1:
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": moves.id,
                "view_mode": "form",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Comprobantes de colaciones"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }

    def action_open_account_move(self):
        self.ensure_one()
        if not self.account_move_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.account_move_id.id,
            "view_mode": "form",
        }

    def action_cancel(self):
        if any(record.account_move_id for record in self):
            raise UserError(_(
                "No puede anular una colación contabilizada. Revierta primero el comprobante contable."
            ))
        self.write({"state": "cancelled"})

    def action_reset_entered(self):
        if not self.env.su and not self.env.user.has_group("step_colaciones.group_colaciones_manager"):
            raise UserError(_("Solo un administrador de Colaciones puede reabrir el registro."))
        if any(record.account_move_id for record in self):
            raise UserError(_("No se puede reabrir un registro con comprobante contable."))
        self.write({
            "state": "entered",
            "tariff_line_id": False,
            "currency_id": False,
            "unit_cost": 0,
            "total_cost": 0,
            "expense_account_id": False,
            "provision_account_id": False,
            "provision_journal_id": False,
            "analytic_distribution": False,
            "analytic_source": False,
            "analytic_fallback_used": False,
            "analytic_warning": False,
            "company_currency_amount": 0,
        })

    def unlink(self):
        if any(record.state != "entered" for record in self):
            raise UserError(_("Solo se pueden eliminar registros en estado Ingresado."))
        return super().unlink()

    def _totem_response(self, duplicate=False):
        self.ensure_one()
        return {
            "ok": not duplicate,
            "duplicate": duplicate,
            "terminal": True,
            "registration": self.name,
            "employee": self.employee_name_snapshot,
            "product": self.product_tmpl_id.display_name,
            "event_datetime": fields.Datetime.to_string(self.event_datetime),
            "message": _("La colación ya estaba registrada hoy.") if duplicate else _("Colación registrada correctamente."),
        }

    @api.model
    def _dashboard_period(self, period):
        today = fields.Date.context_today(self)
        if period:
            try:
                year, month = str(period).split("-")[:2]
                return today.replace(year=int(year), month=int(month), day=1)
            except (TypeError, ValueError):
                pass
        return today.replace(day=1)

    def _dashboard_periods(self, selected):
        base_domain = [("company_id", "in", self.env.companies.ids)]
        months = set()
        for month_start, _count in self._read_group(
            base_domain, ["meal_date:month"], ["__count"]
        ):
            if month_start:
                months.add(month_start.replace(day=1))
        current = fields.Date.context_today(self).replace(day=1)
        months.update({current, current - relativedelta(months=1), selected})
        ordered = sorted(months, reverse=True)[:24]
        if selected not in ordered:
            ordered = sorted(set(ordered) | {selected}, reverse=True)
        return [
            {
                "value": month.strftime("%Y-%m"),
                "label": format_date(self.env, month, date_format="MMMM y").capitalize(),
            }
            for month in ordered
        ]

    @api.model
    def get_dashboard_data(self, period=None):
        today = fields.Date.context_today(self)
        month_start = self._dashboard_period(period)
        month_end = month_start + relativedelta(months=1, days=-1)
        base_domain = [("company_id", "in", self.env.companies.ids)]
        period_domain = base_domain + [
            ("meal_date", ">=", month_start),
            ("meal_date", "<=", month_end),
        ]
        entered = self.search_count(period_domain + [("state", "=", "entered")])
        valued = self.search(period_domain + [("state", "in", ("validated", "costed", "accounted"))])
        total_period = self.search_count(period_domain + [("state", "!=", "cancelled")])
        offline_period = self.search_count(period_domain + [("source", "=", "totem_offline")])
        unique_employees = len(set(self.search(period_domain + [("state", "!=", "cancelled")]).mapped("employee_id").ids))
        by_product = self._read_group(
            period_domain + [("state", "!=", "cancelled")],
            ["product_tmpl_id"], ["__count"], order="__count desc", limit=5,
        )
        recent = self.search(period_domain, limit=6, order="event_datetime desc")
        return {
            "date": fields.Date.to_string(today),
            "selected_period": month_start.strftime("%Y-%m"),
            "period": format_date(self.env, month_start, date_format="MMMM y").capitalize(),
            "periods": self._dashboard_periods(month_start),
            "total_period": total_period,
            "entered_period": entered,
            "validated_period": len(valued),
            "costed_period": self.search_count(period_domain + [("state", "=", "costed")]),
            "accounted_period": self.search_count(period_domain + [("state", "=", "accounted")]),
            "validated_cost": sum(valued.mapped("total_cost")),
            "currency": self.env.company.currency_id.symbol,
            "unique_employees": unique_employees,
            "offline_period": offline_period,
            "by_product": [{"name": product.display_name, "count": count} for product, count in by_product],
            "recent": [{
                "id": record.id,
                "name": record.name,
                "employee": record.employee_name_snapshot,
                "product": record.product_tmpl_id.display_name,
                "state": record.state,
                "time": fields.Datetime.to_string(record.event_datetime),
            } for record in recent],
        }
