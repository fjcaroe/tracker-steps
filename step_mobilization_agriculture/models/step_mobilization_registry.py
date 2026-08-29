# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMoviRegistry(models.Model):
    """Extensión agrícola: liga el viaje a un fundo y resuelve la
    distribución de costo (centro de costo/labor) vía tarja, sin que el
    núcleo de Movilización conozca step.fundo/step.tarja."""
    _inherit = 'step.movi.registry'

    fundo_id = fields.Many2one(
        'step.fundo', string="Fundo", ondelete='restrict', copy=False,
        help='ondelete restrict (no cascade): borrar un fundo con viajes de movilización '
             'asociados debe bloquearse, no arrastrar el historial operacional a la papelera.')

    def _get_cost_distribution_hook(self, employee):
        self.ensure_one()
        if not self.fundo_id or not self.date:
            return super()._get_cost_distribution_hook(employee)
        cache = getattr(self, '_mobilization_agri_cost_cache', None)
        if cache is None:
            cache = {}
            tarjas = self.env['step.tarja'].search([
                ('fundo_id', '=', self.fundo_id.id),
                ('date', '=', self.date),
                ('company_id', '=', self.company_id.id),
                ('tarja_type', '=', 'propio'),
            ])
            for tarja in tarjas:
                for line in tarja.tarja_line:
                    cache.setdefault(line.employee_id.id, {
                        'cost_id': line.cost_id.id,
                        'labor_id': line.labor_id.id,
                    })
            self._mobilization_agri_cost_cache = cache
        return cache.get(employee.id)


class StepMoviRegistryLine(models.Model):
    _inherit = 'step.movi.registry.line'

    fundo_id = fields.Many2one(related='movi_id.fundo_id', string="Fundo", store=True)
