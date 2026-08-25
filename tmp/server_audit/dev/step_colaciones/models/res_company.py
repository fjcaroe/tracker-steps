import re

from urllib.parse import urlparse

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


#: Ruta histórica servida por Nginx en el mismo dominio de Odoo. Se usa como
#: valor de reserva para que una instalación existente conserve su URL actual
#: mientras no se configure un host propio para la aplicación.
LEGACY_APP_PATH = "/colaciones/app"

#: Nombres de host que se aceptan sin HTTPS porque corresponden a entornos de
#: desarrollo local.
LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class ResCompany(models.Model):
    _inherit = "res.company"

    colaciones_pwa_base_url = fields.Char(
        string="URL de la App de Colaciones",
        help=(
            "Dirección pública desde la que se sirve la aplicación del tótem, "
            "por ejemplo https://colaciones.stepsapp.cl. Si se deja vacía se "
            "usa la ruta /colaciones/app/ del mismo dominio de Odoo."
        ),
    )
    colaciones_provision_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de provisión de colaciones",
        domain="[('company_id', '=', id), ('type', 'in', ('general', 'purchase'))]",
        check_company=True,
        help=(
            "Diario donde se generan los comprobantes de colaciones. La cuenta "
            "predeterminada del diario se utiliza como cuenta de abono o provisión."
        ),
    )
    colaciones_accounting_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable contable de colaciones",
        domain="[('share', '=', False)]",
        help=(
            "Recibe una actividad cuando una distribución dinámica no encuentra "
            "horas y debe utilizar la distribución fija del trabajador."
        ),
    )

    @api.constrains("colaciones_provision_journal_id")
    def _check_colaciones_provision_journal(self):
        for company in self:
            journal = company.colaciones_provision_journal_id
            if not journal:
                continue
            if journal.company_id != company:
                raise ValidationError(_("El diario de provisión debe pertenecer a la compañía."))
            if journal.type not in ("general", "purchase"):
                raise ValidationError(_(
                    "El diario de provisión debe ser de tipo Misceláneo o Compras."
                ))
            if not journal.default_account_id:
                raise ValidationError(_(
                    "Configure la cuenta predeterminada (cuenta de abono) en el "
                    "diario de provisión de colaciones."
                ))

    @api.model
    def _normalize_colaciones_base_url(self, value):
        """Valida y normaliza la URL base de la aplicación de Colaciones.

        Devuelve la URL sin barras finales. Una cadena vacía significa "sin
        configurar" y no es un error: el llamador debe aplicar el valor de
        reserva.
        """
        value = (value or "").strip()
        if not value:
            return ""
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValidationError(_(
                "La URL de la App de Colaciones debe comenzar con http:// o https://."
            ))
        if not parsed.netloc:
            raise ValidationError(_(
                "La URL de la App de Colaciones debe incluir un nombre de host."
            ))
        hostname = (parsed.hostname or "").lower()
        is_local = hostname in LOCAL_HOSTNAMES or hostname.endswith(".local")
        if parsed.scheme != "https" and not is_local:
            raise ValidationError(_(
                "La App de Colaciones solo puede publicarse sobre HTTPS fuera de un "
                "entorno local."
            ))
        if parsed.query or parsed.fragment:
            raise ValidationError(_(
                "La URL de la App de Colaciones no debe incluir parámetros ni "
                "fragmento: el token se agrega automáticamente."
            ))
        path = re.sub(r"/+$", "", parsed.path or "")
        return "%s://%s%s" % (parsed.scheme, parsed.netloc, path)

    @api.constrains("colaciones_pwa_base_url")
    def _check_colaciones_pwa_base_url(self):
        for company in self:
            company._normalize_colaciones_base_url(company.colaciones_pwa_base_url)

    def _colaciones_fallback_base_url(self):
        """Ruta histórica en el propio dominio de Odoo."""
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").strip()
        base = re.sub(r"/+$", "", base)
        if not base:
            return ""
        return "%s%s" % (base, LEGACY_APP_PATH)

    def colaciones_app_base_url(self):
        """URL base efectiva de la aplicación para esta compañía."""
        self.ensure_one()
        configured = self._normalize_colaciones_base_url(self.colaciones_pwa_base_url)
        return configured or self._colaciones_fallback_base_url()
