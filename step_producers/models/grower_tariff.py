"""Producer tariff concepts used to estimate cost per kilogram."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GrowerTariff(models.Model):
    _inherit = "step.export.grower.rate"

    preliq_producer_ids = fields.Many2many(
        "res.partner", "step_grower_tariff_producer_rel", "rate_id", "partner_id",
        string="Productores aplicables",
        help="Vacío: todos los productores. Permite excepciones para uno o más productores.")
    preliq_line_ids = fields.One2many(
        "step.producer.grower.tariff.line", "rate_id", string="Conceptos de gasto")

    @api.model
    def resolve_preliq_cost(self, company, season, species, producer, variety,
                            product, fob_usd_per_kg, packaging=False):
        """Resolve one tariff list, then the most specific line for each concept."""
        rates = self.search([
            ("company_id", "=", company.id), ("season_id", "=", season.id),
            ("species_id", "=", species.id),
        ])
        candidates = rates.filtered(
            lambda rate: producer in rate.preliq_producer_ids
            if rate.preliq_producer_ids else not rate.producer_id or rate.producer_id == producer)
        specific = candidates.filtered(
            lambda rate: bool(rate.preliq_producer_ids) or bool(rate.producer_id))
        candidates = specific or candidates
        if len(candidates) != 1:
            raise UserError(_(
                "Se necesita exactamente una Tarifa Productor aplicable a empresa, "
                "temporada, especie y productor (coincidencias: %s).") % len(candidates))
        rate = candidates[0]
        selected = {}
        for line in rate.preliq_line_ids:
            if ((line.variety_id and line.variety_id != variety)
                    or (line.product_id and line.product_id != product)
                    or (line.packaging_id and line.packaging_id != packaging)):
                continue
            score = sum(bool(value) for value in
                        (line.variety_id, line.product_id, line.packaging_id))
            key = line.item_id.id
            previous = selected.get(key)
            if previous and previous[0] == score:
                raise UserError(_(
                    "Hay dos valores de Tarifa Productor igual de específicos para %s."
                ) % line.item_id.display_name)
            if not previous or score > previous[0]:
                selected[key] = (score, line)
        if not selected:
            raise UserError(_("La Tarifa Productor no tiene conceptos de gasto aplicables."))
        return sum(
            line.value if line.value_type == "usd_kg"
            else line.value * fob_usd_per_kg
            for _, line in selected.values())


class GrowerTariffLine(models.Model):
    _name = "step.producer.grower.tariff.line"
    _description = "Concepto de Tarifa Productor"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    rate_id = fields.Many2one(
        "step.export.grower.rate", required=True, ondelete="cascade")
    item_id = fields.Many2one(
        "step.export.grower.discount", string="Ítem Productor", required=True)
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    product_id = fields.Many2one("product.product", string="Producto")
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    value_type = fields.Selection([
        ("usd_kg", "USD por kg"), ("fob_fraction", "Fracción del FOB"),
    ], required=True, default="usd_kg", string="Tipo de valor")
    value = fields.Float(string="Valor de tarifa", required=True, digits=(16, 4))

    @api.constrains("value", "value_type")
    def _check_value(self):
        for line in self:
            if line.value < 0 or (line.value_type == "fob_fraction" and line.value > 1):
                raise ValidationError(_(
                    "El valor debe ser positivo; la fracción del FOB debe estar entre 0 y 1."))
