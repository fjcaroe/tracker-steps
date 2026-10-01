"""Usa los kilos reales por productor de cada tarja al repartir el FOB."""

from odoo import models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    def _step_liquidation_kg(self):
        self.ensure_one()
        if self.is_fruit_tag and self.step_tag_line_ids:
            return self.step_actual_kg
        return super()._step_liquidation_kg()

    def _step_producer_shares(self):
        self.ensure_one()
        if self.is_fruit_tag and self.step_tag_line_ids:
            total = self.step_actual_kg
            if total <= 0:
                return []
            by_producer = {}
            for line in self.step_tag_line_ids:
                by_producer[line.producer_id] = by_producer.get(line.producer_id, 0) + line.kilos
            return [(producer, kilos / total) for producer, kilos in by_producer.items()
                    if producer and kilos > 0]
        return super()._step_producer_shares()
