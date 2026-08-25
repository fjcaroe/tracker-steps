from odoo import api, models

from ..tools import dt_book


def format_amount(value):
    """Entero con separador de miles chileno; vacío si no hay valor."""
    if value in (None, "", False):
        return ""
    return "{:,.0f}".format(int(value)).replace(",", ".")


class _BookReportMixin(models.AbstractModel):
    """Base común de los PDF.

    El dataset se construye aquí y sólo aquí: el botón del asistente se limita
    a validar y a abrir el informe, de modo que una acción del usuario produce
    un único dataset y un único registro de auditoría.
    """

    _name = "step.remuneration.book.report.mixin"
    _description = "Base de los informes del Libro de Remuneraciones"

    #: Salida que se registra en la auditoría.
    _step_output = "pdf"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["step.hr.remuneration.book.wizard"].browse(docids)[:1]
        dataset = wizard.generate(self._step_output)
        return {
            "doc_ids": docids,
            "doc_model": "step.hr.remuneration.book.wizard",
            "docs": wizard,
            "dataset": dataset,
            "columns": dataset.columns,
            "company": wizard.company_id,
            "fmt": format_amount,
            "rut": dt_book.rut_display,
        }


class ConsolidatedBookReport(models.AbstractModel):
    """PDF del libro consolidado: mismo dataset y mismos totales que el Excel."""

    _name = "report.step_hr_remuneration_book.consolidated_book"
    _inherit = "step.remuneration.book.report.mixin"
    _description = "Libro de Remuneraciones consolidado"

    _step_output = "pdf"


class EmployeeSheetsReport(models.AbstractModel):
    """Ficha detallada por trabajador: salida adicional, no el libro."""

    _name = "report.step_hr_remuneration_book.employee_sheets"
    _inherit = "step.remuneration.book.report.mixin"
    _description = "Fichas detalladas por trabajador"

    _step_output = "sheets"
