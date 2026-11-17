"""Estimate each native plot once, with independent yield and kg inputs."""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_management_costs.models.estimation import PROTECTED_LINE_FIELDS

PROTECTED_LINE_FIELDS.add("cuartel_id")


class Estimation(models.Model):
    _inherit = "step.management.estimation"

    def _center_plot_values(self, center, plot):
        values = self._center_entry_values(center)
        values["cuartel_id"] = plot.id
        if plot:
            values.update({
                "plot": plot.name,
                "hectares": plot.has_cuartel,
                "plants": plot.plant_cuartel,
                "plants_source": _("Maestro agrícola (cuartel)"),
            })
        return values

    def _plot_detail_commands(self):
        self.ensure_one()
        empty = self.env["step.management.estimation.line"]
        existing = {(line.center_id.id, line.cuartel_id.id): line for line in self.line_ids}
        keep = set()
        commands = []
        for center in self.center_ids:
            plots = list(center.cuartel_line.sorted("id")) or [self.env["step.cuartel.line"]]
            aggregate = existing.get((center.id, False), empty)
            if aggregate and self.method == "kilos" and len(plots) > 1 and aggregate.total_kg_input:
                raise UserError(_(
                    "El centro %(center)s tiene kilos ingresados sin cuartel. "
                    "Asigne el cuartel a esa línea en Detalle y registre los "
                    "kilos de los demás cuarteles antes de recalcular."
                ) % {"center": center.display_name})
            for index, plot in enumerate(plots):
                line = existing.get((center.id, plot.id), empty)
                if not line and index == 0:
                    line = aggregate
                values = self._center_plot_values(center, plot)
                if line:
                    keep.add(line.id)
                    values.pop("yield_ue")
                    values.pop("yield_source")
                    commands.append(Command.update(line.id, values))
                else:
                    if aggregate:
                        values.update({
                            "yield_ue": aggregate.yield_ue,
                            "yield_source": aggregate.yield_source,
                            "kg_factor": aggregate.kg_factor,
                        })
                    commands.append(Command.create(dict(values, center_id=center.id)))
        removed = [Command.delete(line.id) for line in self.line_ids if line.id not in keep]
        return removed + commands

    def action_compute_lines(self):
        for estimation in self:
            if estimation.state != "draft":
                raise UserError(_("Sólo puede recalcular una estimación en borrador."))
            estimation._check_center_filters(include_lines=False)
            if not estimation.center_ids:
                raise UserError(_("Seleccione al menos un centro de costo."))
            estimation.write({"line_ids": estimation._plot_detail_commands()})
            estimation.message_post(body=_("Detalle recalculado por cuartel."))
        return True

    def _check_validation_prerequisites(self):
        for estimation in self:
            aggregate = estimation.line_ids.filtered(
                lambda line: not line.cuartel_id and line.center_id.cuartel_line
            )
            if aggregate:
                raise UserError(_("Use Calcular detalle para distribuir los centros por cuartel antes de validar."))
        return super()._check_validation_prerequisites()


class EstimationLine(models.Model):
    _inherit = "step.management.estimation.line"

    cuartel_id = fields.Many2one(
        "step.cuartel.line", string="Cuartel", ondelete="restrict", index=True,
        domain="[('centro_id', '=', center_id)]",
    )

    _sql_constraints = [
        ("estimation_line_center_unique", "unique(estimation_id, center_id, cuartel_id)",
         "No puede repetir el mismo cuartel en una estimación."),
    ]

    def _auto_init(self):
        result = super()._auto_init()
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS estimation_center_without_plot_uniq
            ON step_management_estimation_line (estimation_id, center_id)
            WHERE cuartel_id IS NULL
        """)
        return result

    @api.constrains("center_id", "cuartel_id", "estimation_id")
    def _check_plot_center(self):
        for line in self:
            if line.cuartel_id and line.cuartel_id.centro_id != line.center_id:
                raise ValidationError(_("El cuartel debe pertenecer al centro de costo de la línea."))
            siblings = line.estimation_id.line_ids.filtered(
                lambda other: other != line and other.center_id == line.center_id
            )
            if siblings and (not line.cuartel_id or any(not other.cuartel_id for other in siblings)):
                raise ValidationError(_("Use líneas por cuartel para el centro y evite sumar además su total agregado."))

    @api.onchange("center_id")
    def _onchange_center_entry(self):
        for line in self.filtered("center_id"):
            plots = line.center_id.cuartel_line
            if line.cuartel_id.centro_id != line.center_id:
                line.cuartel_id = False
            if not line.cuartel_id and len(plots) == 1:
                line.cuartel_id = plots
            values = line.estimation_id._center_plot_values(line.center_id, line.cuartel_id)
            if plots and not line.cuartel_id:
                values.update({"plants": 0, "hectares": 0, "plot": False})
            line.update(values)

    @api.onchange("cuartel_id")
    def _onchange_plot_entry(self):
        for line in self.filtered("cuartel_id"):
            values = line.estimation_id._center_plot_values(line.center_id, line.cuartel_id)
            values.pop("yield_ue")
            values.pop("yield_source")
            line.update(values)

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            values = dict(values)
            if values.get("cuartel_id"):
                estimation = self.env["step.management.estimation"].browse(
                    values.get("estimation_id") or self.env.context.get("default_estimation_id")
                )
                center = self.env["account.analytic.account"].browse(
                    values.get("center_id") or self.env.context.get("default_center_id")
                )
                plot = self.env["step.cuartel.line"].browse(values["cuartel_id"])
                if estimation and center:
                    for key, value in estimation._center_plot_values(center, plot).items():
                        values.setdefault(key, value)
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        if not {"cuartel_id", "center_id"}.intersection(values):
            return super().write(values)
        for line in self:
            center = self.env["account.analytic.account"].browse(values.get("center_id", line.center_id.id))
            plot = self.env["step.cuartel.line"].browse(values.get("cuartel_id", line.cuartel_id.id))
            if "center_id" in values and "cuartel_id" not in values and plot.centro_id != center:
                plot = self.env["step.cuartel.line"]
            prepared = dict(values, cuartel_id=plot.id)
            if center != line.center_id or plot != line.cuartel_id:
                snapshot = line.estimation_id._center_plot_values(center, plot)
                if center == line.center_id:
                    snapshot.pop("yield_ue")
                    snapshot.pop("yield_source")
                prepared = dict(snapshot, **prepared)
            super(EstimationLine, line).write(prepared)
        return True
