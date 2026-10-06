from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Task(models.Model):
    _inherit='project.task'
    # Generic support/project tasks have no crop. Preserve the native columns
    # and require classification only for a center explicitly tied to a crop.
    grupo_variedad_id=fields.Many2one(required=False)
    variedad_id=fields.Many2one(required=False)
    step_agricultural_task=fields.Boolean(compute='_compute_agricultural_task')

    @api.depends('cost_id.especie_id')
    def _compute_agricultural_task(self):
        for task in self:task.step_agricultural_task=bool(task.cost_id.especie_id)

    @api.constrains('cost_id','grupo_variedad_id','variedad_id')
    def _check_agricultural_classification(self):
        for task in self:
            if task.step_agricultural_task and not (task.grupo_variedad_id and task.variedad_id):
                raise ValidationError(_('Las tareas con centro de costo agrícola requieren grupo de variedad y variedad.'))
            if task.variedad_id and task.grupo_variedad_id and task.variedad_id.grupo_variedad_id!=task.grupo_variedad_id:
                raise ValidationError(_('La variedad debe pertenecer al grupo seleccionado.'))
