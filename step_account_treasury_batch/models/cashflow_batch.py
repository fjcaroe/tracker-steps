# -*- coding: utf-8 -*-
"""Puente entre el flujo de caja de Tesorería y los pagos por lotes.

El flujo ya proyecta qué se debe pagar y cuándo. Lo que faltaba era el paso
siguiente: convertir esa proyección en pagos reales agrupados en un lote. Aquí
viven la clasificación de las líneas pagables y la trazabilidad hacia el lote
generado; el proceso en sí lo conduce `step.cashflow.batch.wizard`.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

#: Cubetas que ofrece el proceso, en el orden en que se pagan. El requerimiento
#: funcional pide por omisión lo vencido más la semana 1 del horizonte.
BATCH_SCOPES = [
    ("overdue", "Sólo vencidos"),
    ("overdue_w1", "Vencidos y semana 1"),
    ("horizon", "Todo el horizonte"),
]

SCOPE_BUCKETS = {
    "overdue": ("overdue",),
    "overdue_w1": ("overdue", "w1"),
    "horizon": ("overdue", "w1", "w2", "w3", "w4", "w5"),
}


class StepCashflowLine(models.Model):
    _inherit = "step.cashflow.line"

    treasury_payment_id = fields.Many2one(
        "account.payment", string="Pago generado", readonly=True, copy=False, index=True,
        help="Pago creado desde el flujo para este documento.",
    )
    treasury_batch_id = fields.Many2one(
        "account.batch.payment", string="Lote de pago", readonly=True, copy=False, index=True,
        help="Lote en el que se envió este documento al banco.",
    )

    def action_open_batch_wizard(self):
        """Abre el proceso de lote con las líneas seleccionadas en la lista."""
        flows = self.mapped("cashflow_id")
        if len(flows) != 1:
            raise UserError(_("Seleccione líneas de un solo flujo de caja."))
        report = flows._batch_scope_lines(SCOPE_BUCKETS["horizon"])
        payable = self & report["payable"]
        if not payable:
            raise UserError(_(
                "Ninguna de las líneas seleccionadas se puede pagar en un lote: "
                "sólo se pagan egresos con una factura publicada y con saldo, que "
                "no estén ya incluidos en otro lote."))
        return flows._batch_wizard_action(
            scope="horizon", line_ids=payable.ids,
            skipped=len(self) - len(payable))


class StepCashflow(models.Model):
    _inherit = "step.cashflow"

    def _batch_scope_lines(self, buckets):
        """Clasifica las líneas de egreso del alcance dado.

        Devuelve cuatro conjuntos disjuntos. Sólo `payable` puede pagarse: un
        lote agrupa pagos y un pago necesita un asiento contable publicado con
        saldo. Las órdenes de compra, las proformas y las líneas manuales son
        proyecciones sin asiento, así que se informan aparte en vez de
        descartarse en silencio.
        """
        self.ensure_one()
        Line = self.env["step.cashflow.line"]
        already, no_document, with_document = [], [], []
        for line in self.line_ids:
            if line.flow_type != "outflow" or line.excluded or line.bucket not in buckets:
                continue
            if line.treasury_batch_id:
                already.append(line.id)
            elif line.source_model != "account.move" or not line.source_id:
                no_document.append(line.id)
            else:
                with_document.append(line.id)

        candidates = Line.browse(with_document)
        moves = self.env["account.move"].browse(
            sorted({line.source_id for line in candidates})).exists()
        open_move_ids = {
            move.id for move in moves
            if move.state == "posted"
            and move.payment_state not in ("paid", "reversed")
            and not float_is_zero(move.amount_residual,
                                  precision_rounding=move.currency_id.rounding)
        }
        payable, settled = [], []
        for line in candidates:
            (payable if line.source_id in open_move_ids else settled).append(line.id)
        return {
            "payable": Line.browse(payable),
            "settled": Line.browse(settled),
            "no_document": Line.browse(no_document),
            "already_batched": Line.browse(already),
        }

    def _batch_wizard_action(self, scope="overdue_w1", line_ids=None, skipped=0):
        self.ensure_one()
        context = dict(
            self.env.context,
            default_cashflow_id=self.id,
            default_bucket_scope=scope,
        )
        if line_ids is not None:
            context["default_line_ids"] = list(line_ids)
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear lote de pago"),
            "res_model": "step.cashflow.batch.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_open_batch_wizard(self):
        self.ensure_one()
        if self.state == "cancelled":
            raise UserError(_("Un flujo anulado no genera pagos."))
        return self._batch_wizard_action()
