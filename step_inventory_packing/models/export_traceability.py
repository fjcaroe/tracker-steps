"""Propaga hitos documentales de Exportaciones a las tarjas preparadas."""

from odoo import api, models


class ExportShipment(models.Model):
    _inherit = "step.export.export"

    @api.depends('name', 'shipment_number', 'dus_folio', 'bl_folio')
    @api.depends_context('step_document_reference')
    def _compute_display_name(self):
        super()._compute_display_name()
        reference = self.env.context.get('step_document_reference')
        if reference in ('dus_folio', 'bl_folio'):
            for shipment in self:
                shipment.display_name = '%s / %s' % (shipment[reference] or '', shipment.shipment_number or shipment.name)

    def _step_ready_tags(self):
        return self.mapped("tag_ids").filtered(
            lambda tag: tag.step_tag_kind == "E" and tag.step_tag_line_ids)

    def action_dispatch(self):
        result = super().action_dispatch()
        for shipment in self:
            guides = shipment.dispatch_guide_ids.mapped("external_folio")
            shipment._step_ready_tags().write({
                "step_tag_state": "dispatched",
                "step_shipment": shipment.shipment_number,
                "step_dispatch_guide": ", ".join(folio for folio in guides if folio),
                "step_guide_ids": [(6, 0, shipment.dispatch_guide_ids.ids)],
            })
        return result

    def action_ship(self):
        result = super().action_ship()
        for shipment in self:
            shipment._step_ready_tags().write({
                "step_dus": shipment.dus_folio,
                "step_bl_awb": shipment.bl_folio,
                "step_dus_shipment_ids": [(4, shipment.id)],
                "step_bl_shipment_ids": [(4, shipment.id)],
            })
        return result

    def action_invoice(self):
        result = super().action_invoice()
        for shipment in self:
            invoices = shipment.invoice_ids.filtered(lambda invoice: invoice.state == "posted")
            shipment._step_ready_tags().write({
                "step_invoice": ", ".join(invoices.mapped("name")),
                "step_invoice_ids": [(6, 0, invoices.ids)],
            })
        return result


class ReceiverSettlement(models.Model):
    _inherit = "step.export.receiver.settlement"

    def action_validate(self):
        result = super().action_validate()
        for settlement in self:
            tags = settlement.line_ids.mapped("shipment_id.tag_ids").filtered(
                lambda tag: tag.step_tag_kind == "E" and tag.step_tag_line_ids)
            tags.write({"step_tag_state": "liquidated"})
        return result
