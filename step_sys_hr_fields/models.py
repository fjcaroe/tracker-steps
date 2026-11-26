from odoo import fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    x_studio_categora_empleado = fields.Many2one('hr.employee.category', string='Categoría Empleado',
                                                 ondelete='set null', index=False)
    x_studio_tipo_contrato = fields.Many2one('hr.contract.type', string='Tipo Contrato',
                                             ondelete='set null', index=False)


class Contract(models.Model):
    _inherit = 'hr.contract'

    x_studio_cotizacin_obligatoria_adicional = fields.Float(string='Cotización obligatoria adicional')
