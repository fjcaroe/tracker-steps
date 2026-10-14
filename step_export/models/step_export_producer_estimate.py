# -*- coding: utf-8 -*-
"""Producer fruit estimates and their weekly export forecast (T35 section 3)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class StepExportProducerEstimate(models.Model):
    _inherit = "step.export.estimate"

    series_code = fields.Char(string="Código", copy=False, readonly=True, index=True)
    version_number = fields.Integer(string="Versión", default=1, copy=False, readonly=True)
    previous_version_id = fields.Many2one("step.export.estimate", string="Versión anterior", copy=False, readonly=True)
    state = fields.Selection([
        ("created", "Creada"), ("validated", "Validada"),
        ("current", "Vigente"), ("replaced", "Reemplazada"),
    ], default="created", required=True, tracking=True, copy=False)
    producer_id = fields.Many2one("res.partner", string="Productor", check_company=True)
    packing_partner_id = fields.Many2one("res.partner", string="Packing o planta", check_company=True)
    delivery_start = fields.Date(string="Entrega desde")
    delivery_end = fields.Date(string="Entrega hasta")
    estimate_line_ids = fields.One2many(
        "step.export.estimate.line", "estimate_id", string="Detalle de fruta", copy=True)
    export_kg_total = fields.Float(string="Kilos de exportación", compute="_compute_export_kg_total", store=True)

    _sql_constraints = [
        ("estimate_series_version_unique", "unique(company_id, series_code, version_number)",
         "Ya existe esta versión de la estimación."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("series_code"):
                vals["series_code"] = self.env["ir.sequence"].next_by_code("step.export.estimate") or "EP/Nuevo"
            vals.setdefault("estimate_version", str(vals.get("version_number", 1)))
        return super().create(vals_list)

    @api.depends("estimate_line_ids.export_kg")
    def _compute_export_kg_total(self):
        for record in self:
            record.export_kg_total = sum(record.estimate_line_ids.mapped("export_kg"))

    @api.constrains("delivery_start", "delivery_end")
    def _check_delivery_dates(self):
        for record in self:
            if record.delivery_start and record.delivery_end and record.delivery_end < record.delivery_start:
                raise ValidationError(_("La fecha final de entrega debe ser posterior al inicio."))

    def write(self, vals):
        business_fields = {
            "name", "producer_id", "fundo_id", "packing_partner_id", "season_id",
            "delivery_start", "delivery_end", "estimate_line_ids", "company_id",
        }
        if business_fields.intersection(vals) and any(r.state in ("current", "replaced") for r in self):
            raise UserError(_("Cree otra versión para modificar una estimación vigente o reemplazada."))
        return super().write(vals)

    def action_validate_estimate(self):
        for record in self:
            if record.state != "created":
                raise UserError(_("Solo puede validar una estimación creada."))
            if not record.producer_id or not record.fundo_id or not record.packing_partner_id or not record.season_id:
                raise ValidationError(_("Complete productor, fundo, packing y temporada."))
            if record.fundo_id.partner_id and record.fundo_id.partner_id != record.producer_id:
                raise ValidationError(_("El fundo debe pertenecer al productor."))
            if not record.estimate_line_ids:
                raise ValidationError(_("Ingrese al menos una línea de fruta."))
            for line in record.estimate_line_ids:
                if line.export_kg <= 0 or line.kg_per_box <= 0 or line.boxes_per_package <= 0:
                    raise ValidationError(_("Complete kilos de exportación, kg por caja y cajas por envase."))
                if line.delivery_kind == "process" and not 0 < line.export_percentage <= 1:
                    raise ValidationError(_("El porcentaje de exportación debe ser mayor a 0 y menor o igual a 100 %."))
                weekly_total = sum(line.week_line_ids.mapped("export_kg"))
                if float_compare(weekly_total, line.export_kg, precision_digits=3):
                    raise ValidationError(_("Distribuya todos los kilos de cada línea entre sus semanas."))
            record.state = "validated"
        return True

    def action_activate_estimate(self):
        for record in self:
            if record.state != "validated":
                raise UserError(_("Valide la estimación antes de hacerla vigente."))
            prior = self.search([
                ("company_id", "=", record.company_id.id),
                ("series_code", "=", record.series_code),
                ("state", "=", "current"),
                ("id", "!=", record.id),
            ])
            prior.write({"state": "replaced"})
            record.state = "current"
        return True

    def action_new_estimate_version(self):
        self.ensure_one()
        if self.state != "current":
            raise UserError(_("La nueva versión debe partir de una estimación vigente."))
        if not self.series_code:
            self.series_code = self.env["ir.sequence"].next_by_code("step.export.estimate")
        version = max(self.search([
            ("company_id", "=", self.company_id.id),
            ("series_code", "=", self.series_code),
        ]).mapped("version_number")) + 1
        new = self.copy({
            "series_code": self.series_code, "version_number": version,
            "previous_version_id": self.id, "state": "created", "estimate_version": str(version),
        })
        return {
            "type": "ir.actions.act_window", "name": _("Nueva versión de estimación"),
            "res_model": self._name, "res_id": new.id, "view_mode": "form", "target": "current",
        }


class StepExportProducerEstimateLine(models.Model):
    _name = "step.export.estimate.line"
    _description = "Línea de estimación de productor"
    _order = "id"

    estimate_id = fields.Many2one("step.export.estimate", required=True, ondelete="cascade", index=True)
    delivery_kind = fields.Selection([
        ("process", "Para proceso"), ("packed", "Embalada"),
    ], required=True, default="process")
    species_id = fields.Many2one("step.especie", string="Especie", required=True)
    variety_group_id = fields.Many2one("step.grupo.variedad", string="Grupo de variedades")
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    package_type_id = fields.Many2one("stock.package.type", string="Envase de traslado")
    export_kg = fields.Float(string="Kilos exportación", digits=(16, 3))
    export_percentage = fields.Float(string="% exportación (0 a 1)", digits=(8, 4), default=1)
    kg_per_box = fields.Float(string="Kg por caja", digits=(12, 3))
    boxes_per_package = fields.Float(string="Cajas por envase", digits=(12, 2))
    process_kg = fields.Float(string="Kilos a proceso", compute="_compute_quantities", store=True)
    harvest_box_qty = fields.Float(string="Cajas cosecha", compute="_compute_quantities", store=True)
    bin_qty = fields.Float(string="Bins", compute="_compute_quantities", store=True)
    process_pallet_qty = fields.Float(string="Pallets proceso", digits=(12, 2))
    export_box_qty = fields.Float(string="Cajas exportación", compute="_compute_quantities", store=True)
    export_pallet_qty = fields.Float(string="Pallets exportación", compute="_compute_quantities", store=True)
    week_line_ids = fields.One2many("step.export.estimate.week", "line_id", string="Distribución semanal", copy=True)

    @api.onchange("packaging_id", "package_type_id")
    def _onchange_packing_quantities(self):
        for line in self:
            if line.packaging_id:
                line.kg_per_box = line.packaging_id.step_export_kg_per_box
            if line.package_type_id:
                line.boxes_per_package = line.package_type_id.step_export_boxes_per_pallet

    @api.depends("delivery_kind", "export_kg", "export_percentage", "kg_per_box", "boxes_per_package")
    def _compute_quantities(self):
        for line in self:
            line.process_kg = 0
            line.harvest_box_qty = 0
            line.bin_qty = 0
            line.export_box_qty = 0
            line.export_pallet_qty = 0
            if line.kg_per_box > 0:
                line.export_box_qty = line.export_kg / line.kg_per_box
                if line.boxes_per_package > 0:
                    line.export_pallet_qty = line.export_box_qty / line.boxes_per_package
                if line.delivery_kind == "process" and line.export_percentage > 0:
                    line.process_kg = line.export_kg / line.export_percentage
                    line.harvest_box_qty = line.process_kg / line.kg_per_box
                    if line.boxes_per_package > 0:
                        line.bin_qty = line.harvest_box_qty / line.boxes_per_package

    def _check_editable(self):
        if any(line.estimate_id.state in ("current", "replaced") for line in self):
            raise UserError(_("Cree otra versión para modificar una estimación vigente o reemplazada."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.estimate"].browse(
            [vals["estimate_id"] for vals in vals_list if vals.get("estimate_id")])
        if any(parent.state in ("current", "replaced") for parent in parents):
            raise UserError(_("Cree otra versión para agregar líneas."))
        return super().create(vals_list)

    def write(self, vals):
        if vals:
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()


class StepExportProducerEstimateWeek(models.Model):
    _name = "step.export.estimate.week"
    _description = "Semana de estimación de productor"
    _order = "week_start, id"

    line_id = fields.Many2one("step.export.estimate.line", required=True, ondelete="cascade", index=True)
    week_start = fields.Date(string="Semana desde", required=True)
    export_kg = fields.Float(string="Kilos exportación", digits=(16, 3), required=True)

    _sql_constraints = [
        ("estimate_week_unique", "unique(line_id, week_start)", "La semana ya existe para esta línea."),
        ("estimate_week_kg_nonnegative", "check(export_kg >= 0)", "Los kilos no pueden ser negativos."),
    ]

    @api.constrains("week_start", "line_id")
    def _check_week(self):
        for week in self:
            if week.week_start and week.week_start.weekday() != 0:
                raise ValidationError(_("La semana debe empezar un lunes."))
            estimate = week.line_id.estimate_id
            if estimate.delivery_start and week.week_start < estimate.delivery_start:
                raise ValidationError(_("La semana debe estar dentro del período de entrega."))
            if estimate.delivery_end and week.week_start > estimate.delivery_end:
                raise ValidationError(_("La semana debe estar dentro del período de entrega."))

    def _check_editable(self):
        if any(w.line_id.estimate_id.state in ("current", "replaced") for w in self):
            raise UserError(_("Cree otra versión para modificar la distribución semanal."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.estimate.line"].browse(
            [vals["line_id"] for vals in vals_list if vals.get("line_id")])
        if any(line.estimate_id.state in ("current", "replaced") for line in parents):
            raise UserError(_("Cree otra versión para modificar la distribución semanal."))
        return super().create(vals_list)

    def write(self, vals):
        if vals:
            self._check_editable()
        return super().write(vals)

    def unlink(self):
        self._check_editable()
        return super().unlink()
