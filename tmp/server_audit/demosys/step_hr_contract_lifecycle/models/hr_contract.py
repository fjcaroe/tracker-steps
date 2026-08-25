# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrContract(models.Model):
    """Amplía hr.contract sólo con los datos que no existen ya en Odoo,
    l10n_cl_hr o step_hr (afp_id, isapre_id, causal_id, tipo_de_jornada,
    department_id, job_id, resource_calendar_id, wage ya existen y se
    reutilizan tal cual)."""

    _inherit = "hr.contract"

    # -- Modalidad / plantilla ------------------------------------------------
    labor_modality = fields.Selection(
        [
            ("temporada", "Temporada / faena transitoria"),
            ("trato", "A trato"),
            ("plazo_fijo", "Plazo fijo"),
            ("permanente", "Agrícola permanente / indefinido"),
        ],
        string="Modalidad contractual",
        tracking=True,
    )
    labor_template_id = fields.Many2one(
        "hr.labor.template",
        string="Plantilla laboral",
        domain="[('modality', '=', labor_modality), ('state', '=', 'validated')]",
        tracking=True,
    )
    is_faena_contract = fields.Boolean(
        string="Contrato por faena determinada",
        help="Fecha de término inicialmente indeterminada, vinculada al "
        "fin de la faena/temporada. Para previsión y cálculo se trata "
        "como un contrato de plazo fijo, sin falsear la fecha de término "
        "mientras la faena no concluya.",
    )
    faena_name = fields.Char(string="Faena / temporada")

    # -- Celebración y lugar de prestación -------------------------------------
    date_signature = fields.Date(string="Fecha de celebración", tracking=True)
    commune_signature_id = fields.Many2one(
        "res.city", string="Comuna de celebración"
    )
    work_region_id = fields.Many2one("res.country.state", string="Región de trabajo")
    work_commune_id = fields.Many2one("res.city", string="Comuna de trabajo")
    work_street = fields.Char(string="Calle (lugar de trabajo)")
    work_number = fields.Char(string="Número")
    work_complement = fields.Char(string="Complemento / depto.")
    fundo_id = fields.Many2one("step.fundo", string="Fundo / predio", tracking=True)
    cost_center_id = fields.Many2one("account.analytic.account", string="Centro de costo")

    # -- Jornada ---------------------------------------------------------------
    max_weekly_hours_legal = fields.Float(
        string="Máximo legal vigente (hrs/sem)",
        compute="_compute_max_weekly_hours_legal",
    )
    adequacy_state = fields.Selection(
        [
            ("not_applicable", "No aplica"),
            ("pending", "Pendiente de adecuación"),
            ("adequate", "Adecuado al máximo vigente"),
            ("exception", "Excepción / incidencia"),
        ],
        compute="_compute_adequacy_state",
        string="Estado de adecuación de jornada",
    )
    adequacy_line_id = fields.Many2one(
        "hr.contract.adequacy.line",
        string="Lote de adecuación asociado",
        compute="_compute_adequacy_state",
    )
    colacion_imputable = fields.Boolean(string="Colación imputable a la jornada")
    colacion_minutes = fields.Integer(string="Minutos de colación")
    has_excepcion_jornada = fields.Boolean(
        string="Tiene resolución de jornada excepcional (DT)"
    )
    excepcion_jornada_resolution = fields.Char(string="N° resolución excepcional")
    excepcion_jornada_date = fields.Date(string="Fecha resolución excepcional")

    # -- Datos DT / condicionales -----------------------------------------------
    cae_code = fields.Char(
        string="CAE aplicable", help="Clasificador de Actividad Económica del cargo."
    )
    is_foreign_worker = fields.Boolean(string="Trabajador extranjero sin RUT")
    passport_number = fields.Char(string="N° pasaporte / documento")
    is_subcontracted = fields.Boolean(string="Subcontratación")
    main_company_partner_id = fields.Many2one(
        "res.partner", string="Empresa principal"
    )
    is_temporary_work = fields.Boolean(string="Suministro de trabajadores (EST)")
    user_company_partner_id = fields.Many2one(
        "res.partner", string="Empresa usuaria"
    )
    has_disability = fields.Boolean(
        string="Declara discapacidad/invalidez",
        groups="step_hr_contract_lifecycle.group_contract_sensitive_data",
    )

    # -- Estado documental / registro DT ----------------------------------------
    document_state = fields.Selection(
        [
            ("no_template", "Sin plantilla"),
            ("ready", "Listo para generar"),
            ("generated", "Generado"),
            ("sent_to_sign", "Enviado a firma"),
            ("signed", "Firmado"),
            ("observed", "Observado"),
            ("cancelled", "Cancelado"),
        ],
        default="no_template",
        tracking=True,
        string="Estado del documento",
    )
    dt_registration_state = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("file_generated", "Archivo generado"),
            ("submitted", "Presentado"),
            ("accepted", "Aceptado"),
            ("observed_rejected", "Observado / rechazado"),
        ],
        default="pending",
        tracking=True,
        string="Estado registro DT",
    )
    dt_receipt_attachment_id = fields.Many2one(
        "ir.attachment", string="Comprobante DT"
    )
    document_ids = fields.One2many(
        "hr.labor.document", "contract_id", string="Documentos generados"
    )
    document_count = fields.Integer(compute="_compute_document_count")

    @api.depends()
    def _compute_document_count(self):
        for contract in self:
            contract.document_count = len(contract.document_ids)

    @api.depends("company_id", "date_start", "resource_calendar_id")
    def _compute_max_weekly_hours_legal(self):
        Calendar = self.env["hr.legal.workweek.calendar"]
        for contract in self:
            ref_date = contract.date_start or fields.Date.context_today(contract)
            _rec, hours = Calendar.get_effective_hours(ref_date, contract.company_id)
            contract.max_weekly_hours_legal = hours

    @api.depends("resource_calendar_id", "max_weekly_hours_legal", "state")
    def _compute_adequacy_state(self):
        AdequacyLine = self.env["hr.contract.adequacy.line"]
        for contract in self:
            if contract.state != "open" or not contract.resource_calendar_id:
                contract.adequacy_state = "not_applicable"
                contract.adequacy_line_id = False
                continue
            current = contract.resource_calendar_id.hours_per_week
            if current <= contract.max_weekly_hours_legal:
                contract.adequacy_state = "adequate"
                contract.adequacy_line_id = False
                continue
            line = AdequacyLine.search(
                [
                    ("contract_id", "=", contract.id),
                    ("batch_id.state", "in", ("approved", "applied")),
                ],
                limit=1,
                order="id desc",
            )
            contract.adequacy_line_id = line
            contract.adequacy_state = "pending" if line else "exception"

    def action_view_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos"),
            "res_model": "hr.labor.document",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }
