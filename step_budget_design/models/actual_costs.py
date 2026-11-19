"""Live, reconciled accounting detail; never copy or rewrite journal items."""
import base64
from functools import partial
import io

import xlsxwriter

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import SQL


HEADERS = (
    "Comprobante", "fecha", "cuenta", "producto", "Etiqueta/ glosa", "Cantidad", "UdM",
    "temporada", "centro costos", "actividad", "Debe $", "Haber $", "Debe US$", "Haber US$",
    "categoría producto", "grupo presupuesto", "origen presupuesto",
)
ROLE_FIELDS = {role: "management_actual_%s_plan_id" % role for role in ("season", "center", "activity")}
ROLE_NAMES = {"season": {"temporada"}, "center": {"centro costos", "centro de costos"},
              "activity": {"actividad", "actividades"}}
KEY_FACTOR = 1 << 22  # Stable pairs remain exact in JavaScript for int4 journal IDs.


def default_plan(env, role):
    plans = env["account.analytic.plan"].search([("parent_id", "=", False)])
    languages = {env.lang, "en_US"} | {code for code, label in env["res.lang"].get_installed()}
    matches = plans.filtered(lambda plan: any(
        (plan.with_context(lang=lang).name or "").strip().casefold() in ROLE_NAMES[role]
        for lang in languages if lang
    ))
    return matches.id if len(matches) == 1 else False


class Company(models.Model):
    _inherit = "res.company"

    management_actual_season_plan_id = fields.Many2one(
        "account.analytic.plan", string="Plan analítico de temporada", ondelete="restrict",
        domain="[('parent_id', '=', False)]", default=lambda self: default_plan(self.env, "season"))
    management_actual_center_plan_id = fields.Many2one(
        "account.analytic.plan", string="Plan analítico de centros de costo", ondelete="restrict",
        domain="[('parent_id', '=', False)]", default=lambda self: default_plan(self.env, "center"))
    management_actual_activity_plan_id = fields.Many2one(
        "account.analytic.plan", string="Plan analítico de actividades", ondelete="restrict",
        domain="[('parent_id', '=', False)]", default=lambda self: default_plan(self.env, "activity"))

    @api.constrains(*ROLE_FIELDS.values())
    def _check_actual_cost_plans(self):
        for company in self:
            plans = [company[name] for name in ROLE_FIELDS.values() if company[name]]
            if any(plan.parent_id for plan in plans) or len(set(plan.id for plan in plans)) != len(plans):
                raise ValidationError(_("Seleccione planes raíz distintos para temporada, centro y actividad."))


class ActualCost(models.Model):
    _name = "step.management.actual.cost.report"
    _description = "Costos reales de comprobantes contables"
    _auto = False
    _order = "date desc, move_line_id desc, center_id, id"

    move_line_id = fields.Many2one("account.move.line", string="Apunte contable", readonly=True)
    move_id = fields.Many2one("account.move", string="Comprobante", readonly=True)
    date = fields.Date(string="fecha", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    account_id = fields.Many2one("account.account", string="cuenta", readonly=True)
    product_id = fields.Many2one("product.product", string="producto", readonly=True)
    name = fields.Char(string="Etiqueta/ glosa", readonly=True)
    quantity = fields.Float(string="Cantidad", digits="Product Unit of Measure", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="UdM", readonly=True)
    center_id = fields.Many2one("account.analytic.account", string="centro costos", readonly=True)
    percentage = fields.Float(string="Distribución %", readonly=True, aggregator=False)
    distribution_valid = fields.Boolean(string="Distribución conciliada", readonly=True)
    season_ids = fields.Many2many("account.analytic.account", compute="_compute_dimensions",
        search="_search_seasons", string="temporada", readonly=True,
        domain=lambda self: [("root_plan_id", "in", self.env.companies.mapped(ROLE_FIELDS["season"]).ids)])
    activity_ids = fields.Many2many("account.analytic.account", compute="_compute_dimensions",
        search="_search_activities", string="actividad", readonly=True,
        domain=lambda self: [("root_plan_id", "in", self.env.companies.mapped(ROLE_FIELDS["activity"]).ids)])
    analytic_distribution = fields.Json(related="move_line_id.analytic_distribution", readonly=True)
    category_id = fields.Many2one(related="product_id.categ_id", string="categoría producto", readonly=True)
    group_id = fields.Many2one("step.management.budget.group", compute="_compute_group",
        search="_search_group", string="grupo presupuesto", readonly=True)
    origin_id = fields.Many2one("step.management.budget.origin", compute="_compute_group",
        search="_search_origin", string="origen presupuesto", readonly=True)
    clp_id = fields.Many2one("res.currency", compute="_compute_currency_amounts")
    usd_id = fields.Many2one("res.currency", compute="_compute_currency_amounts")
    debit_clp = fields.Monetary(string="Debe $", currency_field="clp_id", compute="_compute_currency_amounts", aggregator=False)
    credit_clp = fields.Monetary(string="Haber $", currency_field="clp_id", compute="_compute_currency_amounts", aggregator=False)
    debit_usd = fields.Monetary(string="Debe US$", currency_field="usd_id", compute="_compute_currency_amounts", aggregator=False)
    credit_usd = fields.Monetary(string="Haber US$", currency_field="usd_id", compute="_compute_currency_amounts", aggregator=False)
    clp_available = fields.Boolean(compute="_compute_currency_amounts")
    usd_available = fields.Boolean(compute="_compute_currency_amounts")
    fx_note = fields.Char(string="Conversión", compute="_compute_currency_amounts")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(SQL(r"""
          CREATE VIEW %s AS
          WITH RECURSIVE roots AS (
            SELECT id, id root_id FROM account_analytic_plan WHERE parent_id IS NULL
            UNION ALL SELECT p.id, r.root_id FROM account_analytic_plan p JOIN roots r ON r.id=p.parent_id
          )
          SELECT l.id::bigint*4194304+COALESCE(w.center_id,0) id,
            l.id move_line_id,l.move_id,l.date,l.company_id,l.account_id,l.product_id,l.name,
            l.quantity*w.percentage/100.0 quantity,l.product_uom_id uom_id,w.center_id,w.percentage,
            w.distribution_valid,w.season_accounts,w.activity_accounts
          FROM account_move_line l JOIN res_company co ON co.id=l.company_id
          CROSS JOIN LATERAL (
            WITH atoms AS (
              SELECT regexp_replace(d.key,'\s','','g') AS analytic_key,d.value::numeric percentage,
                a.id account_id,r.root_id
              FROM jsonb_each_text(CASE WHEN jsonb_typeof(l.analytic_distribution)='object'
                THEN l.analytic_distribution ELSE '{}'::jsonb END) d
              CROSS JOIN LATERAL regexp_split_to_table(d.key, ',') AS token(account_token)
              JOIN account_analytic_account a ON a.id=CASE WHEN btrim(token.account_token) ~ '^[0-9]+$' THEN btrim(token.account_token)::integer END
              JOIN roots r ON r.id=a.plan_id
            ), centers AS (
              SELECT account_id center_id,SUM(percentage) percentage FROM atoms
              WHERE root_id=co.management_actual_center_plan_id GROUP BY account_id
            ), weights AS (
              SELECT center_id,percentage FROM centers WHERE percentage>0
              UNION ALL SELECT NULL::integer,100-COALESCE(SUM(percentage),0) FROM centers
                HAVING COALESCE(SUM(percentage),0)<100
            )
            SELECT weights.center_id,weights.percentage,
              (SUM(weights.percentage) OVER() BETWEEN 99.99999 AND 100.00001) distribution_valid,
              CASE WHEN cardinality(d.local_seasons)>0 THEN d.local_seasons
                   WHEN cardinality(d.all_seasons)=1 THEN d.all_seasons ELSE ARRAY[]::integer[] END season_accounts,
              CASE WHEN cardinality(d.local_activities)>0 THEN d.local_activities
                   WHEN cardinality(d.all_activities)=1 THEN d.all_activities ELSE ARRAY[]::integer[] END activity_accounts
            FROM weights CROSS JOIN LATERAL (
              SELECT array_agg(DISTINCT a.account_id) FILTER(WHERE a.root_id=co.management_actual_season_plan_id) all_seasons,
                array_agg(DISTINCT a.account_id) FILTER(WHERE a.root_id=co.management_actual_activity_plan_id) all_activities,
                array_agg(DISTINCT a.account_id) FILTER(WHERE a.root_id=co.management_actual_season_plan_id
                  AND (weights.center_id IS NULL OR weights.center_id::text=ANY(string_to_array(a.analytic_key,',')))) local_seasons,
                array_agg(DISTINCT a.account_id) FILTER(WHERE a.root_id=co.management_actual_activity_plan_id
                  AND (weights.center_id IS NULL OR weights.center_id::text=ANY(string_to_array(a.analytic_key,',')))) local_activities
              FROM atoms a
            ) d
          ) w
          WHERE l.parent_state='posted' AND jsonb_typeof(l.analytic_distribution)='object'
            AND l.analytic_distribution <> '{}'::jsonb
        """, SQL.identifier(self._table)))

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        # Fail explicitly before a key can exceed the exact browser integer
        # range; never silently collide or renumber rows when new entries post.
        if self.env["account.analytic.account"].search_count([
            ("id", ">=", KEY_FACTOR),
            ("root_plan_id", "in", self.env.companies.mapped(ROLE_FIELDS["center"]).ids)], limit=1):
            raise UserError(_("El identificador del centro excede el rango del informe. Solicite su ampliación a soporte."))
        source = self.env["account.move.line"]._search([])
        return super()._search(expression.AND([domain, [("move_line_id", "in", source)]]), offset, limit, order)

    def _check_access(self, operation):
        result = super()._check_access(operation)
        if result or operation != "read":
            return result
        if not self.env.user.has_group("step_management_costs.group_management_readonly"):
            return self, partial(AccessError, _("Necesita acceso de consulta a Gestión y Costos y a Contabilidad."))
        source = self.env["account.move.line"]
        if self.ids:
            self.env.cr.execute(SQL("SELECT id,move_line_id FROM %s WHERE id IN %s",
                SQL.identifier(self._table), tuple(self.ids)))
            mapping = dict(self.env.cr.fetchall())
            source = source.browse(set(mapping.values()))
            result = source._check_access("read")
            if result:
                forbidden = set(result[0].ids)
                return self.browse([key for key,value in mapping.items() if value in forbidden]), result[1]
        else:
            result = source._check_access("read")
            if result:
                return self, result[1]
        return None

    def _compute_dimensions(self):
        self.env.cr.execute(SQL("SELECT id,season_accounts,activity_accounts FROM %s WHERE id IN %s",
            SQL.identifier(self._table), tuple(self.ids) or (0,)))
        data = {key: (seasons, activities) for key, seasons, activities in self.env.cr.fetchall()}
        ids = {value for dimensions in data.values() for values in dimensions for value in (values or [])}
        accounts = self.env["account.analytic.account"].search([("id", "in", list(ids))])
        for row in self:
            seasons, activities = data[row.id]
            row.season_ids = accounts.filtered(lambda account: account.id in (seasons or []))
            row.activity_ids = accounts.filtered(lambda account: account.id in (activities or []))

    @api.model
    def _search_dimension(self, role, operator, value):
        text_search = operator in ("like", "ilike", "=like", "=ilike", "not like", "not ilike")
        if text_search:
            selected = self.env["account.analytic.account"].search([
                ("root_plan_id", "in", self.env.companies.mapped(ROLE_FIELDS[role]).ids),
                ("name", operator.replace("not ", ""), value)])
            value = selected.ids
            operator = "not in" if operator.startswith("not ") else "in"
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(_("Use una selección de cuentas analíticas para filtrar."))
        value = list(value) if isinstance(value, (list, tuple, set)) else [value]
        column = "season_accounts" if role == "season" else "activity_accounts"
        ids = [v for v in value if v]
        condition = SQL("%s && %s::integer[]", SQL.identifier(column), ids) if ids or text_search else SQL("cardinality(%s)>0", SQL.identifier(column))
        matched = SQL("SELECT id FROM %s WHERE %s", SQL.identifier(self._table), condition)
        negative = operator in ("!=", "not in")
        if not ids and not text_search:
            negative = not negative
        return [("id", "not in" if negative else "in", matched)]

    @api.model
    def _search_seasons(self, operator, value):
        return self._search_dimension("season", operator, value)

    @api.model
    def _search_activities(self, operator, value):
        return self._search_dimension("activity", operator, value)

    def _compute_group(self):
        for row in self:
            group = row.product_id._get_management_budget_group(row.company_id) if row.product_id else False
            row.group_id = group
            row.origin_id = group.origin_id if group else False

    @api.model
    def _search_master(self, field, operator, value):
        if operator in ("like", "ilike", "=like", "=ilike", "not like", "not ilike"):
            model = "step.management.budget.origin" if field == "origin_id" else "step.management.budget.group"
            value = self.env[model].search([("name", operator.replace("not ", ""), value)]).ids
            operator = "not in" if operator.startswith("not ") else "in"
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(_("Use una selección del maestro presupuestario para filtrar."))
        value = list(value) if isinstance(value, (list, tuple, set)) else [value]
        clauses = []
        for company in self.env.companies:
            groups = self.env["account.move.line"]._read_group([
                ("company_id", "=", company.id), ("parent_state", "=", "posted"),
                ("analytic_distribution", "!=", False)], ["product_id"])
            products = self.env["product.product"].browse([product.id for product, in groups if product])
            def matches_master(product):
                group = product._get_management_budget_group(company)
                return (group.origin_id.id if field == "origin_id" else group.id) in value
            matches = products.filtered(matches_master)
            product_domain = [("product_id", "in", matches.ids)]
            if False in value:
                product_domain = expression.OR([product_domain, [("product_id", "=", False)]])
            clause = expression.AND([[("company_id", "=", company.id)], product_domain])
            clauses.append(clause)
        positive = expression.OR(clauses)
        return ["!"] + positive if operator in ("!=", "not in") else positive

    @api.model
    def _search_group(self, operator, value):
        return self._search_master("group_id", operator, value)

    @api.model
    def _search_origin(self, operator, value):
        return self._search_master("origin_id", operator, value)

    def _target_amounts(self, source, currency):
        if source.company_currency_id == currency:
            return True, source.debit, source.credit
        if source.currency_id == currency:
            return True, max(source.amount_currency, 0), max(-source.amount_currency, 0)
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", currency.id), ("company_id", "in", [False, source.company_id.id]),
            ("name", "<=", source.date)], limit=1)
        if not rate:
            return False, 0, 0
        return True, *(source.company_currency_id._convert(
            amount, currency, source.company_id, source.date) for amount in (source.debit, source.credit))

    def _compute_currency_amounts(self):
        currencies = {key: self.env.ref("base." + key.upper()) for key in ("clp", "usd")}
        self.env.cr.execute(SQL("SELECT id,move_line_id,percentage FROM %s WHERE move_line_id IN %s ORDER BY move_line_id,center_id NULLS LAST",
            SQL.identifier(self._table), tuple(self.move_line_id.ids) or (0,)))
        allocations = {}
        for key, source_id, weight in self.env.cr.fetchall():
            allocations.setdefault(source_id, []).append((key, float(weight)))
        results = {}
        for source in self.move_line_id:
            for key, currency in currencies.items():
                available, debit, credit = self._target_amounts(source, currency)
                rows = allocations[source.id]
                assigned_debit = assigned_credit = 0
                for index, (record_id, weight) in enumerate(rows):
                    last = index == len(rows) - 1
                    d = currency.round(debit - assigned_debit) if last else currency.round(debit * weight / 100)
                    c = currency.round(credit - assigned_credit) if last else currency.round(credit * weight / 100)
                    results[(record_id, key)] = (available, d, c)
                    assigned_debit += d
                    assigned_credit += c
        for row in self:
            missing = []
            for key, currency in currencies.items():
                available, debit, credit = results[(row.id, key)]
                row[key + "_id"] = currency
                row[key + "_available"] = available and row.distribution_valid
                row["debit_" + key] = debit
                row["credit_" + key] = credit
                if not available:
                    missing.append(currency.name)
            row.fx_note = (_("Falta tasa contable: %s") % ", ".join(missing)) if missing else False
            if not row.distribution_valid:
                row.fx_note = _("Revise la distribución analítica del apunte; no concilia al 100%.")

    def action_open_move(self):
        self.ensure_one()
        self.check_access("read")
        self.move_id.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": self.move_id.id,
                "views": [(False, "form")], "target": "current"}

    def action_export_excel(self):
        self.check_access("read")
        if not self:
            raise UserError(_("Seleccione los movimientos que desea exportar. Puede seleccionar todos los resultados del filtro."))
        if self.filtered(lambda row: not row.distribution_valid):
            raise UserError(_("Revise los apuntes cuya distribución analítica no concilia al 100% antes de exportar."))
        export = self.env["step.management.actual.cost.export"].create({
            "file": base64.b64encode(self._excel_bytes()), "filename": "Costos reales.xlsx"})
        return {"type": "ir.actions.act_url", "url": "/web/content/%s/%s/file/%s?download=true" %
                (export._name, export.id, export.filename), "target": "download"}

    def _excel_bytes(self):
        self.check_access("read")
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False})
        sheet = book.add_worksheet("Costos reales")
        title = book.add_format({"bold": True, "font_size": 14, "font_color": "#135F4B"})
        header = book.add_format({"bold": True, "bg_color": "#135F4B", "font_color": "white", "text_wrap": True, "valign": "vcenter"})
        date_format = book.add_format({"num_format": "dd/mm/yyyy"})
        number = book.add_format({"num_format": "#,##0.00"})
        quantity = book.add_format({"num_format": "#,##0.####"})
        total = book.add_format({"num_format": "#,##0.00", "bold": True, "top": 1})
        sheet.write(0, 0, "Costos reales", title)
        sheet.write_row(1, 0, HEADERS, header)
        sheet.set_row(1, 32)
        widths = [24, 12, 34, 30, 42, 12, 12, 20, 30, 26, 18, 18, 18, 18, 26, 26, 26]
        for col, width in enumerate(widths):
            sheet.set_column(col, col, width)
        sums = [0., 0., 0., 0.]
        complete = [True, True, True, True]
        missing = 0
        for index, row in enumerate(self.sorted(lambda record: (record.date, record.move_line_id.id, record.id)), 2):
            values = [row.move_id.name, row.date, row.account_id.display_name, row.product_id.display_name or "",
                row.name or "", row.quantity, row.uom_id.name or "", ", ".join(row.season_ids.mapped("name")),
                row.center_id.display_name or "", ", ".join(row.activity_ids.mapped("name")),
                row.debit_clp if row.clp_available else None, row.credit_clp if row.clp_available else None,
                row.debit_usd if row.usd_available else None, row.credit_usd if row.usd_available else None,
                row.category_id.display_name or "", row.group_id.display_name or "", row.origin_id.name or ""]
            for col, value in enumerate(values):
                if value is None:
                    continue
                sheet.write(index, col, value, date_format if col == 1 else quantity if col == 5 else number if 10 <= col <= 13 else None)
            for col in range(4):
                sums[col] += values[col + 10] or 0
                complete[col] &= values[col + 10] is not None
            missing += int(not row.clp_available or not row.usd_available)
        end = len(self) + 2
        sheet.autofilter(1, 0, max(1, end - 1), 16)
        sheet.write(end, 9, "Total", total)
        for col, amount in enumerate(sums, 10):
            letter = xlsxwriter.utility.xl_col_to_name(col)
            if complete[col - 10]:
                sheet.write_formula(end, col, "=SUBTOTAL(109,%s3:%s%s)" % (letter, letter, end), total, amount)
        if missing:
            sheet.write(end + 2, 0, "%s movimiento(s) sin tasa contable: las celdas de esa moneda están vacías." % missing)
        sheet.freeze_panes(2, 2)
        sheet.hide_gridlines(2)
        sheet.set_landscape()
        sheet.set_paper(8)
        sheet.fit_to_pages(1, 0)
        sheet.repeat_rows(0, 1)
        book.close()
        return output.getvalue()


class ActualCostExport(models.TransientModel):
    _name = "step.management.actual.cost.export"
    _description = "Descarga de costos reales"
    file = fields.Binary(readonly=True, attachment=False)
    filename = fields.Char(readonly=True)


class ActualCostPlans(models.TransientModel):
    _name = "step.management.actual.cost.plans"
    _description = "Planes analíticos de costos reales"
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True, readonly=True)
    season_plan_id = fields.Many2one("account.analytic.plan", domain="[('parent_id', '=', False)]")
    center_plan_id = fields.Many2one("account.analytic.plan", domain="[('parent_id', '=', False)]")
    activity_plan_id = fields.Many2one("account.analytic.plan", domain="[('parent_id', '=', False)]")

    @api.model
    def default_get(self, names):
        values = super().default_get(names)
        for role, company_field in ROLE_FIELDS.items():
            values[role + "_plan_id"] = self.env.company[company_field].id
        return values

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.company_id.write({name: self[role + "_plan_id"].id for role, name in ROLE_FIELDS.items()})
        return {"type": "ir.actions.act_window_close"}
