from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class StepManagementEstimationUnit(models.Model):
    _name = "step.management.estimation.unit"
    _description = "Unidad de estimación de cosecha"
    _order = "code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    kg_factor = fields.Float(
        string="Conversión a kg", required=True, default=1.0, digits=(16, 6),
        help="Kilogramos equivalentes a una unidad de estimación.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("estimation_unit_code_company_unique", "unique(code, company_id)",
         "El código de la unidad debe ser único por empresa."),
    ]

    @api.constrains("kg_factor")
    def _check_kg_factor(self):
        for record in self:
            if record.kg_factor <= 0:
                raise ValidationError(_("La conversión a kilogramos debe ser mayor que cero."))


class StepManagementFruitCategory(models.Model):
    _name = "step.management.fruit.category"
    _description = "Categoría de fruta"
    _order = "code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("fruit_category_code_company_unique", "unique(code, company_id)",
         "El código de la categoría debe ser único por empresa."),
    ]


class StepManagementFruitClass(models.Model):
    _name = "step.management.fruit.class"
    _description = "Clase de fruta"
    _order = "category_id, code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    category_id = fields.Many2one(
        "step.management.fruit.category", string="Categoría", required=True,
        check_company=True, index=True,
    )
    use_harvest = fields.Boolean(string="Usar en cosecha", default=True)
    use_packing = fields.Boolean(string="Usar en packing")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("fruit_class_code_company_unique", "unique(code, company_id)",
         "El código de la clase debe ser único por empresa."),
    ]


class StepManagementCaliberGroup(models.Model):
    _name = "step.management.caliber.group"
    _description = "Grupo de calibres de fruta"
    _order = "sequence, code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("caliber_group_code_company_unique", "unique(code, company_id)",
         "El código del grupo de calibres debe ser único por empresa."),
    ]


class StepManagementFruitCaliber(models.Model):
    _name = "step.management.fruit.caliber"
    _description = "Calibre de fruta"
    _order = "group_id, sequence, code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    group_id = fields.Many2one(
        "step.management.caliber.group", string="Grupo", required=True,
        check_company=True, index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("fruit_caliber_code_company_unique", "unique(code, company_id)",
         "El código del calibre debe ser único por empresa."),
    ]


class StepManagementEstimationCurve(models.Model):
    _name = "step.management.estimation.curve"
    _description = "Curva de distribución de estimación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "curve_type, code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True, tracking=True)
    code = fields.Char(string="Código", required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )
    curve_type = fields.Selection(
        [("week", "Semanas"), ("caliber", "Grupos de calibre"),
         ("class", "Clases de fruta")],
        string="Tipo de curva", required=True, index=True, tracking=True,
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("validated", "Validada")],
        string="Estado", required=True, default="draft", index=True, tracking=True,
    )
    line_ids = fields.One2many(
        "step.management.estimation.curve.line", "curve_id", string="Distribución",
        copy=True,
    )
    total_percentage = fields.Float(
        string="Total %", compute="_compute_totals", store=True, digits=(16, 4),
    )
    distribution_complete = fields.Boolean(
        string="Distribución completa", compute="_compute_totals", store=True,
    )
    validated_by_id = fields.Many2one(
        "res.users", string="Validada por", readonly=True, copy=False,
    )
    validated_at = fields.Datetime(string="Validada el", readonly=True, copy=False)
    notes = fields.Html(string="Notas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("estimation_curve_code_company_type_unique",
         "unique(code, company_id, curve_type)",
         "El código de la curva debe ser único por empresa y tipo."),
    ]

    @api.depends("line_ids.percentage")
    def _compute_totals(self):
        for record in self:
            record.total_percentage = sum(record.line_ids.mapped("percentage"))
            record.distribution_complete = bool(record.line_ids) and float_compare(
                record.total_percentage, 100.0, precision_digits=4,
            ) == 0

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("state", "draft") != "draft" for vals in vals_list):
            raise UserError(_("Las curvas nuevas deben crearse en borrador."))
        return super().create(vals_list)

    def write(self, vals):
        if "state" in vals:
            raise UserError(_("Cambie el estado de la curva usando sus botones de acción."))
        protected = {
            "name", "code", "company_id", "curve_type", "line_ids", "notes",
            "validated_by_id", "validated_at",
        }
        if protected.intersection(vals) and any(record.state == "validated" for record in self):
            raise UserError(_("Una curva validada es inmutable. Devuélvala a borrador para editarla."))
        return super().write(vals)

    def unlink(self):
        if any(record.state == "validated" for record in self):
            raise UserError(_("No puede eliminar una curva validada."))
        return super().unlink()

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.update({
            "name": _("%s (copia)") % self.name,
            "code": _("%s-COPIA") % self.code,
            "state": "draft",
            "validated_by_id": False,
            "validated_at": False,
        })
        return super().copy(default)

    def action_validate(self):
        self._require_manager()
        for record in self:
            if record.state != "draft":
                raise UserError(_("Sólo se puede validar una curva en borrador."))
            if not record.line_ids:
                raise UserError(_("Agregue al menos una línea a la curva."))
            record.line_ids._check_dimension()
            if not record.distribution_complete:
                raise UserError(_(
                    "La distribución debe sumar exactamente 100%%. Total actual: %.4f%%."
                ) % record.total_percentage)
            super(StepManagementEstimationCurve, record).write({
                "state": "validated",
                "validated_by_id": self.env.user.id,
                "validated_at": fields.Datetime.now(),
            })
        return True

    def action_set_draft(self):
        self._require_manager()
        for record in self:
            if record.state != "validated":
                raise UserError(_("Sólo una curva validada puede volver a borrador."))
            super(StepManagementEstimationCurve, record).write({
                "state": "draft",
                "validated_by_id": False,
                "validated_at": False,
            })
        return True

    def _require_manager(self):
        if not self.env.user.has_group("step_management_costs.group_management_manager"):
            raise UserError(_(
                "Sólo el administrador de Gestión y Costos puede validar o reabrir curvas."
            ))


class StepManagementEstimationCurveLine(models.Model):
    _name = "step.management.estimation.curve.line"
    _description = "Línea de curva de estimación"
    _order = "sequence, dimension_key, id"
    _check_company_auto = True

    curve_id = fields.Many2one(
        "step.management.estimation.curve", string="Curva", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="curve_id.company_id", string="Empresa", store=True, index=True,
    )
    curve_type = fields.Selection(
        related="curve_id.curve_type", string="Tipo", store=True, index=True,
    )
    sequence = fields.Integer(default=10)
    week_number = fields.Integer(string="Semana calendario")
    caliber_group_id = fields.Many2one(
        "step.management.caliber.group", string="Grupo de calibre",
        check_company=True, index=True,
    )
    fruit_class_id = fields.Many2one(
        "step.management.fruit.class", string="Clase de fruta",
        check_company=True, index=True,
    )
    percentage = fields.Float(string="Porcentaje", required=True, digits=(16, 4))
    dimension_key = fields.Char(
        string="Clave de distribución", compute="_compute_dimension", store=True,
        index=True,
    )
    dimension_name = fields.Char(
        string="Dimensión", compute="_compute_dimension", store=True,
    )

    _sql_constraints = [
        ("estimation_curve_dimension_unique", "unique(curve_id, dimension_key)",
         "No puede repetir la misma semana, grupo de calibre o clase en una curva."),
    ]

    @api.depends("curve_type", "week_number", "caliber_group_id", "fruit_class_id")
    def _compute_dimension(self):
        for record in self:
            if record.curve_type == "week" and record.week_number:
                record.dimension_key = "week:%02d" % record.week_number
                record.dimension_name = "W%02d" % record.week_number
            elif record.curve_type == "caliber" and record.caliber_group_id:
                record.dimension_key = "caliber:%s" % record.caliber_group_id.id
                record.dimension_name = record.caliber_group_id.display_name
            elif record.curve_type == "class" and record.fruit_class_id:
                record.dimension_key = "class:%s" % record.fruit_class_id.id
                record.dimension_name = record.fruit_class_id.display_name
            else:
                record.dimension_key = False
                record.dimension_name = False

    @api.constrains(
        "curve_type", "week_number", "caliber_group_id", "fruit_class_id", "percentage",
    )
    def _check_dimension(self):
        for record in self:
            if record.percentage <= 0 or record.percentage > 100:
                raise ValidationError(_("Cada porcentaje debe ser mayor que 0 y menor o igual a 100."))
            if record.curve_type == "week":
                if not 1 <= record.week_number <= 53:
                    raise ValidationError(_("La semana calendario debe estar entre 1 y 53."))
                if record.caliber_group_id or record.fruit_class_id:
                    raise ValidationError(_("Una curva semanal sólo puede contener semanas."))
            elif record.curve_type == "caliber":
                if not record.caliber_group_id or record.week_number or record.fruit_class_id:
                    raise ValidationError(_(
                        "Una curva de calibres sólo puede contener grupos de calibre."
                    ))
            elif record.curve_type == "class":
                if not record.fruit_class_id or record.week_number or record.caliber_group_id:
                    raise ValidationError(_(
                        "Una curva de clases sólo puede contener clases de fruta."
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        curves = self.env["step.management.estimation.curve"].browse(
            [vals.get("curve_id") for vals in vals_list if vals.get("curve_id")]
        )
        if any(curve.state == "validated" for curve in curves):
            raise UserError(_("No puede agregar líneas a una curva validada."))
        return super().create(vals_list)

    def write(self, vals):
        curves = self.mapped("curve_id")
        if vals.get("curve_id"):
            curves |= self.env["step.management.estimation.curve"].browse(vals["curve_id"])
        if any(curve.state == "validated" for curve in curves):
            raise UserError(_("No puede modificar líneas de una curva validada."))
        return super().write(vals)

    def unlink(self):
        if any(curve.state == "validated" for curve in self.mapped("curve_id")):
            raise UserError(_("No puede eliminar líneas de una curva validada."))
        return super().unlink()
