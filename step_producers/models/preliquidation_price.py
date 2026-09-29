"""Precios esperados para la simulación de retorno al productor (T38)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProducerPreliquidationPrice(models.Model):
    _name = "step.producer.preliq.price"
    _description = "Lista de precios de preliquidación"
    _order = "valid_from desc, id desc"

    name = fields.Char(string="Nombre", required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    season_id = fields.Many2one("step.temporada", string="Temporada", required=True)
    species_id = fields.Many2one("step.especie", string="Especie", required=True)
    valid_from = fields.Date(string="Vigente desde", required=True)
    valid_to = fields.Date(string="Vigente hasta", required=True)
    currency_id = fields.Many2one("res.currency", required=True, default=lambda self: self.env.ref("base.USD"))
    active = fields.Boolean(default=True)
    line_ids = fields.One2many("step.producer.preliq.price.line", "price_id", string="Precios")

    @api.constrains("valid_from", "valid_to")
    def _check_dates(self):
        for record in self:
            if record.valid_to < record.valid_from:
                raise ValidationError(_("La fecha final debe ser posterior al inicio."))

    @api.model
    def resolve_price(self, company, season, species, variety, when,
                      product=False, packaging=False, caliber=False, uom=False):
        """Devuelve la línea más específica; rechaza empates ambiguos.

        Un campo opcional vacío es precio general. La semana ISO usa la fecha
        de movimiento. Productor y empresa no se infieren de la lista.
        """
        day = fields.Date.to_date(when)
        lists = self.search([
            ("active", "=", True), ("company_id", "=", company.id),
            ("season_id", "=", season.id), ("species_id", "=", species.id),
            ("valid_from", "<=", day), ("valid_to", ">=", day),
        ])
        candidates = []
        for line in lists.mapped("line_ids"):
            if line.variety_id != variety or (uom and line.uom_id != uom):
                continue
            selectors = (
                (line.product_id, product), (line.packaging_id, packaging),
                (line.caliber_id, caliber),
            )
            if any(selected and selected != actual for selected, actual in selectors):
                continue
            if line.week_number and line.week_number != day.isocalendar().week:
                continue
            score = sum(bool(selected) for selected, _ in selectors) + bool(line.week_number)
            candidates.append((score, line.price_id.valid_from, line))
        if not candidates:
            raise UserError(_("No hay precio de preliquidación aplicable para la variedad y fecha."))
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_score, best_date, best_line = candidates[0]
        tied = [line for score, date, line in candidates
                if score == best_score and date == best_date]
        if len(tied) > 1:
            raise UserError(_("Hay varias líneas de precio igualmente específicas para esta fruta."))
        return best_line


class ProducerPreliquidationPriceLine(models.Model):
    _name = "step.producer.preliq.price.line"
    _description = "Precio de preliquidación de fruta"

    price_id = fields.Many2one("step.producer.preliq.price", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="price_id.company_id", store=True, index=True)
    variety_id = fields.Many2one("step.variedad", string="Variedad", required=True)
    product_id = fields.Many2one("product.product", string="Producto")
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    caliber_id = fields.Many2one("step.packing.fruit.caliber", string="Calibre")
    uom_id = fields.Many2one("uom.uom", string="UdM", required=True)
    week_number = fields.Integer(string="Semana ISO", default=0,
                                 help="0 aplica a cualquier semana.")
    price = fields.Monetary(string="Precio FOB por UdM", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="price_id.currency_id", store=True)

    _sql_constraints = [
        ("price_positive", "check(price > 0)", "El precio debe ser mayor a cero."),
        ("week_range", "check(week_number between 0 and 53)", "La semana debe estar entre 1 y 53, o 0 para todas."),
    ]
