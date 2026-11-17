"""Select native centers from either tab and snapshot their agricultural data."""
from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.step_management_costs.models.estimation import PROTECTED_HEADER_FIELDS

PROTECTED_HEADER_FIELDS.add("farm_id")


class Estimation(models.Model):
    _inherit = "step.management.estimation"

    farm_id = fields.Many2one(
        "step.fundo", string="Fundo", check_company=True, ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
    )

    def _center_entry_values(self, center):
        self.ensure_one()
        yield_value, yield_source = self._agri_resolve_standard_yield(center)
        return {
            "farm": center.fundo_id.name or center.farm,
            "plot": ", ".join(center.cuartel_line.mapped("name")) or center.plot,
            "species": center.especie_id.name or center.species or self.species,
            "variety": center.variedad_id.name or center.variety or self.variety,
            "hectares": center.has_cost or center.hectares,
            "plants": center.plant_cost or center.plants,
            "yield_ue": yield_value if yield_value is not None else self.default_yield_ue,
            "plants_source": _("Maestro agrícola (centro)"),
            "yield_source": yield_source or _("Manual / por defecto (núcleo)"),
        }

    def _check_center_filters(self, include_lines=True):
        for estimation in self:
            centers = estimation.center_ids
            if include_lines:
                centers |= estimation.line_ids.center_id
            wrong = centers.filtered(lambda center:
                center.company_id != estimation.company_id
                or (estimation.farm_id and center.fundo_id != estimation.farm_id)
                or (estimation.species_id and center.especie_id != estimation.species_id)
                or (estimation.variety_id and center.variedad_id != estimation.variety_id)
            )
            if wrong:
                raise ValidationError(_(
                    "Los centros seleccionados deben corresponder a la empresa, "
                    "fundo, especie y variedad del encabezado. Revise %(centers)s."
                ) % {"centers": ", ".join(wrong.mapped("display_name"))})

    def action_compute_lines(self):
        self._check_center_filters(include_lines=False)
        result = super().action_compute_lines()
        for estimation in self:
            for line in estimation.line_ids:
                line.plot = ", ".join(line.center_id.cuartel_line.mapped("name")) or line.plot
        return result

    def _check_validation_prerequisites(self):
        self._check_center_filters()
        return super()._check_validation_prerequisites()


class EstimationLine(models.Model):
    _inherit = "step.management.estimation.line"

    cuartel_ids = fields.Many2many(
        "step.cuartel.line", string="Cuarteles del centro",
        compute="_compute_cuartels",
    )

    @api.depends("center_id.cuartel_line")
    def _compute_cuartels(self):
        for line in self:
            line.cuartel_ids = line.center_id.cuartel_line

    @api.onchange("center_id")
    def _onchange_center_entry(self):
        for line in self.filtered("center_id"):
            line.update(line.estimation_id._center_entry_values(line.center_id))

    def _link_selected_centers(self):
        for estimation in self.estimation_id:
            missing = self.filtered(
                lambda line: line.estimation_id == estimation
            ).center_id - estimation.center_ids
            if missing:
                estimation.write({"center_ids": [Command.link(center.id) for center in missing]})

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            values = dict(values)
            estimation = self.env["step.management.estimation"].browse(values.get("estimation_id"))
            center = self.env["account.analytic.account"].browse(values.get("center_id"))
            if estimation and center:
                for key, value in estimation._center_entry_values(center).items():
                    values.setdefault(key, value)
            prepared.append(values)
        lines = super().create(prepared)
        lines._link_selected_centers()
        return lines

    def write(self, values):
        if "center_id" not in values:
            return super().write(values)
        old_centers = {estimation: self.filtered(
            lambda line: line.estimation_id == estimation
        ).center_id for estimation in self.estimation_id}
        center = self.env["account.analytic.account"].browse(values["center_id"])
        for line in self:
            prepared = dict(values)
            if center and center != line.center_id:
                prepared = dict(line.estimation_id._center_entry_values(center), **values)
            super(EstimationLine, line).write(prepared)
        self._link_selected_centers()
        for estimation, centers in old_centers.items():
            removed = centers - estimation.line_ids.center_id
            if removed:
                estimation.write({"center_ids": [Command.unlink(center.id) for center in removed]})
        return True

    def unlink(self):
        old_centers = {estimation: self.filtered(
            lambda line: line.estimation_id == estimation
        ).center_id for estimation in self.estimation_id}
        result = super().unlink()
        for estimation, centers in old_centers.items():
            removed = centers - estimation.line_ids.center_id
            if removed:
                estimation.write({"center_ids": [Command.unlink(center.id) for center in removed]})
        return result
