from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StepDispatchDriver(models.Model):
    """Maestro de choferes de la versión 18.0.1.

    Desde 18.0.2 el chofer es un contacto con "¿Chofer?" marcado, como pide el
    diseño (nota 1 del formulario de registro). Se conserva para no perder el
    historial de las guías anteriores; la migración crea el contacto.
    """

    _name = "step.dispatch.driver"
    _description = "Chofer de despacho (anterior)"
    _order = "name"

    name = fields.Char(required=True)
    vat = fields.Char(string="RUT", required=True)
    phone = fields.Char(string="Teléfono")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ("vat_company_unique", "unique(vat, company_id)",
         "Ya existe un chofer con este RUT en la empresa."),
    ]


class StepDispatchGuide(models.Model):
    _name = "step.dispatch.guide"
    _description = "Guía de despacho"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Referencia", default=lambda self: _("Nueva"), readonly=True,
        copy=False, index=True,
    )
    dte_provider = fields.Selection(related="company_id.dispatch_dte_provider")
    external_folio = fields.Char(
        string="Número de guía", required=True, copy=False, tracking=True,
        help="Folio asignado por el proveedor DTE externo (modo Tercero). "
             "En ese modo la guía de Odoo es un documento interno no tributario.",
    )
    date = fields.Date(string="Fecha de guía", default=fields.Date.context_today,
                       required=True, tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("confirmed", "Confirmada"), ("cancelled", "Anulada")],
        default="draft", required=True, tracking=True, copy=False,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)

    # Cliente / destinatario
    partner_id = fields.Many2one("res.partner", string="Cliente / destinatario",
                                 required=True, tracking=True)
    partner_vat = fields.Char(related="partner_id.vat", string="RUT")
    partner_street = fields.Char(related="partner_id.street", string="Dirección")
    partner_city = fields.Char(related="partner_id.city", string="Comuna")
    partner_state_id = fields.Many2one(related="partner_id.state_id", string="Región")
    contact_id = fields.Many2one(
        "res.partner", string="Contacto",
        domain="[('parent_id', '=', partner_id)]",
    )
    receiver_activity = fields.Char(string="Giro receptor")
    reference = fields.Char(string="Referencia")
    payment_term_id = fields.Many2one("account.payment.term", string="Forma de pago")
    date_due = fields.Date(string="Vencimiento")

    # Configuración de despacho
    transfer_reason_id = fields.Many2one(
        "step.dispatch.transfer.reason", string="Razón del traslado", tracking=True,
    )
    transfer_reason = fields.Char(string="Detalle del motivo")
    dispatch_type_id = fields.Many2one("step.freight.dispatch.type", string="Tipo despacho", tracking=True)
    departure_datetime = fields.Datetime(string="Fecha hora salida")
    arrival_datetime = fields.Datetime(string="Fecha hora llegada")
    origin_address = fields.Char(string="Dirección de origen", required=True)
    destination_address = fields.Char(string="Dirección de destino", required=True)
    carrier_id = fields.Many2one(
        "res.partner", string="Transportista", required=True,
        domain="[('step_carga', '=', True)]",
    )
    carrier_vat = fields.Char(related="carrier_id.vat", string="RUT transportista")
    driver_partner_id = fields.Many2one(
        "res.partner", string="Chofer", tracking=True,
        domain="[('step_chofer', '=', True)]",
    )
    driver_vat = fields.Char(related="driver_partner_id.vat", string="RUT chofer")
    driver_id = fields.Many2one("step.dispatch.driver", string="Chofer (maestro anterior)")
    vehicle_id = fields.Many2one("fleet.vehicle", string="Camión")
    trailer_vehicle_id = fields.Many2one("fleet.vehicle", string="Remolque")
    truck_plate = fields.Char(string="Patente camión", required=True, compute="_compute_plates",
                              store=True, readonly=False, precompute=True)
    trailer_plate = fields.Char(string="Patente remolque", compute="_compute_plates",
                                store=True, readonly=False, precompute=True)

    # Flete
    freight_paid = fields.Boolean(string="Paga flete", tracking=True)
    freight_route_id = fields.Many2one("step.freight.route", string="Tramo")
    freight_route_from = fields.Char(related="freight_route_id.origin", string="Tramo desde")
    freight_route_to = fields.Char(related="freight_route_id.destination", string="Tramo hasta")
    freight_order_id = fields.Many2one("step.freight.order", string="OT flete", copy=False)

    picking_id = fields.Many2one("stock.picking", string="Operación de inventario", copy=False)
    line_ids = fields.One2many("step.dispatch.guide.line", "guide_id", string="Detalle", copy=True)

    total_bins = fields.Float(string="Total bins", compute="_compute_totals", store=True)
    total_kilos = fields.Float(string="Total kilos", compute="_compute_totals", store=True)
    amount_untaxed = fields.Monetary(string="Sub total", compute="_compute_totals", store=True)
    amount_exempt = fields.Monetary(string="Exento", compute="_compute_totals", store=True)
    amount_tax = fields.Monetary(string="IVA", compute="_compute_totals", store=True)
    amount_total = fields.Monetary(string="Total", compute="_compute_totals", store=True)
    tax_rate = fields.Float(string="Tasa impuesto", compute="_compute_totals", store=True)

    empty_bins_return = fields.Float(string="Bins vacíos devolución")
    globalgap_certified = fields.Boolean(string="Fruta certificada GLOBALG.A.P.")
    ggn = fields.Char(string="GGN")
    csg = fields.Char(string="CSG")
    note = fields.Html(string="Observación")

    # Facturación y libro de guías
    invoice_id = fields.Many2one("account.move", string="Factura", copy=False, readonly=True)
    invoice_status = fields.Selection(
        [("no", "No facturable"), ("to_invoice", "Por facturar"), ("invoiced", "Facturada")],
        string="Facturación", compute="_compute_invoice_status", store=True,
    )
    sii_operation_code = fields.Char(related="transfer_reason_id.code", store=True,
                                     string="Tipo de operación")
    annul_code = fields.Selection(
        [("1", "1. Folio anulado antes de enviarlo al SII"),
         ("2", "2. Anulada después de enviarla al SII"),
         ("3", "3. Recepción parcial")],
        string="Anulado / modificado", copy=False, tracking=True,
        help="Indicador del Libro de Guías. Se completa al anular; la recepción "
             "parcial se marca a mano.",
    )
    amount_modified = fields.Monetary(
        string="Monto total modificado", copy=False,
        help="Monto corregido cuando la recepción fue parcial (indicador 3).",
    )

    book_ref_type = fields.Char(string="Tipo doc. referencia", compute="_compute_book_reference")
    book_ref_folio = fields.Char(string="Folio doc. referencia", compute="_compute_book_reference")
    book_ref_date = fields.Date(string="Fecha doc. referencia", compute="_compute_book_reference")

    _sql_constraints = [
        ("external_folio_company_unique", "unique(external_folio, company_id)",
         "El número de guía ya está registrado para esta empresa."),
    ]

    def _compute_book_reference(self):
        for guide in self:
            ref = guide._book_invoice_reference()
            guide.book_ref_type = ref.get("type")
            guide.book_ref_folio = ref.get("folio")
            guide.book_ref_date = ref.get("date")

    @api.depends("vehicle_id", "trailer_vehicle_id")
    def _compute_plates(self):
        # Sin vehículo del maestro se conserva la patente escrita a mano.
        for guide in self:
            guide.truck_plate = guide.vehicle_id.license_plate or guide.truck_plate
            guide.trailer_plate = guide.trailer_vehicle_id.license_plate or guide.trailer_plate

    @api.depends("line_ids.bin_count", "line_ids.quantity_kg", "line_ids.quantity",
                 "line_ids.price_unit", "line_ids.tax_ids")
    def _compute_totals(self):
        for guide in self:
            untaxed = exempt = tax = rate = 0.0
            for line in guide.line_ids:
                taxes = line.tax_ids.filtered(lambda t: t.amount)
                if not taxes:
                    exempt += line.subtotal
                    continue
                res = taxes.compute_all(line.price_unit, guide.currency_id, line.quantity,
                                        product=line.product_id, partner=guide.partner_id)
                untaxed += res["total_excluded"]
                tax += res["total_included"] - res["total_excluded"]
                rate = rate or taxes[:1].amount
            guide.total_bins = sum(guide.line_ids.mapped("bin_count"))
            guide.total_kilos = sum(guide.line_ids.mapped("quantity_kg"))
            guide.amount_untaxed = untaxed
            guide.amount_exempt = exempt
            guide.amount_tax = tax
            guide.amount_total = untaxed + exempt + tax
            guide.tax_rate = rate

    @api.depends("state", "transfer_reason_id.invoiceable", "invoice_id.state")
    def _compute_invoice_status(self):
        for guide in self:
            if guide.invoice_id and guide.invoice_id.state != "cancel":
                guide.invoice_status = "invoiced"
            elif guide.state == "confirmed" and guide.transfer_reason_id.invoiceable:
                guide.invoice_status = "to_invoice"
            else:
                guide.invoice_status = "no"

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.payment_term_id = self.partner_id.property_payment_term_id
            if not self.destination_address:
                self.destination_address = self.partner_id.contact_address.replace("\n", ", ").strip(", ")

    @api.onchange("dispatch_type_id")
    def _onchange_dispatch_type_id(self):
        rule = self.dispatch_type_id.paga_flete
        if rule == "no":
            self.freight_paid = False
        elif rule == "si":
            self.freight_paid = True

    @api.constrains("freight_paid", "dispatch_type_id")
    def _check_freight_paid(self):
        for guide in self:
            if guide.freight_paid and guide.dispatch_type_id.paga_flete == "no":
                raise ValidationError(_("Este tipo de despacho no paga flete."))

    @api.constrains("departure_datetime", "arrival_datetime")
    def _check_datetimes(self):
        for guide in self:
            if (guide.departure_datetime and guide.arrival_datetime
                    and guide.arrival_datetime < guide.departure_datetime):
                raise ValidationError(_("La fecha hora de llegada no puede ser anterior a la salida."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nueva"):
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["name"] = self.env["ir.sequence"].with_company(company).next_by_code(
                    "step.dispatch.guide") or _("Nueva")
        return super().create(vals_list)

    def _check_ready_to_confirm(self):
        for guide in self:
            if guide.company_id.dispatch_dte_provider != "third_party":
                raise UserError(_(
                    "La emisión DTE tipo 52 con proveedor Odoo aún no está habilitada. "
                    "Use el modo Tercero con un folio emitido externamente."))
            if not guide.line_ids:
                raise UserError(_("Agregue al menos una línea antes de confirmar."))
            missing = []
            if not guide.transfer_reason_id:
                missing.append(_("Razón del traslado"))
            if not guide.driver_partner_id and not guide.driver_id:
                missing.append(_("Chofer"))
            if missing:
                raise UserError(_("Complete antes de confirmar: %s.", ", ".join(missing)))
            if guide.dispatch_type_id.paga_flete == "si" and not guide.freight_paid:
                raise UserError(_("Este tipo de despacho paga flete: marque Paga flete."))
            if guide.freight_paid and not guide.freight_order_id and not guide.freight_route_id:
                raise UserError(_("Indique el tramo del flete para generar la OT de flete."))

    def _prepare_freight_order_vals(self):
        self.ensure_one()
        return {
            "name": _("Flete guía %s", self.external_folio),
            "date": self.date,
            "freight_carrier_id": self.carrier_id.id,
            "route_id": self.freight_route_id.id,
            "vehicle_id": self.vehicle_id.id,
            "quantity": 1.0,
            "company_id": self.company_id.id,
            "notes": _("Generada desde la guía de despacho %s (%s).", self.external_folio, self.name),
        }

    def action_confirm(self):
        self._check_ready_to_confirm()
        for guide in self.filtered(lambda g: g.freight_paid and not g.freight_order_id):
            guide.freight_order_id = self.env["step.freight.order"].create(
                guide._prepare_freight_order_vals())
        self.write({"state": "confirmed"})
        return True

    def action_cancel(self):
        if self.filtered(lambda g: g.invoice_status == "invoiced"):
            raise UserError(_("No se puede anular una guía facturada. Anule primero la factura."))
        for guide in self:
            guide.write({
                "annul_code": guide.annul_code or ("2" if guide.state == "confirmed" else "1"),
                "state": "cancelled",
            })
        return True

    def action_draft(self):
        self.write({"state": "draft", "annul_code": False})
        return True

    # ------------------------------------------------------------------
    # Facturación de guías
    # ------------------------------------------------------------------
    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        vals = []
        for line in self.line_ids:
            line_vals = {
                "product_id": line.product_id.id,
                "name": _("%(desc)s (Guía N° %(folio)s)", desc=line.description, folio=self.external_folio),
                "quantity": line.quantity,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "tax_ids": [fields.Command.set(line.tax_ids.ids)],
            }
            if line.analytic_distribution:
                line_vals["analytic_distribution"] = line.analytic_distribution
            vals.append(fields.Command.create(line_vals))
        return vals

    def _add_chilean_references(self, invoice):
        """Referencia las guías en la factura si está la localización chilena."""
        if "l10n_cl_reference_ids" not in invoice._fields:
            return
        doc_type = self.env["l10n_latam.document.type"].search([
            ("code", "=", "52"), ("country_id.code", "=", "CL")], limit=1)
        if not doc_type:
            return
        Reference = invoice._fields["l10n_cl_reference_ids"].comodel_name
        Reference = self.env[Reference]
        vals = []
        for guide in self:
            ref_vals = {
                "move_id": invoice.id,
                "origin_doc_number": guide.external_folio,
                "l10n_cl_reference_doc_type_id": doc_type.id,
                "date": guide.date,
            }
            vals.append({k: v for k, v in ref_vals.items() if k in Reference._fields})
        Reference.create(vals)

    def action_create_invoice(self):
        guides = self.filtered(lambda g: g.invoice_status == "to_invoice")
        if not guides or guides != self:
            raise UserError(_(
                "Solo se facturan guías confirmadas, con razón de traslado facturable "
                "y que aún no tengan factura."))
        partners = guides.mapped("partner_id.commercial_partner_id")
        if len(partners) > 1 or len(guides.company_id) > 1:
            raise UserError(_("Las guías seleccionadas deben ser del mismo cliente y de la misma empresa."))
        first = guides[0]
        line_vals = []
        for guide in guides.sorted("date"):
            line_vals += guide._prepare_invoice_line_vals()
        invoice = self.env["account.move"].with_company(first.company_id).create({
            "move_type": "out_invoice",
            "partner_id": first.partner_id.id,
            "company_id": first.company_id.id,
            "invoice_payment_term_id": first.payment_term_id.id,
            "invoice_origin": ", ".join(guides.mapped("external_folio")),
            "invoice_line_ids": line_vals,
        })
        guides.write({"invoice_id": invoice.id})
        guides._add_chilean_references(invoice)
        return {
            "type": "ir.actions.act_window", "name": _("Factura de guías"),
            "res_model": "account.move", "res_id": invoice.id, "view_mode": "form",
            "target": "current",
        }

    def action_view_invoice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "account.move",
            "res_id": self.invoice_id.id, "view_mode": "form",
        }

    def action_view_freight_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "step.freight.order",
            "res_id": self.freight_order_id.id, "view_mode": "form",
        }

    # ------------------------------------------------------------------
    # Libro de guías (formato SII)
    # ------------------------------------------------------------------
    def _book_invoice_reference(self):
        self.ensure_one()
        invoice = self.invoice_id
        if not invoice or invoice.state == "cancel":
            return {}
        doc_type = getattr(invoice, "l10n_latam_document_type_id", False)
        number = getattr(invoice, "l10n_latam_document_number", False)
        return {
            "type": doc_type.code if doc_type else "33",
            "folio": number or invoice.name,
            "date": invoice.invoice_date,
        }

    def get_book_data(self):
        """Libro de Guías de Despacho (instructivo SII LGD): detalle y resumen del período."""
        def amount(value):
            return f"{value:,.0f}".replace(",", ".")

        guides = self.sorted(lambda g: (g.date, g.external_folio))
        lines = [{
            "folio": g.external_folio,
            "annul": g.annul_code or "",
            "operation": g.sii_operation_code or "",
            "date": g.date.isoformat(),
            "vat": g.partner_vat or "",
            "partner": (g.partner_id.name or "")[:50],
            "net": amount(g.amount_untaxed + g.amount_exempt),
            "rate": f"{g.tax_rate:.2f}" if g.tax_rate else "",
            "tax": amount(g.amount_tax),
            "total": amount(g.amount_total),
            "modified": amount(g.amount_modified) if g.annul_code == "3" else "",
            "ref_type": g.book_ref_type or "",
            "ref_folio": g.book_ref_folio or "",
            "ref_date": g.book_ref_date.isoformat() if g.book_ref_date else "",
        } for g in guides]
        valid = guides.filtered(lambda g: g.annul_code not in ("1", "2"))
        sales = valid.filtered(lambda g: g.sii_operation_code == "1")
        non_sales = []
        for code in sorted(set(valid.mapped("sii_operation_code")) - {"1", False}):
            group = valid.filtered(lambda g: g.sii_operation_code == code)
            non_sales.append({
                "code": code, "reason": group[:1].transfer_reason_id.name,
                "count": len(group), "amount": amount(sum(group.mapped("amount_total"))),
            })
        company = guides[:1].company_id or self.env.company
        return {
            "company": company.name,
            "vat": company.vat or "",
            "period_from": guides[:1].date.isoformat() if guides else "",
            "period_to": guides[-1:].date.isoformat() if guides else "",
            "lines": lines,
            "annulled_folios": len(guides.filtered(lambda g: g.annul_code == "1")),
            "annulled_guides": len(guides.filtered(lambda g: g.annul_code == "2")),
            "sales_count": len(sales),
            "sales_amount": amount(sum(sales.mapped("amount_total"))),
            "modified_amount": amount(sum(guides.filtered(lambda g: g.annul_code == "3").mapped("amount_modified"))),
            "non_sales": non_sales,
        }


class StepDispatchGuideLine(models.Model):
    _name = "step.dispatch.guide.line"
    _description = "Línea de guía de despacho"
    _inherit = ["analytic.mixin"]
    _order = "sequence, id"

    guide_id = fields.Many2one(
        "step.dispatch.guide", required=True, ondelete="cascade", index=True,
    )
    company_id = fields.Many2one(related="guide_id.company_id", store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    description = fields.Char(string="Descripción", required=True)
    packaging_id = fields.Many2one(
        "product.packaging", string="Empaque",
        domain="[('product_id', '=', product_id)]",
    )
    bin_count = fields.Float(string="Cant. empaque",
                             help="Cantidad de empaques (bins, cajas). Suma el total de bins de la guía.")
    product_uom_id = fields.Many2one("uom.uom", string="UdM", required=True)
    quantity = fields.Float(string="Cantidad UdM", required=True, default=1.0)
    quantity_kg = fields.Float(string="Kilos")
    price_unit = fields.Monetary(string="Precio neto")
    tax_ids = fields.Many2many(
        "account.tax", string="Impuestos",
        domain="[('type_tax_use', '=', 'sale'), ('company_id', 'parent_of', company_id)]",
        help="Sin impuesto, la línea suma en Exento.",
    )
    lot_id = fields.Many2one(
        "stock.lot", string="Lote / serie",
        domain="[('product_id', '=', product_id)]",
    )
    subtotal = fields.Monetary(string="Subtotal", compute="_compute_subtotal", store=True)
    currency_id = fields.Many2one(related="guide_id.currency_id", store=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id
            company = self.guide_id.company_id or self.env.company
            self.tax_ids = self.product_id.taxes_id.filtered(
                lambda t: t.company_id in company.parent_ids)
            if self.packaging_id.product_id != self.product_id:
                self.packaging_id = False

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.constrains("quantity", "bin_count", "quantity_kg")
    def _check_non_negative(self):
        for line in self:
            if line.quantity <= 0 or line.bin_count < 0 or line.quantity_kg < 0:
                raise ValidationError(_("Las cantidades deben ser positivas y los totales no negativos."))
