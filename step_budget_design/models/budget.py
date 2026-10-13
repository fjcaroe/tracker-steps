from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_management_costs.models.operational_budget import PROTECTED_HEADER_FIELDS, REVISION_LINE_FIELDS, FROZEN_STATES
from odoo.addons.step_management_costs.models.budget_import import MONTH_KEY_BY_NUMBER
from .template import season_months

PROTECTED_HEADER_FIELDS.update({'season_id','budget_version_id'})
REVISION_LINE_FIELDS.update({'origin_id','activity_id','calculation_uom_id','expected_kg'})


class Budget(models.Model):
    _inherit='step.management.operational.budget'
    season_id=fields.Many2one('step.temporada',string='Temporada',check_company=True)
    budget_version_id=fields.Many2one('step.management.budget.version',string='Versión presupuesto',check_company=True)

    @api.onchange('template_id')
    def _onchange_design_template(self):
        for row in self:
            if row.template_id.season_id:
                row.season_id=row.template_id.season_id
                row.budget_version_id=row.template_id.budget_version_id

    def _season_date_range(self):
        self.ensure_one()
        return (self.season_id.start_date,self.season_id.end_date) if self.season_id else super()._season_date_range()

    def action_generate_lines(self):
        for record in self:
            if record.budget_type=='general':
                record.action_prepare_general()
                continue
            template=record.template_id
            if not template.season_id:
                super(Budget,record).action_generate_lines();continue
            record._ensure_transition(('draft','calculated'),_('calcular'))
            if record.import_id:raise UserError(_('Edite los registros de la carga Excel.'))
            template._validate_design()
            if record.season_id and record.season_id!=template.season_id:raise ValidationError(_('La plantilla y el presupuesto deben usar la misma temporada.'))
            if not record.allocation_ids or any(a.hectares<=0 for a in record.allocation_ids):raise ValidationError(_('Seleccione centros con hectáreas mayores que cero.'))
            commands=[]
            for allocation in record.allocation_ids:
                scale=allocation.hectares/template.base_hectares
                for line in template.line_ids:
                    commands.append(Command.create({'center_id':allocation.center_id.id,'template_line_id':line.id,
                        'category':line.origin_id.category,'origin_id':line.origin_id.id,'group_id':line.group_id.id,
                        'indicator':line.indicator,'activity_id':line.activity_id.id,'product_id':line.product_id.id,'uom_id':line.uom_id.id,
                        'calculation_uom_id':line.calculation_uom_id.id,'hectares':allocation.hectares,
                        'expected_kg':(template.base_kg or template.expected_yield_kg_ha*template.base_hectares)*scale,
                        'quantity_per_ha':line.quantity_per_ha,'quantity':line.calculation_quantity*scale,
                        'unit_price':line.calculation_unit_price,'calculation_mode':'quantity',
                        'month_ids':[Command.create({'month':MONTH_KEY_BY_NUMBER[m.period_date.month],'period_date':m.period_date,
                            'quantity':m.quantity*scale,'unit_price':line.calculation_unit_price}) for m in line.month_ids]}))
            record.line_ids.unlink()
            record.write({'season_id':template.season_id.id,'season':template.season_id.name,'budget_version_id':template.budget_version_id.id,
                'line_ids':commands,'state':'calculated','conversion_rate_type':'estimated'})
        return True

    def _revision_line_commands(self):
        commands=super()._revision_line_commands()
        for line,command in zip(self.line_ids,commands):
            for month,mcommand in zip(line.month_ids,command[2]['month_ids']):mcommand[2]['period_date']=month.period_date
        return commands

    def action_approve(self):
        for row in self.filtered('season_id'):
            periods=set(season_months(row.season_id))
            if any(not m.period_date or m.period_date not in periods for m in row.line_ids.month_ids):raise ValidationError(_('Complete el año-mes de todas las distribuciones de la temporada.'))
        return super().action_approve()


class BudgetLine(models.Model):
    _inherit='step.management.budget.line'
    origin_id=fields.Many2one('step.management.budget.origin',string='Origen presupuesto')
    activity_id=fields.Many2one('account.analytic.account',string='Actividad',check_company=True)
    calculation_uom_id=fields.Many2one('step.management.budget.calculation.uom',string='UdM cálculo')
    expected_kg=fields.Float(string='Kilos estimados del centro')

    def write(self,vals):
        if {'origin_id','activity_id','calculation_uom_id','expected_kg'}.intersection(vals) and any(r.budget_id.state in FROZEN_STATES for r in self):raise UserError(_('Cree una revisión para cambiar el detalle aprobado.'))
        return super().write(vals)


class BudgetMonth(models.Model):
    _inherit='step.management.budget.month'
    _order='period_date, id'
    period_date=fields.Date(string='Año-mes',index=True)

    @api.depends('month','budget_id.season','budget_id.date','period_date')
    def _compute_conversion_date(self):
        super()._compute_conversion_date()
        for row in self.filtered('period_date'):row.conversion_date=row.period_date

    @api.constrains('period_date','budget_id','month')
    def _check_design_period(self):
        for row in self.filtered('period_date'):
            if row.period_date.day!=1 or MONTH_KEY_BY_NUMBER[row.period_date.month]!=row.month:raise ValidationError(_('El mes debe coincidir con la fecha año-mes.'))
            if row.budget_id.season_id and row.period_date not in season_months(row.budget_id.season_id):raise ValidationError(_('El mes está fuera de la temporada.'))

    def write(self,vals):
        if 'period_date' in vals and any(r.budget_id.state in FROZEN_STATES for r in self):raise UserError(_('Cree una revisión para cambiar los meses aprobados.'))
        return super().write(vals)
