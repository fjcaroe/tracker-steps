"""Consult the native fruit package and its existing shipment relations."""
from copy import deepcopy
from lxml import etree
from odoo import api, fields, models


class ExportFruitTagConsultation(models.Model):
    _inherit = "stock.quant.package"

    step_export_shipment_numbers = fields.Char(string="Números de embarque", compute="_compute_export_shipment_numbers")

    @api.depends("step_export_shipment_ids.shipment_number")
    def _compute_export_shipment_numbers(self):
        for tag in self:
            tag.step_export_shipment_numbers = ", ".join(tag.step_export_shipment_ids.mapped("shipment_number"))

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type in ("list", "search") and arch.get("class") == "o_export_fruit_tag_consultation":
            arch = deepcopy(arch)
            extra = ["step_tag_kind", "step_tag_state", "step_export_season_id", "step_producer_id",
                     "step_producer_code", "step_sdp_code", "step_filling", "step_composition",
                     "step_actual_kg", "step_actual_boxes", "step_packing_result",
                     "step_packing_production_id", "step_packaging_id", "step_packing_line_id",
                     "step_result_product_id", "step_reserved_ids", "step_producer_process_ids",
                     "harvest_date", "received_at", "step_shipment", "step_dispatch_guide",
                     "step_dus", "step_invoice", "step_bl_awb"]
            for name in extra:
                if name in self._fields:
                    attrs = {"name": name}
                    if view_type == "list":
                        attrs["optional"] = "show" if name in ("step_tag_kind", "step_tag_state", "step_filling", "step_result_product_id", "step_packaging_id") else "hide"
                    arch.append(etree.Element("field", **attrs))
        return arch, view
