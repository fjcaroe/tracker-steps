"""Normalización de importes para el tipo de trabajador 3 de PreviRed."""

from decimal import Decimal, ROUND_HALF_UP

from odoo import _, models
from odoo.addons.step_payroll_contracts.history import stored_line_total

from odoo.addons.step_hr_previred.tools import previred


class PreviredExtractor(models.AbstractModel):
    _inherit = "step.previred.extractor"

    def _enrich_official_fields(self, record, payslip, dataset):
        result = super()._enrich_official_fields(record, payslip, dataset)
        if len(record.principal) == previred.FIELD_COUNT:
            self._restore_ccaf_fields(record, payslip, dataset)
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
            base_afp = stored_line_total(afp_lines)
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
                employer = int(Decimal(str(stored_line_total(
                    employer_lines
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

    def _restore_ccaf_fields(self, record, payslip, dataset):
        """Repair the vendor's zero-day gate after attendance normalization.

        The supplier can report zero days for an ended contract even when its
        stored payslip contains attendance and taxable salary. The core restores
        field 13, but fields 84/90 previously retained the supplier's zero. Only
        those missing fields are restored; existing contributions are preserved.
        """
        row = record.principal
        health = str(row[74] or "").strip()
        ccaf = str(row[82] or "").strip()
        days = str(row[12] or "0").strip()
        taxable = str(row[63] or "0").strip()
        if (health != "07" or ccaf in ("", "0", "00")
                or not days.isdigit() or int(days) <= 0
                or not taxable.isdigit() or int(taxable) <= 0):
            return
        missing_base = not str(row[83] or "0").strip().strip("0")
        missing_amount = not str(row[89] or "0").strip().strip("0")
        if not (missing_base or missing_amount):
            return
        # A positive field 64 is the supplier's already-capped Fonasa base.
        # Do not use current wages, another contract, or the AFP base (RIMA).
        if missing_base:
            row[83] = str(int(taxable))
        if not missing_amount:
            return
        indicator = self.env["previred.indicator"].search([
            ("date", ">=", payslip.date_from.replace(day=1)),
            ("date", "<=", payslip.date_to),
        ], order="date desc, id desc", limit=1)
        rate = Decimal(str(indicator.ccaf_empleadores_afiliados or 0)) \
            if indicator else Decimal(0)
        if not rate.is_finite() or rate <= 0 or rate > 7:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_ERROR, "ccaf_rate_missing",
                _("No se puede recuperar la cotización CCAF: revise el "
                  "indicador CCAF del período de la liquidación."),
                record.department_label))
            return
        # Keep the supplier's existing integer-peso convention.
        row[89] = str(int(Decimal(taxable) * rate / 100))
        dataset.issues.append(previred.Issue(
            previred.SEVERITY_WARNING, "ccaf_attendance_restored",
            _("Se recuperaron los campos CCAF 84/90 desde la renta Fonasa "
              "y los días de asistencia de la liquidación, usando el "
              "indicador del mismo período. Revise el archivo generado."),
            record.department_label))
