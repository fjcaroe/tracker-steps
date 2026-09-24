# -*- coding: utf-8 -*-
"""Catálogos de Aserradero.

Todos son autocontenidos: no dependen de otros módulos Steps para que la
aplicación se pueda instalar sola en cualquier instancia.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepSawmillCatalog(models.AbstractModel):
    _name = 'step.sawmill.catalog'
    _description = 'Catálogo base de Aserradero'
    _order = 'sequence, name'

    name = fields.Char(string='Nombre', required=True, translate=True)
    sequence = fields.Integer(string='Secuencia', default=10)
    active = fields.Boolean(string='Activo', default=True)
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        help='Vacío = compartido por todas las empresas.')

    @api.constrains('name', 'company_id')
    def _check_unique_name(self):
        for rec in self:
            dup = self.with_context(active_test=False).search_count([
                ('id', '!=', rec.id),
                ('name', '=ilike', rec.name),
                ('company_id', '=', rec.company_id.id),
            ])
            if dup:
                raise ValidationError(_(
                    'Ya existe "%(name)s" en %(model)s para esta empresa.',
                    name=rec.name, model=rec._description))


class StepSawmillGrade(models.Model):
    _name = 'step.sawmill.grade'
    _inherit = 'step.sawmill.catalog'
    _description = 'Grado de madera'


class StepSawmillQuality(models.Model):
    _name = 'step.sawmill.quality'
    _inherit = 'step.sawmill.catalog'
    _description = 'Calidad de madera'

    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')


class StepSawmillProductType(models.Model):
    _name = 'step.sawmill.product.type'
    _inherit = 'step.sawmill.catalog'
    _description = 'Tipo de producto'

    description = fields.Char(string='Descripción')
    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')


class StepSawmillDestination(models.Model):
    _name = 'step.sawmill.destination'
    _inherit = 'step.sawmill.catalog'
    _description = 'Destino de producto'

    description = fields.Char(string='Descripción')
    scope = fields.Selection(
        [('internal', 'Interno'), ('external', 'Externo')],
        string='Grupo destino', default='internal', required=True)


class StepSawmillCostingDriver(models.Model):
    _name = 'step.sawmill.costing.driver'
    _inherit = 'step.sawmill.catalog'
    _description = 'Driver de costeo'


class StepSawmillShift(models.Model):
    _name = 'step.sawmill.shift'
    _inherit = 'step.sawmill.catalog'
    _description = 'Turno'

    hour_from = fields.Float(string='Desde (hora)')
    hour_to = fields.Float(string='Hasta (hora)')


class StepSawmillProcessType(models.Model):
    _name = 'step.sawmill.process.type'
    _inherit = 'step.sawmill.catalog'
    _description = 'Tipo de proceso'

    category = fields.Selection([
        ('production', 'Producción'),
        ('correction', 'Corrección'),
        ('reclassified', 'Desclasificado'),
        ('service', 'Servicio'),
    ], string='Categoría proceso')


class StepSawmillProcessLine(models.Model):
    _name = 'step.sawmill.process.line'
    _inherit = 'step.sawmill.catalog'
    _description = 'Línea / máquina de proceso'

    workcenter_id = fields.Many2one('mrp.workcenter', string='Centro de trabajo')
    staff_total = fields.Integer(string='Dotación total')
    capacity_inches = fields.Float(string='Capacidad pulgadas')
    capacity_m3 = fields.Float(string='Capacidad m³')


class StepSawmillWorkingDays(models.Model):
    _name = 'step.sawmill.working.days'
    _description = 'Días y horas hábiles por mes'
    _order = 'month desc, id'

    name = fields.Char(string='Descripción', required=True)
    month = fields.Date(string='Mes', required=True,
                        help='Primer día del mes al que aplica.')
    working_days = fields.Integer(string='Días hábiles')
    working_hours = fields.Integer(string='Horas hábiles')
    company_id = fields.Many2one('res.company', string='Empresa',
                                 default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    @api.constrains('working_days', 'working_hours')
    def _check_positive(self):
        for rec in self:
            if rec.working_days < 0 or rec.working_hours < 0:
                raise ValidationError(_('Los días y horas hábiles no pueden ser negativos.'))
