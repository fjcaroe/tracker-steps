# -*- coding: utf-8 -*-
"""Recolección de datos de las hojas automáticas del flujo de caja.

Vive aparte del encabezado para que cada motor (contabilidad, ventas, compras,
proformas) tenga un punto de extensión claro.
"""

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

from .cashflow import AUTOMATIC_SHEETS

_logger = logging.getLogger(__name__)


class StepCashflowCollect(models.Model):
    _inherit = "step.cashflow"

    def action_refresh(self):
        """Actualiza las hojas automáticas sin pisar los ajustes manuales."""
        for flow in self:
            if flow.state == "approved":
                raise UserError(_(
                    "El flujo %s está aprobado: reábralo para actualizar datos.")
                    % flow.display_name)
            flow._refresh_lines()
        return True

    def _refresh_lines(self):
        self.ensure_one()
        collected = {}
        for sheet in AUTOMATIC_SHEETS:
            for vals in getattr(self, "_collect_%s" % sheet)():
                key = (vals["source_model"], vals["source_id"], vals.get("source_line_id", 0))
                collected[key] = vals

        Line = self.env["step.cashflow.line"]
        existing = {}
        for line in self.line_ids:
            if line.is_manual:
                continue
            existing[(line.source_model, line.source_id, line.source_line_id)] = line

        created = updated = protected = retired = 0
        for key, vals in collected.items():
            line = existing.pop(key, None)
            if line is None:
                Line.create(dict(vals, cashflow_id=self.id))
                created += 1
                continue
            if line.adjust_reason:
                # Ajuste manual sobre una línea automática: no se pisa nunca.
                protected += 1
                continue
            changes = {}
            for field_name, value in vals.items():
                if field_name in ("source_model", "source_id", "source_line_id"):
                    continue
                current = line[field_name]
                if hasattr(current, "id"):
                    current = current.id or False
                if current != (value or False) and current != value:
                    changes[field_name] = value
            if changes:
                line.write(changes)
                updated += 1

        for line in existing.values():
            if line.adjust_reason or line.comment or line.excluded:
                line.write({
                    "excluded": True,
                    "comment": (line.comment or "") + _(" | El documento origen ya no aplica."),
                })
            else:
                line.unlink()
            retired += 1

        self.message_post(body=_(
            "Datos actualizados: %(created)s nuevas, %(updated)s actualizadas, "
            "%(protected)s con ajuste manual respetadas, %(retired)s retiradas.",
            created=created, updated=updated, protected=protected, retired=retired))
        return True

    # ------------------------------------------------------------------
    # Utilidades comunes
    # ------------------------------------------------------------------
    def _line_defaults(self, sheet):
        self.ensure_one()
        concept = self.env["step.treasury.concept"]._concept_for_sheet(sheet, self.company_id)
        return {"sheet": sheet, "concept_id": concept.id or False, "is_manual": False}

    def _document_type_of(self, move):
        """Tipo de documento LATAM cuando la localización lo aporta."""
        doc_type = move.l10n_latam_document_type_id if "l10n_latam_document_type_id" in move._fields else False
        if doc_type:
            return doc_type.id, doc_type.display_name
        labels = dict(move._fields["move_type"].selection)
        return False, labels.get(move.move_type, "")

    # ------------------------------------------------------------------
    # Hojas automáticas
    # ------------------------------------------------------------------
    def _collect_open_entries(self, sheet, account_type, move_types, sign):
        """Documentos abiertos leídos por apunte contable.

        Trabajar a nivel de apunte cubre de forma natural las cuotas (cada una
        tiene su propio vencimiento), los pagos parciales (residual real) y las
        notas de crédito (residual de signo contrario).
        """
        self.ensure_one()
        defaults = self._line_defaults(sheet)
        results = []
        entries = self.env["account.move.line"].search([
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"),
            ("account_id.account_type", "=", account_type),
            ("reconciled", "=", False),
            ("move_id.move_type", "in", move_types),
        ])
        for entry in entries:
            currency = entry.currency_id or self.company_id.currency_id
            residual = entry.amount_residual_currency if entry.currency_id else entry.amount_residual
            if float_is_zero(residual, precision_rounding=currency.rounding):
                continue
            move = entry.move_id
            doc_type_id, doc_name = self._document_type_of(move)
            results.append(dict(defaults, **{
                "source_model": "account.move",
                "source_id": move.id,
                "source_line_id": entry.id,
                "partner_id": move.partner_id.id,
                "partner_vat": move.partner_id.vat or "",
                "doc_type_id": doc_type_id,
                "doc_type_name": doc_name,
                "doc_number": move.name,
                "doc_date": move.invoice_date or move.date,
                "due_date": entry.date_maturity,
                "currency_id": currency.id,
                "amount_origin": residual * sign,
            }))
        return results

    def _collect_customer(self):
        return self._collect_open_entries(
            "customer", "asset_receivable",
            ("out_invoice", "out_refund", "out_receipt"), 1)

    def _collect_vendor(self):
        return self._collect_open_entries(
            "vendor", "liability_payable",
            ("in_invoice", "in_refund", "in_receipt"), -1)

    def _collect_orders(self, sheet, model, states, qty_field, doc_label):
        """Pedidos con importe aún no facturado.

        Se proyecta `precio_total x cantidad_a_facturar / cantidad_base`.
        `qty_to_invoice` es la fuente canónica de Odoo y ya incorpora la
        política del producto: pedido/entregado en ventas y pedido/recibido en
        compras. Así no se anticipa caja por bienes aún no entregados/recibidos
        cuando la política exige ese hito, ni se vuelve a contar lo facturado.
        """
        self.ensure_one()
        defaults = self._line_defaults(sheet)
        results = []
        orders = self.env[model].search([
            ("company_id", "=", self.company_id.id),
            ("state", "in", states),
        ])
        for order in orders:
            pending = 0.0
            for line in order.order_line:
                if getattr(line, "display_type", False):
                    continue
                quantity = line[qty_field]
                if not quantity:
                    continue
                to_invoice = line.qty_to_invoice
                if to_invoice <= 0:
                    continue
                pending += line.price_total * (to_invoice / quantity)
            currency = order.currency_id
            if float_is_zero(pending, precision_rounding=currency.rounding):
                continue
            results.append(dict(defaults, **{
                "source_model": model,
                "source_id": order.id,
                "source_line_id": 0,
                "partner_id": order.partner_id.id,
                "partner_vat": order.partner_id.vat or "",
                "doc_type_name": doc_label,
                "doc_number": order.name,
                "doc_date": fields.Date.to_date(order.date_order),
                "due_date": order._treasury_due_date(),
                "currency_id": currency.id,
                "amount_origin": pending,
            }))
        return results

    def _collect_sale_order(self):
        return self._collect_orders(
            "sale_order", "sale.order", ("sale",), "product_uom_qty", _("Nota de venta"))

    def _collect_purchase_order(self):
        return self._collect_orders(
            "purchase_order", "purchase.order", ("purchase",), "product_qty", _("Orden de compra"))

    def _collect_proforma(self):
        self.ensure_one()
        defaults = self._line_defaults("proforma")
        results = []
        proformas = self.env["step.vendor.proforma"]._treasury_pending_proformas(self.company_id)
        for proforma in proformas:
            if float_is_zero(proforma.amount_total, precision_rounding=proforma.currency_id.rounding):
                continue
            results.append(dict(defaults, **{
                "source_model": "step.vendor.proforma",
                "source_id": proforma.id,
                "source_line_id": 0,
                "partner_id": proforma.partner_id.id,
                "partner_vat": proforma.partner_id.vat or "",
                "doc_type_name": _("Proforma"),
                "doc_number": proforma.name,
                "doc_date": proforma.date,
                "due_date": proforma.date_due,
                "currency_id": proforma.currency_id.id,
                "amount_origin": proforma.amount_total,
            }))
        return results
