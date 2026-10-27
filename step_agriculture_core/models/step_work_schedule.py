# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepWorkSchedule(models.Model):
    _name = 'step.work.schedule'

    @api.depends('lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo')
    def _compute_total_hrs(self):
        total = 0
        for schedule in self:
            total += float(schedule.lunes)
            total += float(schedule.martes)
            total += float(schedule.miercoles)
            total += float(schedule.jueves)
            total += float(schedule.viernes)
            total += float(schedule.sabado)
            total += float(schedule.domingo)
            schedule.total = float(total)

    name = fields.Char(string='Nombre', index=True, required=True)
    lunes = fields.Float(string='Lunes')
    martes = fields.Float(string='Martes')
    miercoles = fields.Float(string='Miercoles')
    jueves = fields.Float(string='Jueves')
    viernes = fields.Float(string='Viernes')
    sabado = fields.Float(string='Sabado')
    domingo = fields.Float(string='Domingo')
    total = fields.Float(string='Hrs. Totales', compute='_compute_total_hrs', store=True)

    # @api.onchange('lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo')
    # def onchange_total_hrs(self):
    #     self.ensure_one()
    #     total = 0
    #     for record in self:
    #         total += float(record.lunes)
    #         total += float(record.martes)
    #         total += float(record.miercoles)
    #         total += float(record.jueves)
    #         total += float(record.viernes)
    #         total += float(record.sabado)
    #         total += float(record.domingo)
    #         record.total = float(total)
    # placeholder = "Codigo Multiple..."