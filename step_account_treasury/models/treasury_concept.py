# -*- coding: utf-8 -*-
"""Maestro de conceptos de flujo de caja."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: Hojas del flujo. El orden es el del documento funcional.
SHEET_SELECTION = [
    ("customer", "Clientes"),
    ("sale_order", "Notas de venta"),
    ("other_income", "Otras recaudaciones"),
    ("vendor", "Proveedores"),
    ("purchase_order", "Órdenes de compra"),
    ("proforma", "Proformas"),
    ("other_payment", "Otros pagos"),
]

#: Hojas que suman al saldo y hojas que restan.
INFLOW_SHEETS = ("customer", "sale_order", "other_income")
OUTFLOW_SHEETS = ("vendor", "purchase_order", "proforma", "other_payment")

FLOW_TYPE_SELECTION = [
    ("opening", "Saldo inicial"),
    ("inflow", "Ingreso"),
    ("outflow", "Egreso"),
]


class StepTreasuryConcept(models.Model):
    _name = "step.treasury.concept"
    _description = "Concepto de flujo de caja"
    _inherit = ["mail.thread"]
    _order = "sequence, code, id"
    _check_company_auto = True

    name = fields.Char(string="Descripción", required=True, tracking=True)
    code = fields.Char(string="Código flujo", required=True, index=True, tracking=True)
    flow_type = fields.Selection(
        FLOW_TYPE_SELECTION, string="Tipo", required=True, default="inflow", tracking=True,
        help="Saldo inicial se cuenta una sola vez; ingreso suma y egreso resta.",
    )
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)
    account_ids = fields.Many2many(
        "account.account", "step_treasury_concept_account_rel", "concept_id", "account_id",
        string="Cuentas posibles", check_company=True,
        help="Cuentas contables asociadas al concepto. Admite varias.",
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, index=True,
        default=lambda self: self.env.company,
    )
    suggested_sheet = fields.Selection(
        SHEET_SELECTION, string="Hoja sugerida",
        help="Hoja del flujo en la que se propone este concepto por omisión.",
    )
    note = fields.Text(string="Notas")
    legacy_studio_id = fields.Integer(
        string="Id Studio de origen", readonly=True, copy=False, index=True,
        help="Identificador del concepto en el prototipo Studio del que se migró.",
    )

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)",
         "El código de concepto debe ser único por empresa."),
    ]

    @api.depends("code", "name")
    def _compute_display_name(self):
        for record in self:
            record.display_name = "%s %s" % (record.code or "", record.name or "")

    @api.constrains("account_ids", "company_id")
    def _check_account_company(self):
        """Ninguna cuenta puede pertenecer a otra empresa."""
        for record in self:
            for account in record.account_ids:
                if record.company_id not in account.company_ids:
                    raise ValidationError(_(
                        "La cuenta %(account)s no pertenece a la empresa %(company)s.",
                        account=account.display_name, company=record.company_id.display_name,
                    ))

    @api.constrains("flow_type", "suggested_sheet")
    def _check_flow_type_sheet(self):
        """La hoja sugerida no puede contradecir el signo del concepto."""
        for record in self:
            if not record.suggested_sheet:
                continue
            if record.flow_type == "inflow" and record.suggested_sheet not in INFLOW_SHEETS:
                raise ValidationError(_(
                    "El concepto %s es de ingreso: no puede sugerir una hoja de egreso.")
                    % record.display_name)
            if record.flow_type == "outflow" and record.suggested_sheet not in OUTFLOW_SHEETS:
                raise ValidationError(_(
                    "El concepto %s es de egreso: no puede sugerir una hoja de ingreso.")
                    % record.display_name)

    @api.model
    def _concept_for_sheet(self, sheet, company):
        """Concepto por omisión de una hoja automática, si está configurado."""
        return self.sudo().search([
            ("suggested_sheet", "=", sheet),
            ("company_id", "=", company.id),
            ("active", "=", True),
        ], limit=1, order="sequence, id")
