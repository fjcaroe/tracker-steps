# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError


class StepCosechaProceso(models.Model):
    _name = 'step.cosecha.proceso'
    _inherit = ['mail.thread']
    _description = 'Proceso Postcosecha'
    _order = 'date desc, id desc'

    name = fields.Char(string='Nombre', index=True, required=True)
    registry_id = fields.Many2one(
        'step.cosecha.registry', string='Registro de cosecha', tracking=True,
        copy=False, domain="[('company_id', '=', company_id)]"
    )
    product_id = fields.Many2one(
        'product.template', string='Producto', related='registry_id.product_id',
        store=True, readonly=True
    )
    date = fields.Date(string='Fecha', default=fields.Date.context_today, tracking=True)
    super_id = fields.Many2one('hr.employee', 'Supervisor')
    cosecha_ubi_id = fields.Many2one('step.cosecha.ubicacion', 'Tipo Ubicación')
    responsable_id = fields.Many2one('res.users', 'Responsable')
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, index=True
    )
    proceso_line = fields.One2many(
        comodel_name='step.cosecha.proceso.line',
        inverse_name='proceso_id',
        string="Proceso Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('progress', 'En progreso'),
            ('done', 'Listo'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='draft',
        tracking=True,
    )
    control_count = fields.Integer(
        string='Controles', compute='_compute_process_totals', store=True
    )
    rejected_count = fields.Integer(
        string='Controles rechazados', compute='_compute_process_totals', store=True
    )
    duration_hours = fields.Float(
        string='Horas de proceso', compute='_compute_process_totals', store=True,
        digits=(12, 2)
    )

    @api.depends('proceso_line.calidad', 'proceso_line.duration_hours')
    def _compute_process_totals(self):
        for process in self:
            process.control_count = len(process.proceso_line)
            process.rejected_count = len(process.proceso_line.filtered(
                lambda line: line.calidad == 'rechaza'
            ))
            process.duration_hours = sum(process.proceso_line.mapped('duration_hours'))

    @api.onchange('registry_id')
    def _onchange_registry_id(self):
        for process in self:
            registry = process.registry_id
            if not registry:
                continue
            process.date = fields.Date.to_date(registry.date) if registry.date else False
            process.super_id = registry.super_id
            process.cosecha_ubi_id = registry.cosecha_ubi_id
            process.responsable_id = registry.responsable_id
            process.company_id = registry.company_id

    def action_draft(self):
        for movi in self:
            if movi.state != 'progress':
                raise UserError(_("Sólo un proceso en progreso puede volver a Nuevo."))
            movi.write({'state': 'draft'})

    def action_progress(self):
        for movi in self:
            if movi.state != 'draft':
                raise UserError(_("Sólo un proceso nuevo puede pasar a En progreso."))
            movi.write({'state': 'progress'})

    def action_done(self):
        for movi in self:
            if movi.state != 'progress':
                raise UserError(_("El proceso debe estar En progreso antes de marcarlo listo."))
            if not movi.proceso_line:
                raise UserError(_("Agregue al menos un control antes de finalizar el proceso."))
            movi.write({'state': 'done'})
