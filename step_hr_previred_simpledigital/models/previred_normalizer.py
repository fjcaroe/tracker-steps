"""Normalización de importes para el tipo de trabajador 3 de PreviRed."""

from decimal import Decimal, ROUND_HALF_UP

from odoo import models

from odoo.addons.step_hr_previred.tools import previred


class PreviredExtractor(models.AbstractModel):
    _inherit = "step.previred.extractor"

    def _enrich_official_fields(self, record, payslip, dataset):
        result = super()._enrich_official_fields(record, payslip, dataset)
        if dataset.spec_version != "98" or len(record.principal) != \
                previred.FIELD_COUNT:
            return result

        row = record.principal
        worker_type = str(
            row[previred.F_WORKER_TYPE - 1] or ""
        ).strip()
        if worker_type != "3":
            return result

        # El tipo 3 mantiene su cotización base AFP, pero no paga la
        # cotización adicional de cargo del empleador. El generador del
        # proveedor suma AFP + AFP_EMP en el campo 28; tomar directamente AFP
        # evita depender de la tasa o de si la liquidación ya fue recalculada.
        afp_lines = payslip.line_ids.filtered(lambda line: line.code == "AFP")
        if afp_lines:
            def line_total(line):
                return line.total or (
                    line.amount * line.quantity * line.rate / 100.0
                )

            base_afp = sum(line_total(line) for line in afp_lines)
            row[previred.F_AFP_CONTRIBUTION - 1] = str(int(Decimal(
                str(base_afp)
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
        else:
            # Respaldo para liquidaciones históricas sin una línea AFP
            # separada: resta sólo AFP_EMP al total que entregó el motor.
            current = str(
                row[previred.F_AFP_CONTRIBUTION - 1] or "0"
            ).strip()
            employer_lines = payslip.line_ids.filtered(
                lambda line: line.code == "AFP_EMP"
            )
            if current.isdigit() and employer_lines:
                employer = int(Decimal(str(sum(
                    line.total or (
                        line.amount * line.quantity * line.rate / 100.0
                    ) for line in employer_lines
                ))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                row[previred.F_AFP_CONTRIBUTION - 1] = str(max(
                    0, int(current) - employer
                ))

        # Para el tipo 3 PreviRed exige cero en SIS y en las nuevas
        # cotizaciones del Seguro Social. Los campos 94 y 95 ya son
        # normalizados por el núcleo; se fijan de nuevo aquí para dejar la
        # regla completa y auditable junto a la corrección del campo 28.
        row[previred.F_SIS_CONTRIBUTION - 1] = "0"
        row[previred.F_LIFE_EXPECTANCY - 1] = "0"
        row[previred.F_PROTECTED_RETURN - 1] = "0"
        return result
