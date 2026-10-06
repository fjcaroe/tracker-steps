"""Producer purchase contracts, product commitments and payment schedules (T30)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class ProducerPurchaseContract(models.Model):
    _name = "step.producer.purchase.contract"
    _description = "Contrato de compra de productor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(string="Folio", required=True, readonly=True, copy=False,
                       default=lambda self: _("Nuevo"), index=True)
    company_id = fields.Many2one("res.company", string="Empresa", required=True,
                                 default=lambda self: self.env.company, index=True, tracking=True)
    partner_id = fields.Many2one("res.partner", string="Productor", required=True,
                                 tracking=True, check_company=True,
                                 domain="[('is_productor', '=', True), ('company_id', 'in', [False, company_id])]")
    currency_id = fields.Many2one("res.currency", string="Moneda", required=True,
                                  default=lambda self: self.env.company.currency_id, tracking=True)
    date_start = fields.Date(string="Válido desde", tracking=True)
    date_end = fields.Date(string="Válido hasta", tracking=True)
    operation_type = fields.Char(string="Tipo de operación", tracking=True)
    reference = fields.Char(string="Referencia", tracking=True)
    state = fields.Selection([("draft", "Borrador"), ("confirmed", "Confirmado"),
                              ("closed", "Cerrado")], default="draft", required=True,
                             copy=False, tracking=True)
    version = fields.Integer(string="Versión", default=1, readonly=True, copy=False)
    parent_id = fields.Many2one("step.producer.purchase.contract", string="Versión anterior",
                                readonly=True, copy=False, check_company=True)
    revision_ids = fields.One2many("step.producer.purchase.contract", "parent_id", string="Revisiones")
    is_superseded = fields.Boolean(compute="_compute_is_superseded", store=True)
    legacy_contract_id = fields.Integer(string="ID contrato anterior", copy=False, readonly=True, index=True)

    product_line_ids = fields.One2many("step.producer.purchase.contract.product", "contract_id",
                                       string="Productos")
    installment_ids = fields.One2many("step.producer.purchase.contract.installment", "contract_id",
                                      string="Calendario de pago")
    purchase_order_ids = fields.One2many("purchase.order", "step_producer_contract_id",
                                         string="Órdenes de compra")
    quantity_total = fields.Float(string="Cantidad contratada", compute="_compute_totals",
                                  store=True, digits=(16, 4))
    amount_total = fields.Monetary(string="Neto del contrato", compute="_compute_totals",
                                   store=True, currency_field="currency_id")
    scheduled_total = fields.Monetary(string="Neto programado", compute="_compute_totals",
                                      store=True, currency_field="currency_id")
    notes = fields.Html(string="Notas")

    journal_id = fields.Many2one("account.journal", string="Diario de contrato", check_company=True,
                                 groups="account.group_account_user",
                                 domain="[('company_id', '=', company_id), ('type', 'in', ['general', 'purchase'])]")
    provision_account_id = fields.Many2one("account.account", string="Cuenta de provisión (haber)",
                                            check_company=True, groups="account.group_account_user")
    accounting_date = fields.Date(string="Fecha contable", default=fields.Date.context_today,
                                  groups="account.group_account_user")
    accounting_move_id = fields.Many2one("account.move", string="Asiento de provisión",
                                         readonly=True, copy=False, check_company=True,
                                         groups="account.group_account_user")
    pending_reversal_move_id = fields.Many2one(
        "account.move", string="Reversa de cuotas pendientes", check_company=True,
        groups="account.group_account_user",
        help="Si se contabilizó esta versión y se revisan condiciones, el contador vincula aquí "
             "la reversa de la parte pendiente antes de contabilizar la nueva versión.")

    _sql_constraints = [
        ("date_range", "check(date_start is null or date_end is null or date_start <= date_end)",
         "El inicio del contrato no puede ser posterior al término."),
        ("legacy_unique", "unique(legacy_contract_id)", "Ese contrato anterior ya fue migrado."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.producer.purchase.contract") or _("Nuevo")
        return super().create(vals_list)

    @api.depends("revision_ids")
    def _compute_is_superseded(self):
        for contract in self:
            contract.is_superseded = bool(contract.revision_ids)

    @api.depends("product_line_ids.quantity", "product_line_ids.amount",
                 "installment_ids.amount", "installment_ids.active")
    def _compute_totals(self):
        for contract in self:
            contract.quantity_total = sum(contract.product_line_ids.mapped("quantity"))
            contract.amount_total = sum(contract.product_line_ids.mapped("amount"))
            contract.scheduled_total = sum(contract.installment_ids.filtered("active").mapped("amount"))

    def write(self, vals):
        if "state" in vals and not self.env.su:
            raise UserError(_("Cambie el estado con los botones del contrato."))
        frozen = {"partner_id", "currency_id", "company_id", "date_start", "date_end"}
        if frozen.intersection(vals) and any(contract.state != "draft" for contract in self):
            raise UserError(_("Cree una revisión para cambiar los datos de un contrato confirmado."))
        if {"journal_id", "provision_account_id", "accounting_date"}.intersection(vals) and any(
                contract.accounting_move_id for contract in self):
            raise UserError(_("No puede cambiar la configuración de un asiento ya generado."))
        return super().write(vals)

    def _check_schedule(self):
        self.ensure_one()
        products = self.product_line_ids
        installments = self.installment_ids.filtered("active")
        if not products or not installments:
            raise ValidationError(_("Agregue productos y un calendario de pago antes de confirmar."))
        for product in products:
            if not product.species_id:
                raise ValidationError(_("Indique la especie de cada producto del contrato."))
            allocated = installments.filtered(lambda line: line.product_line_id == product)
            quantity = sum(allocated.mapped("quantity"))
            if float_compare(quantity, product.quantity, precision_digits=4):
                raise ValidationError(_(
                    "Las cuotas de %s suman %s, pero el producto contratado indica %s."
                ) % (product.product_id.display_name, quantity, product.quantity))
        if not self.currency_id.is_zero(self.scheduled_total - self.amount_total):
            raise ValidationError(_("El neto programado debe coincidir con el neto de productos."))

    def action_confirm(self):
        for contract in self:
            if contract.state != "draft":
                raise UserError(_("Sólo se confirma un contrato en Borrador."))
            contract._check_schedule()
            contract.sudo().state = "confirmed"
        return True

    def action_close(self):
        for contract in self:
            if contract.state != "confirmed":
                raise UserError(_("Sólo se cierra un contrato Confirmado."))
            contract.sudo().state = "closed"
        return True

    def action_revise(self):
        self.ensure_one()
        if self.state != "confirmed" or self.is_superseded:
            raise UserError(_("Sólo puede revisar la última versión Confirmada."))
        pending = self.installment_ids.filtered(lambda line: line.active and line.state != "accounted")
        if not pending:
            raise UserError(_("No hay cuotas pendientes para una nueva versión."))
        revision_values = {
            "company_id": self.company_id.id, "partner_id": self.partner_id.id,
            "currency_id": self.currency_id.id, "date_start": self.date_start,
            "date_end": self.date_end, "operation_type": self.operation_type,
            "reference": self.reference, "notes": self.notes,
            "parent_id": self.id, "version": self.version + 1,
        }
        if self.env.su or self.env.user.has_group("account.group_account_user"):
            revision_values.update({
                "journal_id": self.journal_id.id,
                "provision_account_id": self.provision_account_id.id,
                "accounting_date": self.accounting_date,
            })
        new_contract = self.create(revision_values)
        product_map = {}
        for old_product in self.product_line_ids:
            quantity = sum(pending.filtered(lambda line: line.product_line_id == old_product).mapped("quantity"))
            if not quantity:
                continue
            product_map[old_product.id] = self.env["step.producer.purchase.contract.product"].sudo().create({
                "contract_id": new_contract.id, "product_id": old_product.product_id.id,
                "species_id": old_product.species_id.id,
                "variety_id": old_product.variety_id.id,
                "category_id": old_product.category_id.id,
                "caliber_id": old_product.caliber_id.id,
                "description": old_product.description, "quantity": quantity,
                "uom_id": old_product.uom_id.id, "price_unit": old_product.price_unit,
                "debit_account_id": old_product.sudo().debit_account_id.id,
            })
        for old_line in pending:
            self.env["step.producer.purchase.contract.installment"].create({
                "contract_id": new_contract.id,
                "product_line_id": product_map[old_line.product_line_id.id].id,
                "sequence": old_line.sequence, "quantity": old_line.quantity,
                "date_due": old_line.date_due,
                "validation_criteria": old_line.validation_criteria,
            })
        pending.sudo().write({"active": False})
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "view_mode": "form", "res_id": new_contract.id}

    def action_account(self):
        if not self.env.su and not self.env.user.has_group("account.group_account_user"):
            raise UserError(_("Sólo un usuario de Contabilidad puede contabilizar contratos."))
        for contract in self:
            self.env.cr.execute("SELECT id FROM step_producer_purchase_contract WHERE id = %s FOR UPDATE",
                                (contract.id,))
            contract.invalidate_recordset(["accounting_move_id"])
            if contract.state != "confirmed" or contract.accounting_move_id:
                raise UserError(_("Confirme un contrato sin asiento previo para contabilizarlo."))
            contract._check_schedule()
            if contract.currency_id.is_zero(contract.amount_total):
                raise UserError(_("El neto del contrato debe ser positivo para contabilizarlo."))
            if not contract.journal_id or not contract.provision_account_id:
                raise UserError(_("Seleccione el diario de contrato y la cuenta de provisión."))
            if contract.journal_id.company_id != contract.company_id:
                raise UserError(_("El diario debe pertenecer a la empresa del contrato."))
            if contract.journal_id.type not in ("general", "purchase"):
                raise UserError(_("Use un diario general o de compras para esta provisión."))
            if contract.journal_id.currency_id and contract.journal_id.currency_id != contract.currency_id:
                raise UserError(_("La moneda del diario debe coincidir con la del contrato."))
            allowed_accounts = contract.journal_id.account_control_ids
            if allowed_accounts:
                debit_accounts = contract.company_id.step_producer_advance_account_id
                disallowed = (debit_accounts | contract.provision_account_id) - allowed_accounts
                if disallowed:
                    raise UserError(_(
                        "El diario %(journal)s restringe las cuentas permitidas. "
                        "Revise la cuenta de anticipo en Ajustes contables de Productores "
                        "y la cuenta de provisión del contrato; después configure en "
                        "Contabilidad → Configuración → Diarios → Ajustes avanzados → "
                        "Cuentas permitidas las cuentas aprobadas por Contabilidad. "
                        "Cuentas rechazadas: %(accounts)s.",
                        journal=contract.journal_id.display_name,
                        accounts=", ".join(sorted(disallowed.mapped("display_name")))))
            if contract.parent_id.accounting_move_id and (
                    not contract.parent_id.pending_reversal_move_id or
                    contract.parent_id.pending_reversal_move_id.state != "posted"):
                raise UserError(_(
                    "Vincule y publique la reversa de cuotas pendientes de la versión anterior."
                ))
            date = contract.accounting_date or fields.Date.context_today(contract)
            currency = contract.currency_id
            company = contract.company_id
            advance_product = company.step_producer_advance_product_id
            advance_account = company.step_producer_advance_account_id
            if not advance_product or not advance_account:
                raise UserError(_("Configure el concepto y la cuenta de anticipo en Productores → Configuraciones → Ajustes contables."))
            company._check_contract_advance_company()
            if company not in contract.provision_account_id.company_ids or contract.provision_account_id.deprecated:
                raise UserError(_("La cuenta de provisión debe estar vigente y pertenecer a la empresa del contrato."))
            if contract.provision_account_id.account_type not in ("liability_current", "liability_non_current", "liability_payable"):
                raise UserError(_("Use una cuenta de pasivo para la provisión del contrato."))
            lines = []
            installments = contract.installment_ids.filtered("active")
            for installment in installments:
                amount_currency = currency.round(installment.amount)
                if currency.is_zero(amount_currency):
                    continue
                balance = currency._convert(amount_currency, company.currency_id, company, date)
                common = {
                    "name": installment.advance_description,
                    "partner_id": contract.partner_id.id,
                    "currency_id": currency.id, "date_maturity": installment.date_due,
                    "step_producer_installment_id": installment.id,
                }
                lines.extend([
                    (0, 0, dict(common, account_id=advance_account.id,
                                product_id=advance_product.id,
                                amount_currency=amount_currency, debit=balance, credit=0.0)),
                    (0, 0, dict(common, account_id=contract.provision_account_id.id,
                                amount_currency=-amount_currency, debit=0.0, credit=balance)),
                ])
            move = self.env["account.move"].with_company(company).create({
                "move_type": "entry", "date": date, "journal_id": contract.journal_id.id,
                "company_id": company.id, "partner_id": contract.partner_id.id,
                "ref": contract.name, "line_ids": lines,
            })
            move.action_post()
            contract.accounting_move_id = move
            for installment in installments:
                installment.provision_line_id = move.line_ids.filtered(
                    lambda line: line.step_producer_installment_id == installment
                    and line.account_id == contract.provision_account_id)
        return True

    def action_open_account_move(self):
        self.ensure_one()
        if not self.accounting_move_id:
            raise UserError(_("El contrato aún no tiene un asiento de provisión."))
        return {"type": "ir.actions.act_window", "res_model": "account.move",
                "view_mode": "form", "res_id": self.accounting_move_id.id}


class ProducerPurchaseContractProduct(models.Model):
    _name = "step.producer.purchase.contract.product"
    _description = "Producto de contrato de compra"
    _inherit = ["analytic.mixin"]
    _rec_name = "description"
    _order = "contract_id, sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one("step.producer.purchase.contract", required=True,
                                  ondelete="cascade", index=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True, readonly=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True,
                                 check_company=True, domain="[('step_export_enabled', '=', True)]")
    species_id = fields.Many2one("step.especie", string="Especie", index=True)
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    category_id = fields.Many2one("step.packing.fruit.category", string="Categoría")
    caliber_id = fields.Many2one("step.packing.fruit.caliber", string="Calibre")
    description = fields.Char(string="Descripción")
    quantity = fields.Float(string="Cantidad", required=True, digits=(16, 4))
    ordered_quantity = fields.Float(string="Ordenado", compute="_compute_ordered_quantity",
                                    digits=(16, 4))
    uom_id = fields.Many2one("uom.uom", string="UdM", required=True)
    price_unit = fields.Float(string="Precio unitario", required=True, digits=(16, 4))
    amount = fields.Monetary(string="Neto", compute="_compute_amount", store=True,
                             currency_field="currency_id")
    debit_account_id = fields.Many2one("account.account", string="Cuenta de cargo (debe)",
                                       check_company=True, groups="account.group_account_user")
    purchase_order_line_ids = fields.One2many(
        "purchase.order.line", "step_producer_contract_product_id", string="Líneas de compra")

    @api.depends("product_id.display_name", "species_id.name", "variety_id.name", "category_id.name", "caliber_id.name")
    def _compute_display_name(self):
        for line in self:
            parts = [line.product_id.display_name]
            parts += [item.display_name for item in (line.variety_id, line.category_id, line.caliber_id) if item]
            line.display_name = " / ".join(part for part in parts if part) or _("Producto del contrato")

    @api.constrains("product_id")
    def _check_export_product(self):
        for line in self:
            if not line.product_id.step_export_enabled:
                raise ValidationError(_("Seleccione un producto marcado como Es exportación."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.species_id = line.product_id.product_tmpl_id.step_export_species_id
                line.uom_id = line.product_id.uom_po_id
                line.description = line.product_id.display_name

    @api.depends("quantity", "price_unit")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit

    @api.depends("purchase_order_line_ids.product_qty", "purchase_order_line_ids.order_id.state")
    def _compute_ordered_quantity(self):
        for line in self:
            order_lines = line.purchase_order_line_ids.filtered(
                lambda order_line: order_line.order_id.state in ("purchase", "done"))
            line.ordered_quantity = sum(order_lines.mapped("product_qty"))

    @api.constrains("quantity", "price_unit")
    def _check_values(self):
        for line in self:
            if line.quantity <= 0 or line.price_unit < 0:
                raise ValidationError(_("La cantidad debe ser positiva y el precio no puede ser negativo."))

    @api.constrains("species_id", "variety_id", "category_id", "caliber_id",
                    "product_id", "contract_id")
    def _check_variant(self):
        for line in self:
            if line.variety_id and line.variety_id.especie_id != line.species_id:
                raise ValidationError(_("La variedad debe pertenecer a la especie elegida."))
            if line.caliber_id and line.caliber_id.species_id and line.caliber_id.species_id != line.species_id:
                raise ValidationError(_("El calibre debe pertenecer a la especie elegida."))
            key = (line.species_id.id, line.product_id.id, line.variety_id.id,
                   line.category_id.id, line.caliber_id.id)
            siblings = line.contract_id.product_line_ids - line
            if any((other.species_id.id, other.product_id.id, other.variety_id.id,
                    other.category_id.id, other.caliber_id.id) == key for other in siblings):
                raise ValidationError(_("Ya existe una línea con la misma combinación de especie, producto, variedad, categoría y calibre."))

    @api.model
    def resolve_variant_price(self, contract, product, species, variety=False,
                              category=False, caliber=False):
        """Return the most specific applicable contract line; refuse equal-ranked ties."""
        variety_id = variety.id if variety else False
        category_id = category.id if category else False
        caliber_id = caliber.id if caliber else False
        candidates = contract.product_line_ids.filtered(
            lambda line: line.product_id == product and line.species_id == species
            and (not line.variety_id or line.variety_id.id == variety_id)
            and (not line.category_id or line.category_id.id == category_id)
            and (not line.caliber_id or line.caliber_id.id == caliber_id))
        if not candidates:
            raise UserError(_("El contrato no tiene precio para esta combinación de fruta."))
        ranked = candidates.sorted(
            key=lambda line: sum(bool(value) for value in
                                 (line.variety_id, line.category_id, line.caliber_id)),
            reverse=True)
        best = ranked[0]
        score = sum(bool(value) for value in
                    (best.variety_id, best.category_id, best.caliber_id))
        if len(ranked) > 1 and sum(bool(value) for value in
                                   (ranked[1].variety_id, ranked[1].category_id,
                                    ranked[1].caliber_id)) == score:
            raise UserError(_("Hay dos precios igual de específicos para esta fruta."))
        return best

    def write(self, vals):
        if any(line.contract_id.state != "draft" for line in self) and set(vals) & {
                "product_id", "species_id", "variety_id", "category_id", "caliber_id",
                "quantity", "uom_id", "price_unit", "analytic_distribution",
                "description"}:
            raise UserError(_("Cree una revisión para cambiar productos de un contrato confirmado."))
        if "debit_account_id" in vals:
            if any(line.contract_id.accounting_move_id for line in self):
                raise UserError(_("No cambie la cuenta de cargo después de contabilizar el contrato."))
            if not self.env.su and not self.env.user.has_group("account.group_account_user"):
                raise UserError(_("Sólo Contabilidad puede cambiar la cuenta de cargo."))
        return super().write(vals)

    def unlink(self):
        if any(line.contract_id.state != "draft" for line in self):
            raise UserError(_("No se eliminan productos de un contrato confirmado."))
        return super().unlink()


class ProducerPurchaseContractInstallment(models.Model):
    _name = "step.producer.purchase.contract.installment"
    _description = "Cuota de contrato de compra de productor"
    _order = "contract_id, sequence, date_due, id"
    _check_company_auto = True

    contract_id = fields.Many2one("step.producer.purchase.contract", required=True,
                                  ondelete="cascade", index=True)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True, readonly=True)
    sequence = fields.Integer(string="N°", default=10)
    product_line_id = fields.Many2one("step.producer.purchase.contract.product",
                                      string="Producto contratado", required=True,
                                      domain="[('contract_id', '=', contract_id)]")
    advance_description = fields.Char(string="Concepto de anticipo", compute="_compute_advance_description")
    advance_product_id = fields.Many2one(related="company_id.step_producer_advance_product_id",
                                        string="Producto de anticipo")
    provision_line_id = fields.Many2one("account.move.line", string="Apunte de provisión",
                                       readonly=True, copy=False, check_company=True)

    @api.depends("contract_id.name")
    def _compute_advance_description(self):
        for line in self:
            line.advance_description = _("Anticipo contrato %s") % line.contract_id.name

    product_id = fields.Many2one(related="product_line_id.product_id", string="Producto")
    quantity = fields.Float(string="Cantidad", required=True, digits=(16, 4))
    uom_id = fields.Many2one(related="product_line_id.uom_id", string="UdM")
    price_unit = fields.Float(related="product_line_id.price_unit", string="Precio", digits=(16, 4))
    amount = fields.Monetary(string="Neto a pago", compute="_compute_amount", store=True,
                             currency_field="currency_id")
    date_due = fields.Date(string="Vencimiento", required=True)
    validation_criteria = fields.Char(string="Criterio de validación")
    state = fields.Selection([("created", "Creado"), ("approved", "Aprobado"),
                              ("accounted", "Contabilizado")], default="created", required=True)
    active = fields.Boolean(default=True)
    payment_move_id = fields.Many2one("account.move", string="Asiento del pago", check_company=True,
                                      groups="account.group_account_user")
    reversal_move_id = fields.Many2one("account.move", string="Reversa de provisión", check_company=True,
                                       groups="account.group_account_user")

    @api.depends("quantity", "price_unit")
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.price_unit

    @api.constrains("contract_id", "product_line_id", "quantity")
    def _check_values(self):
        for line in self:
            if line.product_line_id.contract_id != line.contract_id:
                raise ValidationError(_("La cuota debe usar un producto del mismo contrato."))
            if line.quantity <= 0:
                raise ValidationError(_("La cantidad de la cuota debe ser positiva."))

    def write(self, vals):
        if "state" in vals and not self.env.su:
            raise UserError(_("Cambie el estado con las acciones de la cuota."))
        if "active" in vals and not self.env.su:
            raise UserError(_("Las cuotas pendientes se archivan al revisar el contrato."))
        frozen = {"product_line_id", "quantity", "date_due", "validation_criteria"}
        if frozen.intersection(vals) and any(line.contract_id.state != "draft" for line in self):
            raise UserError(_("Cree una revisión para cambiar cuotas de un contrato confirmado."))
        return super().write(vals)

    def unlink(self):
        if any(line.contract_id.state != "draft" for line in self):
            raise UserError(_("No se eliminan cuotas de un contrato confirmado."))
        return super().unlink()

    def action_approve(self):
        for line in self:
            if line.state != "created" or line.contract_id.state != "confirmed":
                raise UserError(_("Confirme el contrato antes de aprobar cuotas creadas."))
            line.sudo().state = "approved"
        return True

    def action_mark_accounted(self):
        if not self.env.su and not self.env.user.has_group("account.group_account_user"):
            raise UserError(_("Sólo Contabilidad puede marcar cuotas como contabilizadas."))
        for line in self:
            if line.state != "approved" or not line.contract_id.accounting_move_id:
                raise UserError(_("Apruebe la cuota y contabilice primero el contrato."))
            if not line.payment_move_id or line.payment_move_id.state != "posted":
                raise UserError(_("Vincule un asiento de pago publicado."))
            if not line.reversal_move_id or line.reversal_move_id.state != "posted":
                raise UserError(_("Vincule la reversa parcial de provisión publicada."))
            line.sudo().state = "accounted"
        return True


class ProducerContractMoveLine(models.Model):
    _inherit = "account.move.line"

    step_producer_installment_id = fields.Many2one(
        "step.producer.purchase.contract.installment", string="Cuota de anticipo de contrato",
        copy=False, index=True, check_company=True, ondelete="restrict")
