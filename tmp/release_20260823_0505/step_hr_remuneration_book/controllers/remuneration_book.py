import calendar
import io
import re
from datetime import datetime

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import content_disposition, request

from ..tools.xlsx_book import build_workbook

#: El libro corporativo y el CSV oficial exigen el permiso de exportación
#: completa: ocultar botones no es una medida de seguridad.
PARTIAL_GROUP = "hr_payroll.group_hr_payroll_user"


class StepsRemunerationBookController(http.Controller):
    """Descargas del Libro de Remuneraciones.

    Ninguna ruta acepta un período escrito a mano: se exige un asistente
    válido del propio usuario más un token firmado de vida corta. Las fechas y
    la empresa viajan además como comprobación cruzada y deben coincidir
    exactamente con ese asistente y ser un mes calendario completo.
    """

    # -- utilidades ---------------------------------------------------------

    def _authorized_wizard(self, output, kwargs):
        """Devuelve ``(wizard, error_response)``.

        Cualquier fallo devuelve `not_found()` sin detalle: no se filtra si el
        asistente existe, de quién es ni por qué se rechazó.
        """
        Wizard = request.env["step.hr.remuneration.book.wizard"]
        # Primero el permiso, antes de tocar ningún registro: un usuario sin
        # Nómina no debe provocar siquiera un error de acceso que revele que
        # el asistente existe.
        if not (Wizard.user_has_full_access()
                or request.env.user.has_group(PARTIAL_GROUP)):
            return None, request.not_found()
        try:
            wizard_id = int(kwargs.get("wizard_id") or 0)
        except (TypeError, ValueError):
            return None, request.not_found()
        if not wizard_id:
            return None, request.not_found()
        wizard = Wizard.browse(wizard_id).exists()
        if not wizard:
            return None, request.not_found()
        if wizard.create_uid.id != request.env.uid:
            return None, request.not_found()
        if kwargs.get("output") != output:
            return None, request.not_found()
        if not Wizard.check_download_token(
            wizard, output, kwargs.get("token"), kwargs.get("exp")
        ):
            return None, request.not_found()

        if wizard.mode == "full":
            if not Wizard.user_has_full_access():
                return None, request.not_found()
        elif not request.env.user.has_group(PARTIAL_GROUP):
            return None, request.not_found()
        if output == "csv" and wizard.mode != "full":
            return None, request.not_found()
        if not self._period_matches(wizard, kwargs):
            return None, request.not_found()
        company = wizard.company_id
        if not company or company not in request.env.companies:
            return None, request.not_found()
        try:
            if int(kwargs.get("company_id") or 0) != company.id:
                return None, request.not_found()
        except (TypeError, ValueError):
            return None, request.not_found()
        return wizard, None

    @staticmethod
    def _period_matches(wizard, kwargs):
        """El período debe ser un mes calendario completo y el del asistente."""
        try:
            parsed_from = datetime.strptime(
                kwargs.get("date_from") or "", "%Y-%m-%d").date()
            parsed_to = datetime.strptime(
                kwargs.get("date_to") or "", "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return False
        if parsed_from.day != 1:
            return False
        last_day = calendar.monthrange(parsed_from.year, parsed_from.month)[1]
        if (parsed_to.year, parsed_to.month, parsed_to.day) != (
            parsed_from.year, parsed_from.month, last_day
        ):
            return False
        if (parsed_from.month, parsed_from.year) != (
            int(wizard.month), wizard.year
        ):
            return False
        return parsed_from == wizard.date_from and parsed_to == wizard.date_to

    @staticmethod
    def _filename(prefix, company, date_from, extension):
        safe_company = re.sub(r"[^A-Za-z0-9_-]+", "_", company.name or "").strip("_")
        return "%s_%s_%s.%s" % (prefix, safe_company or "empresa",
                                date_from[:7], extension)

    @staticmethod
    def _respond(payload, filename, content_type):
        return request.make_response(
            payload,
            headers=[
                ("Content-Type", content_type),
                ("Content-Disposition", content_disposition(filename)),
                ("Cache-Control", "no-store"),
            ],
        )

    @staticmethod
    def _blocked(message):
        """Respuesta segura: sin traceback y sin datos personales."""
        return request.make_response(
            message,
            headers=[("Content-Type", "text/plain; charset=utf-8"),
                     ("Cache-Control", "no-store")],
            status=409,
        )

    # -- libro consolidado en Excel -----------------------------------------

    @http.route(
        "/step/payroll/remuneration-book/xlsx",
        type="http", auth="user", methods=["GET"],
    )
    def download_xlsx(self, **kwargs):
        try:
            wizard, error = self._authorized_wizard("xlsx", kwargs)
        except AccessError:
            return request.not_found()
        if error is not None:
            return error
        try:
            dataset = wizard.generate("xlsx")
        except UserError as exception:
            return self._blocked(exception.args[0] if exception.args else "")
        output = io.BytesIO()
        build_workbook(output, dataset)
        output.seek(0)
        prefix = ("libro_remuneraciones" if wizard.mode == "full"
                  else "reporte_parcial_remuneraciones")
        return self._respond(
            output.getvalue(),
            self._filename(prefix, wizard.company_id,
                           kwargs.get("date_from", ""), "xlsx"),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # -- archivo oficial de la Dirección del Trabajo ------------------------

    @http.route(
        "/step/payroll/remuneration-book/official-csv",
        type="http", auth="user", methods=["GET"],
    )
    def download_official_csv(self, **kwargs):
        """CSV oficial LRE: estructura completa, delimitador `;`, intacto.

        No es el libro consolidado de 24 columnas y no se recorta: la carga
        masiva de Mi DT exige los encabezados oficiales sin agregar ni quitar
        columnas.
        """
        try:
            wizard, error = self._authorized_wizard("csv", kwargs)
        except AccessError:
            return request.not_found()
        if error is not None:
            return error
        Log = request.env["step.remuneration.book.log"]
        extractor = request.env["step.remuneration.book.extractor"]
        try:
            content, source = extractor.official_csv(wizard)
        except UserError as exception:
            Log.record(wizard, "csv", result="blocked", detail="user_error",
                       user=request.env.user)
            return self._blocked(exception.args[0] if exception.args else "")
        Log.record(wizard, "csv", detail=source, user=request.env.user)
        return self._respond(
            content.encode("cp1252", errors="replace"),
            self._filename("lre_oficial", wizard.company_id,
                           kwargs.get("date_from", ""), "csv"),
            "text/csv; charset=windows-1252",
        )
