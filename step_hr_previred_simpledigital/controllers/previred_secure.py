"""Cierre de la ruta Previred del proveedor.

El controlador de SimpleDigital publica `/hr_payroll/previred/txt` con
`auth='user'`, toma la compañía de la **URL** y consulta con `.sudo()`. El
efecto es que cualquier usuario interno autenticado puede descargar la nómina
previsional completa de **cualquier** compañía de la base cambiando un número
en la barra de direcciones, sin permiso de nómina.

Aquí se corrige **heredando el controlador del proveedor**, no registrando una
ruta suelta con la misma URL: `SecuredPreviredExportController` extiende
`PreviredExportController`, y `@http.route()` sin argumentos reutiliza la
definición de ruta del padre. Odoo resuelve el método del descendiente, de modo
que no quedan dos rutas compitiendo ni depende del orden de carga.

No se modifica ni un archivo del addon del proveedor.
"""

import calendar
import logging
from datetime import datetime

from odoo import _, http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from odoo.addons.l10n_cl_simpledigital_payroll.controllers.previred_txt import (
    PreviredExportController,
)

_logger = logging.getLogger(__name__)

GROUP_GENERATE = "step_hr_previred.group_previred_generate"


class SecuredPreviredExportController(PreviredExportController):
    """Añade control de acceso a las rutas Previred del proveedor."""

    # -- guardia -------------------------------------------------------------

    def _previred_guard(self, period, company_id):
        """Revalida permiso, compañía y período **en servidor**.

        Nada de lo que llega por la URL se acepta sin comprobar: ni la
        compañía, ni el período.
        """
        user = request.env.user

        if not user.has_group(GROUP_GENERATE):
            _logger.warning(
                "Previred: %s intentó descargar el archivo sin el permiso de "
                "generación.", user.login)
            raise AccessError(_(
                "Necesita el permiso «Previred: generar exportaciones» para "
                "descargar el archivo previsional."))
        if not user.has_group("hr_payroll.group_hr_payroll_manager"):
            raise AccessError(_(
                "El archivo Previred contiene la nómina corporativa completa. "
                "Sólo un Administrador de Nómina puede descargarlo."))

        # La compañía debe estar entre las habilitadas para ESTE usuario. No
        # basta con que exista: el parámetro llega del cliente.
        allowed = request.env.companies
        if company_id:
            try:
                requested = int(company_id)
            except (TypeError, ValueError):
                raise UserError(_("La compañía indicada no es válida."))
            if requested not in allowed.ids:
                _logger.warning(
                    "Previred: %s intentó exportar la compañía %s, que no "
                    "tiene habilitada.", user.login, requested)
                raise AccessError(_(
                    "No tiene habilitada la compañía solicitada. Previred no "
                    "admite mezclar ni exportar compañías ajenas."))
        else:
            raise UserError(_(
                "Indique la compañía a exportar. El archivo Previred es por "
                "empresa."))

        # El período debe ser un mes real en formato mmaaaa.
        if not period:
            raise UserError(_("Indique el período a exportar, en formato "
                              "mmaaaa."))
        try:
            parsed = datetime.strptime(period, "%m%Y")
        except (TypeError, ValueError):
            raise UserError(_(
                "El período «%s» no tiene el formato mmaaaa.", period))
        if not 1 <= parsed.month <= 12:
            raise UserError(_("El mes del período no es válido."))
        # Un período futuro no puede declararse: no hay remuneraciones aún.
        today = datetime.today()
        if (parsed.year, parsed.month) > (today.year, today.month):
            raise UserError(_(
                "El período %s todavía no ha ocurrido.", period))
        calendar.monthrange(parsed.year, parsed.month)

        # El acceso real a las liquidaciones se comprueba con el ORM, no sólo
        # con el grupo: el generador del proveedor usa `.sudo()` internamente.
        payslips = request.env["hr.payslip"]
        try:
            payslips.check_access("read")
        except AttributeError:  # Odoo < 18 nombra el método de otro modo
            payslips.check_access_rights("read")

        last_day = calendar.monthrange(parsed.year, parsed.month)[1]
        date_from = parsed.date().replace(day=1)
        date_to = parsed.date().replace(day=last_day)
        domain = [
            ("company_id", "=", requested),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
            ("state", "in", ["verify", "done", "paid"]),
        ]
        visible = payslips.search_count(domain)
        corporate = payslips.sudo().search_count(domain)
        if visible != corporate:
            raise AccessError(_(
                "Sus reglas de acceso no permiten ver la nómina corporativa "
                "completa; se bloqueó una descarga Previred parcial."))

    # -- rutas heredadas -----------------------------------------------------

    @http.route()
    def download_previred_txt(self, period=None, company_id=None, **kw):
        """Misma ruta del proveedor, ahora con control de acceso."""
        self._previred_guard(period, company_id)
        return super().download_previred_txt(
            period=period, company_id=company_id, **kw)

    @http.route()
    def download_previred_csv(self, period=None, company_id=None, **kw):
        """La ruta CSV tiene el mismo problema y la misma guardia."""
        self._previred_guard(period, company_id)
        return super().download_previred_csv(
            period=period, company_id=company_id, **kw)
