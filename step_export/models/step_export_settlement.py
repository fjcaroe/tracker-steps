"""Receiver and producer settlements with traceable accounting adjustments."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def _step_liquidation_kg(self):
        self.ensure_one()
        return self.kilos_total

    def _step_producer_shares(self):
        self.ensure_one()
        return [(self.owner_id, 1.0)] if self.owner_id else []


class ReceiverSettlement(models.Model):
    _name = "step.export.receiver.settlement"
    _description = "Liquidación de recibidor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Número", default="Nuevo", readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Creada"), ("validated", "Validada"),
        ("accounted", "Contabilizada"),
    ], default="draft", required=True, tracking=True, copy=False)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    receiver_id = fields.Many2one("res.partner", string="Recibidor", required=True)
    receiver_reference = fields.Char(string="Número liquidación recibidor")
    sales_program_id = fields.Many2one("step.export.sales.program", string="Programa de ventas", required=True)
    season_id = fields.Many2one(related="sales_program_id.season_id", store=True)
    species_id = fields.Many2one(related="sales_program_id.species_id", store=True)
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one("res.currency", string="Moneda recibidor", required=True,
                                  default=lambda self: self.env.ref("base.USD"))
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))
    rate_to_usd = fields.Float(string="USD por unidad", digits=(16, 6), required=True)
    line_ids = fields.One2many("step.export.receiver.settlement.line", "settlement_id", string="Embarques")
    producer_settlement_ids = fields.One2many("step.export.producer.settlement", "receiver_settlement_id",
                                              string="Liquidaciones productores")
    adjustment_move_ids = fields.One2many("account.move", "step_export_settlement_id", string="Notas de ajuste")
    total_sales_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)
    total_fob_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)
    total_difference_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)

    _sql_constraints = [
        ("settlement_company_name_unique", "unique(company_id, name)", "La liquidación ya existe."),
        ("settlement_rate_positive", "check(rate_to_usd > 0)", "El tipo de cambio debe ser positivo."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.export.receiver.settlement") or "Nuevo"
            if not vals.get("rate_to_usd"):
                currency = self.env["res.currency"].browse(vals.get("currency_id")) if vals.get("currency_id") else self.env.ref("base.USD")
                company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
                vals["rate_to_usd"] = currency._convert(1, self.env.ref("base.USD"), company,
                                                         vals.get("date") or fields.Date.today())
        return super().create(vals_list)

    @api.onchange("currency_id", "date")
    def _onchange_rate(self):
        for record in self:
            if record.currency_id:
                record.rate_to_usd = record.currency_id._convert(
                    1, record.usd_currency_id or record.env.ref("base.USD"),
                    record.company_id or record.env.company, record.date or fields.Date.today())

    @api.depends("line_ids.sales_usd", "line_ids.fob_usd", "line_ids.difference_usd")
    def _compute_totals(self):
        for record in self:
            record.total_sales_usd = sum(record.line_ids.mapped("sales_usd"))
            record.total_fob_usd = sum(record.line_ids.mapped("fob_usd"))
            record.total_difference_usd = sum(record.line_ids.mapped("difference_usd"))

    def write(self, vals):
        locked = {"receiver_id", "sales_program_id", "currency_id", "rate_to_usd",
                  "line_ids", "date", "company_id"}
        if locked.intersection(vals) and any(r.state != "draft" for r in self):
            raise UserError(_("Una liquidación validada no puede modificarse."))
        return super().write(vals)

    def action_validate(self):
        for record in self:
            if record.state != "draft" or not record.line_ids:
                raise UserError(_("Ingrese al menos un embarque en la liquidación creada."))
            if record.receiver_id != record.sales_program_id.partner_id:
                raise ValidationError(_("El recibidor debe coincidir con el programa."))
            for line in record.line_ids:
                shipment = line.shipment_id
                if shipment.settlement_id or shipment.state != "invoiced":
                    raise ValidationError(_("Solo se liquidan embarques facturados y sin liquidación previa."))
                if shipment.sales_program_id != record.sales_program_id or shipment.company_id != record.company_id:
                    raise ValidationError(_("El embarque debe pertenecer al programa y empresa de la liquidación."))
                if line.sales_amount < 0 or line.expenses_usd < 0 or not 0 <= line.commission_rate <= 1:
                    raise ValidationError(_("Ventas y gastos no pueden ser negativos; comisión entre 0 y 100 %."))
                if line.use_grade_detail:
                    selected_tags = line.grade_line_ids.mapped("tag_ids")
                    if set(selected_tags.ids) != set(shipment.tag_ids.ids):
                        raise ValidationError(_("El detalle por calibre debe incluir cada tarja exactamente una vez."))
                    if sum(len(grade.tag_ids) for grade in line.grade_line_ids) != len(shipment.tag_ids):
                        raise ValidationError(_("Una tarja no puede repetirse en dos calidades o calibres."))
                    if any(grade.sales_amount <= 0 for grade in line.grade_line_ids):
                        raise ValidationError(_("Ingrese las ventas por categoría y calibre."))
                    if not float_is_zero(sum(line.grade_line_ids.mapped("kg_qty")) -
                                         sum(tag._step_liquidation_kg() for tag in shipment.tag_ids),
                                         precision_rounding=0.001):
                        raise ValidationError(_("Los kilos por calibre deben coincidir con las tarjas."))
                if line.fob_usd < 0:
                    raise ValidationError(_("El FOB no puede ser negativo."))
                if line.invoice_id.state != "posted" or line.invoice_id.move_type != "out_invoice":
                    raise ValidationError(_("Seleccione una factura de cliente publicada."))
                if any(not tag._step_producer_shares() for tag in shipment.tag_ids):
                    raise ValidationError(_("Todas las tarjas deben identificar al productor para generar su liquidación."))
                if any(tag._step_liquidation_kg() <= 0 for tag in shipment.tag_ids):
                    raise ValidationError(_("Todas las tarjas deben tener kilos positivos para distribuir la liquidación."))
                shipment.write({"settlement_id": record.id, "state": "settled"})
                shipment.tag_ids.write({"step_export_settlement_ids": [(4, record.id)]})
            record.state = "validated"
            record._generate_producer_settlements()
        return True

    def action_prepare_grade_lines(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Prepare el detalle por calibre antes de validar."))
            for line in record.line_ids:
                if line.grade_line_ids:
                    continue
                tags = line.shipment_id.tag_ids
                total_kg = sum(tag._step_liquidation_kg() for tag in tags)
                if not total_kg:
                    raise ValidationError(_("El embarque necesita tarjas con kilos para detallar la liquidación."))
                groups = {}
                for tag in tags:
                    key = (tag.fruit_category_id.id, tag.fruit_caliber_id.id)
                    groups.setdefault(key, self.env["stock.quant.package"])
                    groups[key] |= tag
                for (category_id, caliber_id), group_tags in groups.items():
                    kg = sum(tag._step_liquidation_kg() for tag in group_tags)
                    self.env["step.export.receiver.settlement.grade"].create({
                        "line_id": line.id, "category_id": category_id or False,
                        "caliber_id": caliber_id or False,
                        "tag_ids": [(6, 0, group_tags.ids)], "kg_qty": kg,
                        "sales_amount": line.sales_amount * kg / total_kg,
                        "expense_per_kg_usd": line.expenses_usd / total_kg,
                        "commission_rate": line.commission_rate,
                    })
                line.use_grade_detail = True
        return True

    def _generate_producer_settlements(self):
        for record in self:
            allocation = {}
            for line in record.line_ids:
                shipment = line.shipment_id
                tags = shipment.tag_ids.filtered(
                    lambda tag: tag._step_producer_shares() and tag._step_liquidation_kg() > 0)
                total_kg = sum(tag._step_liquidation_kg() for tag in tags)
                for tag in tags:
                    tag_kg = tag._step_liquidation_kg()
                    if line.use_grade_detail:
                        grade = line.grade_line_ids.filtered(lambda row: tag in row.tag_ids)
                        group_kg = sum(row._step_liquidation_kg() for row in grade.tag_ids)
                        grade_fob = grade.fob_usd * tag_kg / group_kg
                        claim_share = line.claim_usd * tag_kg / total_kg
                        amount = grade_fob - claim_share
                    else:
                        amount = line.fob_usd * tag_kg / total_kg
                    for producer, share in tag._step_producer_shares():
                        allocation.setdefault(producer.id, []).append(
                            (tag, amount * share, tag_kg * share))
            for producer_id, entries in allocation.items():
                self.env["step.export.producer.settlement"].create({
                    "receiver_settlement_id": record.id, "producer_id": producer_id,
                    "line_ids": [(0, 0, {"tag_id": tag.id, "allocated_fob_usd": amount,
                                          "kg_qty": kg})
                                 for tag, amount, kg in entries],
                })

    def action_account(self):
        for record in self:
            if record.state != "validated":
                raise UserError(_("Valide la liquidación antes de contabilizar."))
            if not record.adjustment_move_ids:
                for line in record.line_ids:
                    if float_is_zero(line.difference_usd, precision_rounding=record.usd_currency_id.rounding):
                        continue
                    if not line.shipment_id.ivv_folio:
                        raise UserError(_("Registre el IVV del embarque antes de emitir la nota de ajuste."))
                    invoice_line = line.invoice_id.invoice_line_ids.filtered(
                        lambda item: item.account_id and item.display_type == "product")[:1]
                    if not invoice_line:
                        raise UserError(_("La factura inicial necesita una línea de ingreso para crear la nota de ajuste."))
                    if line.external_adjustment_folio:
                        record._post_external_adjustment(line, invoice_line)
                    else:
                        record._post_odoo_adjustment(line, invoice_line)
            if any(move.state != "posted" for move in record.adjustment_move_ids):
                raise UserError(_("Publique todas las notas de ajuste antes de cerrar la liquidación."))
            record.state = "accounted"
        return True

    def _post_external_adjustment(self, line, invoice_line):
        """Book an externally issued 111/112 without asking Odoo to emit it again."""
        self.ensure_one()
        journal = self.company_id.step_export_adjustment_journal_id or self.env["account.journal"].search([
            ("company_id", "=", self.company_id.id), ("type", "=", "general")], limit=1)
        receivable = line.invoice_id.line_ids.filtered(
            lambda item: item.account_id.account_type == "asset_receivable")[:1].account_id
        if not journal or not receivable:
            raise UserError(_("Configure un diario general y una cuenta por cobrar para registrar la nota externa."))
        amount = self.usd_currency_id._convert(
            abs(line.difference_usd), self.company_id.currency_id, self.company_id, self.date)
        positive = line.difference_usd > 0
        move = self.env["account.move"].create({
            "move_type": "entry", "date": self.date, "journal_id": journal.id,
            "company_id": self.company_id.id,
            "ref": "%s / IVV %s / DTE externo %s / factura %s" % (
                self.name, line.shipment_id.ivv_folio, line.external_adjustment_folio,
                line.invoice_id.name),
            "step_export_shipment_id": line.shipment_id.id,
            "step_export_settlement_id": self.id,
            "line_ids": [(0, 0, {
                "name": _("Ajuste por cobrar %s") % line.shipment_id.shipment_number,
                "account_id": receivable.id, "partner_id": self.receiver_id.id,
                "debit": amount if positive else 0, "credit": amount if not positive else 0,
                "currency_id": self.usd_currency_id.id,
                "amount_currency": line.difference_usd,
            }), (0, 0, {
                "name": _("Ajuste ingreso exportación %s") % line.shipment_id.shipment_number,
                "account_id": invoice_line.account_id.id,
                "debit": amount if not positive else 0, "credit": amount if positive else 0,
                "currency_id": self.usd_currency_id.id,
                "amount_currency": -line.difference_usd,
            })],
        })
        move.action_post()
        return move

    def _post_odoo_adjustment(self, line, invoice_line):
        self.ensure_one()
        move_type = "out_invoice" if line.difference_usd > 0 else "out_refund"
        if (self.company_id.country_id.code == "CL" and
                "l10n_latam_document_type_id" not in self.env["account.move"]._fields):
            raise UserError(_("Configure DTE de exportación o registre el folio de la nota externa."))
        move = self.env["account.move"].create({
            "move_type": move_type, "partner_id": self.receiver_id.id,
            "company_id": self.company_id.id,
            "journal_id": (self.company_id.step_export_sale_journal_id or line.invoice_id.journal_id).id,
            "currency_id": self.usd_currency_id.id, "invoice_date": self.date,
            "invoice_origin": line.invoice_id.name,
            "ref": "%s / IVV %s" % (self.name, line.shipment_id.ivv_folio),
            "step_export_shipment_id": line.shipment_id.id,
            "step_export_settlement_id": self.id,
            "invoice_line_ids": [(0, 0, {
                "name": _("Ajuste precio FOB %s / factura %s") % (
                    line.shipment_id.shipment_number, line.invoice_id.name),
                "account_id": invoice_line.account_id.id,
                "quantity": 1, "price_unit": abs(line.difference_usd),
                "tax_ids": [(6, 0, invoice_line.tax_ids.ids)],
            })],
        })
        if "l10n_latam_document_type_id" in move._fields and self.company_id.country_id.code == "CL":
            code = "111" if line.difference_usd > 0 else "112"
            document_type = self.env["l10n_latam.document.type"].search([("code", "=", code)], limit=1)
            if not document_type:
                raise UserError(_("Configure el tipo DTE de exportación %s antes de contabilizar.") % code)
            move.l10n_latam_document_type_id = document_type
        move.action_post()
        return move


class ReceiverSettlementLine(models.Model):
    _name = "step.export.receiver.settlement.line"
    _description = "Embarque en liquidación de recibidor"

    settlement_id = fields.Many2one("step.export.receiver.settlement", required=True, ondelete="cascade", index=True)
    shipment_id = fields.Many2one("step.export.export", string="Embarque", required=True)
    invoice_id = fields.Many2one("account.move", string="Factura inicial", required=True)
    external_adjustment_folio = fields.Char(string="Folio nota externa",
                                            help="Registre el folio 111/112 si la nota se emitió fuera de Odoo.")
    sales_amount = fields.Monetary(string="Ventas exterior", currency_field="currency_id", required=True)
    currency_id = fields.Many2one(related="settlement_id.currency_id")
    usd_currency_id = fields.Many2one(related="settlement_id.usd_currency_id")
    sales_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    expenses_usd = fields.Monetary(string="Gastos manuales USD", currency_field="usd_currency_id")
    calculated_expenses_usd = fields.Monetary(string="Gastos exterior USD", currency_field="usd_currency_id",
                                              compute="_compute_amounts", store=True)
    commission_rate = fields.Float(string="Comisión (0 a 1)", digits=(8, 4))
    commission_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    claim_usd = fields.Monetary(string="Reclamos aceptados USD", currency_field="usd_currency_id",
                                compute="_compute_claim", store=True)
    fob_usd = fields.Monetary(string="FOB USD", currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    initial_invoice_usd = fields.Monetary(string="Facturado inicial USD", currency_field="usd_currency_id",
                                          compute="_compute_amounts", store=True)
    difference_usd = fields.Monetary(string="IVV USD", currency_field="usd_currency_id",
                                     compute="_compute_amounts", store=True)
    use_grade_detail = fields.Boolean(string="Detalle por calibre")
    grade_line_ids = fields.One2many("step.export.receiver.settlement.grade", "line_id",
                                     string="Distribución por categoría y calibre")

    _sql_constraints = [
        ("settlement_shipment_unique", "unique(shipment_id)", "El embarque ya está en una liquidación."),
    ]

    @api.depends("shipment_id.claim_ids.state", "shipment_id.claim_ids.accepted_amount_usd",
                 "shipment_id.claim_ids.shipment_ids", "shipment_id.kg_qty")
    def _compute_claim(self):
        for line in self:
            amount = 0
            for claim in line.shipment_id.claim_ids.filtered(lambda rec: rec.state == "accepted"):
                total_kg = sum(claim.shipment_ids.mapped("kg_qty"))
                weight = line.shipment_id.kg_qty / total_kg if total_kg else 1 / len(claim.shipment_ids)
                amount += claim.accepted_amount_usd * weight
            line.claim_usd = amount

    @api.depends("sales_amount", "settlement_id.rate_to_usd", "expenses_usd", "commission_rate",
                 "use_grade_detail", "grade_line_ids.sales_usd", "grade_line_ids.expenses_usd",
                 "grade_line_ids.commission_usd", "grade_line_ids.fob_usd",
                 "claim_usd", "invoice_id.amount_total", "invoice_id.currency_id", "settlement_id.date")
    def _compute_amounts(self):
        for line in self:
            if line.use_grade_detail:
                line.sales_usd = sum(line.grade_line_ids.mapped("sales_usd"))
                line.calculated_expenses_usd = sum(line.grade_line_ids.mapped("expenses_usd"))
                line.commission_usd = sum(line.grade_line_ids.mapped("commission_usd"))
                line.fob_usd = sum(line.grade_line_ids.mapped("fob_usd")) - line.claim_usd
            else:
                line.sales_usd = line.sales_amount * line.settlement_id.rate_to_usd
                line.calculated_expenses_usd = line.expenses_usd
                line.commission_usd = line.sales_usd * line.commission_rate
                line.fob_usd = line.sales_usd - line.claim_usd - line.expenses_usd - line.commission_usd
            line.initial_invoice_usd = line.invoice_id.currency_id._convert(
                line.invoice_id.amount_untaxed, line.usd_currency_id, line.settlement_id.company_id,
                line.invoice_id.invoice_date or line.settlement_id.date) if line.invoice_id else 0
            line.difference_usd = line.fob_usd - line.initial_invoice_usd

    @api.constrains("shipment_id", "invoice_id")
    def _check_invoice(self):
        for line in self:
            if line.invoice_id and line.shipment_id and line.invoice_id.step_export_shipment_id != line.shipment_id:
                raise ValidationError(_("La factura debe pertenecer al embarque seleccionado."))

    def write(self, vals):
        if vals and any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No modifique líneas de liquidación validadas."))
        return super().write(vals)

    def unlink(self):
        if any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No elimine líneas de liquidación validadas."))
        return super().unlink()


class ReceiverSettlementGrade(models.Model):
    _name = "step.export.receiver.settlement.grade"
    _description = "Categoría y calibre liquidados por recibidor"

    line_id = fields.Many2one("step.export.receiver.settlement.line", required=True, ondelete="cascade")
    category_id = fields.Many2one("step.management.fruit.category", string="Categoría")
    caliber_id = fields.Many2one("step.management.fruit.caliber", string="Calibre")
    tag_ids = fields.Many2many("stock.quant.package", string="Tarjas")
    kg_qty = fields.Float(string="Kilos liquidados", required=True)
    currency_id = fields.Many2one(related="line_id.currency_id")
    usd_currency_id = fields.Many2one(related="line_id.usd_currency_id")
    sales_amount = fields.Monetary(string="Ventas exterior", currency_field="currency_id")
    expense_per_kg_usd = fields.Float(string="Gasto exterior USD/kg", digits=(16, 4))
    commission_rate = fields.Float(string="Comisión (0 a 1)", digits=(8, 4))
    sales_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    expenses_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    commission_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)
    fob_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amounts", store=True)

    @api.depends("kg_qty", "sales_amount", "line_id.settlement_id.rate_to_usd",
                 "expense_per_kg_usd", "commission_rate")
    def _compute_amounts(self):
        for row in self:
            row.sales_usd = row.sales_amount * row.line_id.settlement_id.rate_to_usd
            row.expenses_usd = row.kg_qty * row.expense_per_kg_usd
            row.commission_usd = row.sales_usd * row.commission_rate
            row.fob_usd = row.sales_usd - row.expenses_usd - row.commission_usd

    @api.constrains("kg_qty", "sales_amount", "expense_per_kg_usd", "commission_rate")
    def _check_values(self):
        for row in self:
            if min(row.kg_qty, row.sales_amount, row.expense_per_kg_usd) < 0 or not 0 <= row.commission_rate <= 1:
                raise ValidationError(_("Los kilos, ventas y gastos deben ser positivos; comisión entre 0 y 100 %."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.receiver.settlement.line"].browse([
            vals["line_id"] for vals in vals_list if vals.get("line_id")])
        if any(parent.settlement_id.state != "draft" for parent in parents):
            raise UserError(_("No agregue calibres a una liquidación validada."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(row.line_id.settlement_id.state != "draft" for row in self):
            raise UserError(_("No modifique calibres de una liquidación validada."))
        return super().write(vals)

    def unlink(self):
        if any(row.line_id.settlement_id.state != "draft" for row in self):
            raise UserError(_("No elimine calibres de una liquidación validada."))
        return super().unlink()


class SettlementAccountMove(models.Model):
    _inherit = "account.move"

    step_export_settlement_id = fields.Many2one("step.export.receiver.settlement", string="Liquidación recibidor")
