# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command
from odoo.exceptions import UserError


class StepCosechaRecepcion(models.Model):
    _name = 'step.cosecha.recepcion'
    _inherit = ['mail.thread']
    _description = 'Recepción Operativa de Cosecha'
    _order = 'date desc, id desc'
    _sql_constraints = [
        (
            'step_cosecha_reception_registry_unique',
            'unique(registry_id)',
            'Ya existe un control de recepción para este registro de cosecha.',
        ),
    ]

    name = fields.Char(string='Nombre', index=True, required=True)
    registry_id = fields.Many2one(
        'step.cosecha.registry', string='Registro de cosecha', tracking=True,
        copy=False,
        domain="[('type_tarea', '=', 'contratista'), ('company_id', '=', company_id)]"
    )
    picking_id = fields.Many2one(
        'stock.picking', string='Recepción de bodega',
        related='registry_id.reception_picking_id', store=True, readonly=True
    )
    picking_state = fields.Selection(
        related='picking_id.state', string='Estado de bodega', store=True, readonly=True
    )
    contact_id = fields.Many2one('res.partner', 'Contacto')
    phone = fields.Char(string='Teléfono')
    email = fields.Char(string='Correo electrónico')
    date = fields.Date(string='Fecha', default=fields.Date.context_today, tracking=True)
    dates = fields.Datetime(string='Fecha y hora', default=fields.Datetime.now)
    note = fields.Html(string="Notas")
    labor_id = fields.Many2one('product.template', 'Labor/Tarea', required=False)
    responsable_id = fields.Many2one('res.users', 'Responsable')
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company, index=True
    )
    recep_line = fields.One2many(
        comodel_name='step.cosecha.recepcion.line',
        inverse_name='recep_id',
        string="Recepcion Lines",
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
    line_count = fields.Integer(
        string='Líneas', compute='_compute_reception_totals', store=True
    )
    total_kilos = fields.Float(
        string='Total kilos', compute='_compute_reception_totals', store=True,
        digits='Product Unit of Measure'
    )
    total_boxes = fields.Float(
        string='Total cajas', compute='_compute_reception_totals', store=True
    )
    observed_count = fields.Integer(
        string='Observaciones de calidad', compute='_compute_reception_totals', store=True
    )

    @api.depends('recep_line.quantity', 'recep_line.boxes', 'recep_line.quality')
    def _compute_reception_totals(self):
        for reception in self:
            reception.line_count = len(reception.recep_line)
            reception.total_kilos = sum(reception.recep_line.mapped('quantity'))
            reception.total_boxes = sum(reception.recep_line.mapped('boxes'))
            reception.observed_count = len(reception.recep_line.filtered(
                lambda line: line.quality in ('observed', 'rejected')
            ))

    @api.onchange('contact_id')
    def _onchange_contact_id(self):
        for reception in self:
            if reception.contact_id:
                reception.phone = reception.contact_id.phone or reception.contact_id.mobile
                reception.email = reception.contact_id.email

    @api.onchange('registry_id')
    def _onchange_registry_id(self):
        for reception in self:
            registry = reception.registry_id
            if not registry:
                continue
            reception.name = registry.display_name
            reception.contact_id = registry.partner_id
            reception.phone = registry.partner_id.phone or registry.partner_id.mobile
            reception.email = registry.partner_id.email
            reception.date = fields.Date.to_date(registry.date) if registry.date else False
            reception.responsable_id = registry.responsable_id
            reception.company_id = registry.company_id
            if not reception.recep_line:
                reception.recep_line = [Command.create({
                    'product_id': registry.product_id.id,
                    'packaging_id': registry.packaging_ids.id,
                    'uom_id': registry.product_uom_id.id,
                    'quantity': registry.total_kilos,
                    'boxes': registry.total_boxes,
                    'tarja': registry.tarja,
                })]

    def action_draft(self):
        for movi in self:
            if movi.state != 'progress':
                raise UserError(_("Sólo una recepción en proceso puede volver a Nuevo."))
            movi.write({'state': 'draft'})

    def action_progress(self):
        for movi in self:
            if movi.state != 'draft':
                raise UserError(_("Sólo una recepción nueva puede pasar a En proceso."))
            movi.write({'state': 'progress'})

    def action_done(self):
        for movi in self:
            if movi.state != 'progress':
                raise UserError(_("La recepción debe estar En proceso antes de marcarla lista."))
            if not movi.recep_line:
                raise UserError(_("Agregue al menos una línea de producto a la recepción."))
            if movi.registry_id and not movi.picking_id:
                movi.registry_id.recibir_cosecha(reception_id=movi.id)
            movi.write({'state': 'done'})

    def action_generate_stock_receipt(self):
        self.ensure_one()
        if not self.registry_id:
            raise UserError(_("Seleccione un registro de cosecha contratista."))
        return self.registry_id.recibir_cosecha(reception_id=self.id)

    def action_open_picking(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError(_("Esta recepción todavía no tiene un movimiento de bodega."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Recepción de bodega'),
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
