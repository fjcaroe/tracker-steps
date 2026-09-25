from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Campos de cabecera que quedan congelados una vez confirmado el contrato
# (T30: "Las cuotas estarán sujetas a modificaciones previo a su vencimiento
# de pago" describe el calendario, no el proveedor/moneda del contrato).
FROZEN_HEADER_FIELDS = {"partner_id", "currency_id", "company_id"}


class StepManagementPurchaseContract(models.Model):
    _name = "step.management.purchase.contract"
    _description = "Contrato de compra (anticipo a proveedor/productor)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, tracking=True,
        check_company=True, domain="[('company_id', 'in', [False, company_id])]",
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id, tracking=True,
    )
    date_start = fields.Date(string="Válido desde", tracking=True)
    date_end = fields.Date(string="Válido hasta", tracking=True)
    operation_type = fields.Char(
        string="Tipo de operación", tracking=True,
        help="Texto libre, p. ej. «Fruta: Recepción fruta». El documento de "
             "origen (T30) no trae una lista cerrada de tipos de operación.",
    )
    reference = fields.Char(string="Referencia", tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("confirmed", "Confirmado"), ("closed", "Cerrado")],
        string="Estado", default="draft", required=True, copy=False, tracking=True,
    )
    version = fields.Integer(string="Versión", default=1, copy=False, readonly=True)
    parent_id = fields.Many2one(
        "step.management.purchase.contract", string="Contrato anterior",
        copy=False, readonly=True, check_company=True,
    )
    revision_ids = fields.One2many(
        "step.management.purchase.contract", "parent_id", string="Revisiones",
    )
    is_superseded = fields.Boolean(
        string="Reemplazado", compute="_compute_is_superseded", store=True,
    )
    installment_ids = fields.One2many(
        "step.management.purchase.contract.installment", "contract_id",
        string="Calendario de pago",
    )
    quantity_total = fields.Float(
        string="Cantidad total", compute="_compute_totals", store=True, digits=(16, 4),
    )
    amount_total = fields.Monetary(
        string="Neto a pago total", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    notes = fields.Html(string="Notas")

    _sql_constraints = [
        ("date_range_check", "check(date_start is null or date_end is null or date_start <= date_end)",
         "La fecha de inicio del contrato no puede ser posterior a la fecha de término."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.purchase.contract"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.depends("revision_ids")
    def _compute_is_superseded(self):
        for contract in self:
            contract.is_superseded = bool(contract.revision_ids)

    @api.depends("installment_ids.quantity", "installment_ids.amount", "installment_ids.active")
    def _compute_totals(self):
        for contract in self:
            lines = contract.installment_ids.filtered("active")
            contract.quantity_total = sum(lines.mapped("quantity"))
            contract.amount_total = sum(lines.mapped("amount"))

    def _is_management_manager(self):
        return self.env.user.has_group("step_management_costs.group_management_manager")

    def write(self, vals):
        if not self._is_management_manager():
            frozen = self.filtered(lambda c: c.state != "draft")
            if frozen and (set(vals) & FROZEN_HEADER_FIELDS):
                raise UserError(_(
                    "No puede modificar proveedor, moneda o empresa de un "
                    "contrato ya confirmado: %s. Cree una revisión."
                ) % ", ".join(frozen.mapped("name")))
        return super().write(vals)

    def action_confirm(self):
        for contract in self:
            if contract.state != "draft":
                raise UserError(_("Sólo un contrato en Borrador puede confirmarse."))
            if not contract.installment_ids.filtered("active"):
                raise UserError(_(
                    "El contrato %s no tiene calendario de pago: agregue al "
                    "menos una cuota antes de confirmar."
                ) % contract.name)
            contract.state = "confirmed"
        return True

    def action_close(self):
        for contract in self:
            if contract.state != "confirmed":
                raise UserError(_("Sólo un contrato Confirmado puede cerrarse."))
            contract.state = "closed"
        return True

    def action_revise(self):
        """T30 punto 3.b: ante un cambio de condiciones, se reversan las
        cuotas pendientes del acuerdo anterior y se registra un nuevo
        acuerdo (nueva versión). "Pendiente" = no contabilizada todavía;
        una cuota ya contabilizada no se toca, sólo se archiva la que
        seguía en creado/aprobado."""
        self.ensure_one()
        if self.state != "confirmed":
            raise UserError(_("Sólo se puede revisar un contrato Confirmado."))
        if self.is_superseded:
            raise UserError(_("Este contrato ya tiene una revisión posterior (%s).")
                             % ", ".join(self.revision_ids.mapped("name")))
        pending = self.installment_ids.filtered(
            lambda line: line.active and line.state != "posted"
        )
        new_contract = self.copy({
            "name": _("Nuevo"),
            "version": self.version + 1,
            "parent_id": self.id,
            "state": "draft",
            "installment_ids": [
                (0, 0, {
                    "sequence": line.sequence, "product_id": line.product_id.id,
                    "quantity": line.quantity, "uom_id": line.uom_id.id,
                    "price_unit": line.price_unit, "date_due": line.date_due,
                    "validation_criteria": line.validation_criteria,
                }) for line in pending
            ],
        })
        pending.write({"active": False})
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.purchase.contract",
            "view_mode": "form",
            "res_id": new_contract.id,
        }


class StepManagementPurchaseContractInstallment(models.Model):
    _name = "step.management.purchase.contract.installment"
    _description = "Cuota del calendario de pago de un contrato de compra"
    _order = "contract_id, sequence, date_due"
    _check_company_auto = True

    contract_id = fields.Many2one(
        "step.management.purchase.contract", string="Contrato",
        required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(
        related="contract_id.company_id", string="Empresa", store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        related="contract_id.currency_id", string="Moneda", store=True, readonly=True,
    )
    sequence = fields.Integer(string="N°", default=1)
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True, check_company=True,
    )
    quantity = fields.Float(string="Cantidad", required=True, digits=(16, 4))
    uom_id = fields.Many2one("uom.uom", string="UdM")
    price_unit = fields.Float(string="Precio", required=True, digits=(16, 4))
    amount = fields.Monetary(
        string="Neto a pago", compute="_compute_amount", store=True,
        currency_field="currency_id",
    )
    date_due = fields.Date(string="Vencimiento", required=True)
    validation_criteria = fields.Char(string="Criterio de validación")
    state = fields.Selection(
        [("created", "Creado"), ("approved", "Aprobado"), ("posted", "Contabilizado")],
        string="Estado", default="created", required=True,
        help="«Contabilizado» describe la cuota una vez que el Contador "
             "generó su comprobante contable fuera de este módulo — T30 no "
             "define aún el mapeo de cuentas/diario para publicarlo "
             "automáticamente desde aquí (ver nota del ticket #30).",
    )
    active = fields.Boolean(
        default=True,
        help="Se desmarca al reversar una cuota pendiente durante una "
             "revisión de contrato (T30 punto 3.b); no se borra para "
             "conservar el historial.",
    )

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id and not line.uom_id:
                line.uom_id = line.product_id.uom_po_id

    @api.depends("quantity", "price_unit")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("La cantidad de la cuota debe ser mayor que cero."))

    @api.constrains("price_unit")
    def _check_price(self):
        for line in self:
            if line.price_unit < 0:
                raise ValidationError(_("El precio de la cuota no puede ser negativo."))

    def _is_management_manager(self):
        return self.env.user.has_group("step_management_costs.group_management_manager")

    def write(self, vals):
        if not self._is_management_manager():
            closed = self.filtered(lambda line: line.contract_id.state == "closed")
            if closed and set(vals) - {"state"}:
                raise UserError(_(
                    "No puede modificar cuotas de un contrato cerrado: %s."
                ) % ", ".join(closed.contract_id.mapped("name")))
        return super().write(vals)

    def action_approve(self):
        for line in self:
            if line.state != "created":
                raise UserError(_("Sólo una cuota Creada puede aprobarse."))
            line.state = "approved"
        return True
