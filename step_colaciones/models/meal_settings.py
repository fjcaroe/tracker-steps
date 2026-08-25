from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .res_company import LEGACY_APP_PATH


class StepColacionSettings(models.TransientModel):
    """Pantalla de configuración propia de Colaciones.

    Se implementa como modelo propio del módulo, y no sobre
    ``res.config.settings``, para que un Administrador de Colaciones pueda
    cambiar la URL de la aplicación sin recibir acceso a los ajustes generales
    de Odoo.
    """

    _name = "step.colacion.settings"
    _description = "Ajustes de Colaciones"

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
    )
    pwa_base_url = fields.Char(
        string="URL de la App de Colaciones",
        help=(
            "Dirección pública desde la que se sirve la aplicación del tótem, "
            "por ejemplo https://colaciones.stepsapp.cl. Si se deja vacía se usa "
            "la ruta %s del mismo dominio de Odoo." % LEGACY_APP_PATH
        ),
    )
    effective_base_url = fields.Char(
        string="URL efectiva",
        compute="_compute_effective_base_url",
        help="Dirección que utilizarán los botones Abrir tótem de esta compañía.",
    )
    sample_totem_url = fields.Char(
        string="Formato del enlace",
        compute="_compute_effective_base_url",
        help="Formato del enlace de asociación. El token real nunca se muestra aquí.",
    )
    min_app_version = fields.Char(string="Versión mínima de la App móvil")
    recommended_app_version = fields.Char(string="Versión recomendada de la App móvil")
    can_edit_app_versions = fields.Boolean(compute="_compute_can_edit_app_versions")
    provision_journal_id = fields.Many2one(
        "account.journal",
        string="Diario de provisión",
        domain="[('company_id', '=', company_id), ('type', 'in', ('general', 'purchase'))]",
        check_company=True,
    )
    provision_account_id = fields.Many2one(
        "account.account",
        string="Cuenta de abono",
        related="provision_journal_id.default_account_id",
        readonly=True,
    )
    accounting_responsible_id = fields.Many2one(
        "res.users",
        string="Responsable contable",
        domain="[('share', '=', False)]",
    )

    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        company = self.env["res.company"].browse(values.get("company_id")) or self.env.company
        params = self.env["ir.config_parameter"].sudo()
        values.update({
            "company_id": company.id,
            "pwa_base_url": company.colaciones_pwa_base_url or "",
            "min_app_version": params.get_param("colaciones.min_app_version", "1.0.0"),
            "recommended_app_version": params.get_param("colaciones.recommended_app_version", "1.0.0"),
            "provision_journal_id": company.colaciones_provision_journal_id.id,
            "accounting_responsible_id": company.colaciones_accounting_responsible_id.id,
        })
        return values

    @api.depends("company_id", "pwa_base_url")
    def _compute_effective_base_url(self):
        for record in self:
            configured = record.company_id._normalize_colaciones_base_url(record.pwa_base_url)
            base = configured or record.company_id._colaciones_fallback_base_url()
            record.effective_base_url = base
            record.sample_totem_url = "%s/#token=…" % base if base else ""

    def _compute_can_edit_app_versions(self):
        editable = self.env.user.has_group("base.group_system")
        for record in self:
            record.can_edit_app_versions = editable

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for record in self:
            record.pwa_base_url = record.company_id.colaciones_pwa_base_url or ""
            record.provision_journal_id = record.company_id.colaciones_provision_journal_id
            record.accounting_responsible_id = record.company_id.colaciones_accounting_responsible_id

    # ------------------------------------------------------------------
    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("step_colaciones.group_colaciones_manager"):
            raise AccessError(_("Solo un Administrador de Colaciones puede cambiar estos ajustes."))
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_("No puede configurar una compañía a la que no tiene acceso."))
        # `_normalize_colaciones_base_url` valida esquema, host y ausencia de
        # fragmento; se guarda el valor normalizado, no el texto original.
        normalized = self.company_id._normalize_colaciones_base_url(self.pwa_base_url)
        self.company_id.sudo().write({
            "colaciones_pwa_base_url": normalized or False,
            "colaciones_provision_journal_id": self.provision_journal_id.id,
            "colaciones_accounting_responsible_id": self.accounting_responsible_id.id,
        })
        if self.env.user.has_group("base.group_system"):
            params = self.env["ir.config_parameter"].sudo()
            params.set_param("colaciones.min_app_version", (self.min_app_version or "1.0.0").strip())
            params.set_param(
                "colaciones.recommended_app_version",
                (self.recommended_app_version or "1.0.0").strip(),
            )
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
