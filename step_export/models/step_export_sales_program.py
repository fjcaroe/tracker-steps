# -*- coding: utf-8 -*-
"""Versioned export sales programme (T35, functional document section 1)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepExportSalesProgram(models.Model):
    _name = "step.export.sales.program"
    _description = "Programa de Ventas de Exportación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, series_code, version desc"
    _check_company_auto = True

    name = fields.Char(string="Programa", required=True, tracking=True)
    series_code = fields.Char(string="Código", required=True, copy=False, readonly=True, default="Nuevo", index=True)
    version = fields.Integer(string="Versión", required=True, default=1, copy=False, readonly=True)
    previous_version_id = fields.Many2one("step.export.sales.program", string="Versión anterior", readonly=True, copy=False)
    state = fields.Selection([
        ("created", "Creado"), ("validated", "Validado"),
        ("current", "Vigente"), ("replaced", "Reemplazado"),
    ], string="Estado", default="created", required=True, copy=False, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    partner_id = fields.Many2one("res.partner", string="Recibidor", required=True, check_company=True)
    season_id = fields.Many2one("step.temporada", string="Temporada", required=True, check_company=True)
    species_id = fields.Many2one("step.especie", string="Especie", required=True)
    variety_group_id = fields.Many2one("step.grupo.variedad", string="Grupo de variedades")
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    fruit_type = fields.Selection([
        ("conventional", "Convencional"), ("organic", "Orgánica"),
    ], string="Tipo de fruta", required=True, default="conventional")
    caliber_range = fields.Char(string="Rango de calibres")
    quality = fields.Char(string="Calidad")
    label = fields.Char(string="Etiqueta comercial")
    product_id = fields.Many2one("product.product", string="Producto de exportación", required=True)
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    package_type_id = fields.Many2one("stock.package.type", string="Tipo de pallet", required=True)
    container_size = fields.Selection([("20", "20 pies"), ("40", "40 pies")], required=True, default="40")
    pallets_per_container = fields.Float(string="Pallets por contenedor", digits=(12, 2))
    boxes_per_pallet = fields.Float(string="Cajas por pallet", digits=(12, 2))
    kg_per_box = fields.Float(string="Kg por caja", digits=(12, 3))
    date_start = fields.Date(string="Desde", required=True)
    date_end = fields.Date(string="Hasta", required=True)
    currency_id = fields.Many2one("res.currency", string="Moneda de venta", required=True,
                                  default=lambda self: self.env.company.currency_id)
    usd_currency_id = fields.Many2one("res.currency", string="USD", required=True,
                                      default=lambda self: self.env.ref("base.USD"))
    rate_to_usd = fields.Float(string="USD por unidad de moneda", digits=(16, 6),
                               help="Tipo de cambio guardado en esta versión; se toma de Contabilidad al crearla.")
    line_ids = fields.One2many("step.export.sales.program.line", "program_id", string="Semanas", copy=True)
    container_qty = fields.Float(string="Contenedores", compute="_compute_totals", store=True)
    pallet_qty = fields.Float(string="Pallets", compute="_compute_totals", store=True)
    box_qty = fields.Float(string="Cajas", compute="_compute_totals", store=True)
    kg_qty = fields.Float(string="Kilos", compute="_compute_totals", store=True)
    amount_currency = fields.Monetary(string="Venta", currency_field="currency_id",
                                      compute="_compute_totals", store=True)
    amount_usd = fields.Monetary(string="Venta USD", currency_field="usd_currency_id",
                                 compute="_compute_totals", store=True)

    _sql_constraints = [
        ("series_version_unique", "unique(company_id, series_code, version)",
         "La versión ya existe para este programa y empresa."),
        ("version_positive", "check(version > 0)", "La versión debe ser positiva."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("series_code", "Nuevo") == "Nuevo":
                vals["series_code"] = sequence.next_by_code("step.export.sales.program") or "Nuevo"
            if not vals.get("rate_to_usd"):
                currency = self.env["res.currency"].browse(vals.get("currency_id")) if vals.get("currency_id") else self.env.company.currency_id
                company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
                usd = self.env.ref("base.USD")
                vals["rate_to_usd"] = currency._convert(1.0, usd, company, vals.get("date_start") or fields.Date.today())
        return super().create(vals_list)

    @api.onchange("currency_id", "date_start")
    def _onchange_exchange_rate(self):
        for record in self:
            if record.currency_id:
                record.rate_to_usd = record.currency_id._convert(
                    1.0, record.env.ref("base.USD"), record.company_id or record.env.company,
                    record.date_start or fields.Date.today())

    @api.onchange("package_type_id", "container_size", "packaging_id")
    def _onchange_packing_quantities(self):
        for record in self:
            if record.package_type_id:
                record.boxes_per_pallet = record.package_type_id.step_export_boxes_per_pallet
                record.pallets_per_container = (
                    record.package_type_id.step_export_pallets_20
                    if record.container_size == "20" else record.package_type_id.step_export_pallets_40)
            if record.packaging_id:
                record.kg_per_box = record.packaging_id.step_export_kg_per_box

    @api.depends("line_ids.container_qty", "line_ids.pallet_qty", "line_ids.box_qty",
                 "line_ids.kg_qty", "line_ids.amount_currency", "line_ids.amount_usd")
    def _compute_totals(self):
        for record in self:
            record.container_qty = sum(record.line_ids.mapped("container_qty"))
            record.pallet_qty = sum(record.line_ids.mapped("pallet_qty"))
            record.box_qty = sum(record.line_ids.mapped("box_qty"))
            record.kg_qty = sum(record.line_ids.mapped("kg_qty"))
            record.amount_currency = sum(record.line_ids.mapped("amount_currency"))
            record.amount_usd = sum(record.line_ids.mapped("amount_usd"))

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError(_("La fecha de término debe ser posterior al inicio."))

    def write(self, vals):
        business_fields = {
            "name", "company_id", "partner_id", "season_id", "species_id", "variety_group_id",
            "variety_id", "fruit_type", "caliber_range", "quality", "label", "product_id",
            "packaging_id", "package_type_id", "container_size", "pallets_per_container",
            "boxes_per_pallet", "kg_per_box", "date_start", "date_end", "currency_id",
            "rate_to_usd", "line_ids",
        }
        if business_fields.intersection(vals) and any(r.state in ("current", "replaced") for r in self):
            raise UserError(_("Cree una versión nueva para modificar un programa vigente o reemplazado."))
        return super().write(vals)

    def action_validate(self):
        for record in self:
            if record.state != "created":
                raise UserError(_("Solo puede validar un programa creado."))
            if not record.line_ids:
                raise ValidationError(_("Ingrese al menos una semana."))
            if min(record.pallets_per_container, record.boxes_per_pallet,
                   record.kg_per_box, record.rate_to_usd) <= 0:
                raise ValidationError(_("Complete las cantidades de embalaje y el tipo de cambio con valores positivos."))
            for line in record.line_ids:
                if line.week_start < record.date_start or line.week_start > record.date_end:
                    raise ValidationError(_("Cada semana debe estar dentro del período del programa."))
                if line.week_start.weekday() != 0:
                    raise ValidationError(_("La semana debe empezar un lunes."))
                if line.container_qty <= 0:
                    raise ValidationError(_("Los contenedores de cada semana deben ser positivos."))
            record.state = "validated"
        return True

    def action_activate(self):
        for record in self:
            if record.state != "validated":
                raise UserError(_("Valide el programa antes de hacerlo vigente."))
            previous = self.search([
                ("company_id", "=", record.company_id.id),
                ("series_code", "=", record.series_code),
                ("state", "=", "current"),
                ("id", "!=", record.id),
            ])
            previous.write({"state": "replaced"})
            record.state = "current"
        return True

    def action_new_version(self):
        self.ensure_one()
        if self.state != "current":
            raise UserError(_("La versión nueva debe partir de un programa vigente."))
        next_version = max(self.search([
            ("company_id", "=", self.company_id.id),
            ("series_code", "=", self.series_code),
        ]).mapped("version")) + 1
        new = self.copy({
            "series_code": self.series_code,
            "version": next_version,
            "previous_version_id": self.id,
            "state": "created",
        })
        return {
            "type": "ir.actions.act_window", "name": _("Nueva versión"),
            "res_model": self._name, "res_id": new.id, "view_mode": "form", "target": "current",
        }


class StepExportSalesProgramLine(models.Model):
    _name = "step.export.sales.program.line"
    _description = "Distribución semanal del programa de ventas"
    _order = "week_start, id"

    program_id = fields.Many2one("step.export.sales.program", required=True, ondelete="cascade", index=True)
    week_start = fields.Date(string="Semana desde", required=True)
    container_qty = fields.Float(string="Contenedores", digits=(12, 2), required=True)
    price_per_kg = fields.Float(string="Precio por kg", digits=(16, 4), required=True)
    pallet_qty = fields.Float(string="Pallets", compute="_compute_quantities", store=True)
    box_qty = fields.Float(string="Cajas", compute="_compute_quantities", store=True)
    kg_qty = fields.Float(string="Kilos", compute="_compute_quantities", store=True)
    currency_id = fields.Many2one(related="program_id.currency_id")
    usd_currency_id = fields.Many2one(related="program_id.usd_currency_id")
    amount_currency = fields.Monetary(string="Venta", currency_field="currency_id",
                                      compute="_compute_quantities", store=True)
    amount_usd = fields.Monetary(string="Venta USD", currency_field="usd_currency_id",
                                 compute="_compute_quantities", store=True)

    _sql_constraints = [
        ("week_unique", "unique(program_id, week_start)", "La semana ya existe en el programa."),
        ("containers_nonnegative", "check(container_qty >= 0)", "Los contenedores no pueden ser negativos."),
        ("price_nonnegative", "check(price_per_kg >= 0)", "El precio no puede ser negativo."),
    ]

    @api.depends("container_qty", "price_per_kg", "program_id.pallets_per_container",
                 "program_id.boxes_per_pallet", "program_id.kg_per_box", "program_id.rate_to_usd")
    def _compute_quantities(self):
        for line in self:
            line.pallet_qty = line.container_qty * line.program_id.pallets_per_container
            line.box_qty = line.pallet_qty * line.program_id.boxes_per_pallet
            line.kg_qty = line.box_qty * line.program_id.kg_per_box
            line.amount_currency = line.kg_qty * line.price_per_kg
            line.amount_usd = line.amount_currency * line.program_id.rate_to_usd

    @api.constrains("week_start")
    def _check_week_start(self):
        for line in self:
            if line.week_start and line.week_start.weekday() != 0:
                raise ValidationError(_("La semana debe empezar un lunes."))

    def _check_editable(self):
        if any(line.program_id.state in ("current", "replaced") for line in self):
            raise UserError(_("Cree una versión nueva para modificar las semanas."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.sales.program"].browse(
            [vals["program_id"] for vals in vals_list if vals.get("program_id")])
        if any(parent.state in ("current", "replaced") for parent in parents):
            raise UserError(_("Cree una versión nueva para modificar las semanas."))
        return super().create(vals_list)

    def write(self, vals):
        if {"week_start", "container_qty", "price_per_kg", "program_id"}.intersection(vals):
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
