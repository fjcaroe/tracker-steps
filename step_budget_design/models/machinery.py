from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .template import season_months, monthly_usd

_APPROVE=object()


class MachineryBudget(models.Model):
    _name='step.management.machinery.budget'
    _description='Presupuesto de maquinaria por temporada'
    _inherit=['mail.thread']
    _check_company_auto=True
    name=fields.Char(string='Nombre',required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    season_id=fields.Many2one('step.temporada',string='Temporada',required=True,check_company=True)
    budget_version_id=fields.Many2one('step.management.budget.version',string='Versión',required=True,check_company=True)
    vehicle_id=fields.Many2one('fleet.vehicle',string='Maquinaria',required=True,check_company=True)
    labor_id=fields.Many2one('step.labor',string='Labor maquinaria')
    currency_id=fields.Many2one(related='company_id.currency_id')
    state=fields.Selection([('draft','Ingresado'),('approved','Aprobado')],default='draft',required=True,readonly=True,copy=False)
    month_ids=fields.One2many('step.management.machinery.budget.month','budget_id',string='Horas mensuales',copy=True)
    component_ids=fields.One2many('step.management.machinery.budget.component','budget_id',string='Gastos de maquinaria',copy=True)
    total_hours=fields.Float(string='Horas temporada',compute='_compute_cost')
    total_cost=fields.Monetary(string='Costo temporada',compute='_compute_cost',currency_field='currency_id')
    hourly_rate=fields.Monetary(string='Costo hora máquina presupuestado',compute='_compute_cost',currency_field='currency_id')
    approved_rate=fields.Monetary(string='Tarifa aprobada',readonly=True,copy=False,currency_field='currency_id')

    @api.depends('month_ids.hours','component_ids.amount')
    def _compute_cost(self):
        for row in self:
            row.total_hours=sum(row.month_ids.mapped('hours'));row.total_cost=sum(row.component_ids.mapped('amount'))
            row.hourly_rate=row.total_cost/row.total_hours if row.total_hours else 0

    def _check_edit(self):
        if any(r.state!='draft' for r in self):raise UserError(_('Duplique el presupuesto aprobado para editar otro.'))

    @api.model_create_multi
    def create(self,vals):
        if any(v.get('state','draft')!='draft' or v.get('approved_rate') for v in vals):raise UserError(_('Use Aprobar.'))
        return super().create(vals)

    def write(self,vals):
        if self.env.context.get('_machinery_budget_approve') is not _APPROVE:
            if set(vals).intersection({'state','approved_rate'}):raise UserError(_('Use Aprobar.'))
            self._check_edit()
        return super().write(vals)

    def unlink(self):
        self._check_edit();return super().unlink()

    def action_approve(self):
        self.check_access('write')
        if not self.env.user.has_group('step_management_costs.group_management_approver'):raise UserError(_('La aprobación requiere Control de Gestión.'))
        for record in self:
            record._check_edit()
            periods=set(season_months(record.season_id))
            if record.total_hours<=0 or not record.component_ids or set(record.month_ids.mapped('period_date'))!=periods:raise ValidationError(_('Complete las horas de todos los meses y los gastos antes de aprobar.'))
            if any(c.period_date not in periods for c in record.component_ids):raise ValidationError(_('Los gastos deben estar dentro de la temporada.'))
            record.with_context(_machinery_budget_approve=_APPROVE).write({'approved_rate':record.hourly_rate,'state':'approved'})
        return True


class MachineryMonth(models.Model):
    _name='step.management.machinery.budget.month'
    _description='Horas máquina por mes presupuestado'
    _order='period_date'
    budget_id=fields.Many2one('step.management.machinery.budget',required=True,ondelete='cascade')
    company_id=fields.Many2one(related='budget_id.company_id',store=True)
    period_date=fields.Date(string='Año-mes',required=True)
    hours=fields.Float(string='Horas máquina')
    _sql_constraints=[('machinery_month_unique','unique(budget_id,period_date)','El mes ya existe.'),('machinery_hours_nonnegative','check(hours>=0)','Las horas no pueden ser negativas.')]

    @api.model_create_multi
    def create(self,vals):
        self.env['step.management.machinery.budget'].browse([v['budget_id'] for v in vals if v.get('budget_id')])._check_edit();return super().create(vals)

    def write(self,vals):
        if vals.get('budget_id'):self.env['step.management.machinery.budget'].browse(vals['budget_id'])._check_edit()
        self.budget_id._check_edit();return super().write(vals)

    def unlink(self):
        self.budget_id._check_edit();return super().unlink()

    @api.constrains('period_date','budget_id')
    def _check_period(self):
        for row in self:
            if row.period_date not in season_months(row.budget_id.season_id):raise ValidationError(_('Seleccione un mes de la temporada.'))


class MachineryComponent(models.Model):
    _name='step.management.machinery.budget.component'
    _description='Gasto mensual presupuestado de maquinaria'
    _order='period_date,service_type_id,id'
    budget_id=fields.Many2one('step.management.machinery.budget',required=True,ondelete='cascade')
    company_id=fields.Many2one(related='budget_id.company_id',store=True)
    period_date=fields.Date(string='Año-mes',required=True)
    service_type_id=fields.Many2one('type.service.machinery',string='Tipo servicio maquinaria',required=True)
    activity_id=fields.Many2one('account.analytic.account',string='Actividad',check_company=True)
    product_id=fields.Many2one('product.product',string='Producto-labor',check_company=True)
    uom_id=fields.Many2one('uom.uom',string='UdM producto')
    calculation_mode=fields.Selection([('hours','Por hora máquina'),('direct','Valor directo')],default='hours',required=True,string='Cálculo')
    consumption_per_hour=fields.Float(string='Rendimiento UdM / hora',digits=(16,6))
    unit_price=fields.Float(string='Tarifa',digits=(16,6))
    direct_amount=fields.Float(string='Valor mensual directo')
    quantity=fields.Float(string='Cantidad',compute='_compute_amount')
    currency_id=fields.Many2one(related='budget_id.currency_id')
    usd_currency_id=fields.Many2one('res.currency',default=lambda self:self.env.ref('base.USD'))
    amount=fields.Monetary(string='Valor mes',compute='_compute_amount',currency_field='currency_id')
    amount_usd=fields.Monetary(string='Valor USD',compute='_compute_amount',currency_field='usd_currency_id')
    rate_available=fields.Boolean(compute='_compute_amount')
    exchange_rate=fields.Float(compute='_compute_amount',string='Dólar estimado')

    @api.depends('calculation_mode','direct_amount','consumption_per_hour','unit_price','period_date','budget_id.month_ids.hours','budget_id.month_ids.period_date')
    def _compute_amount(self):
        for row in self:
            hours=sum(row.budget_id.month_ids.filtered(lambda m:m.period_date==row.period_date).mapped('hours'))
            row.quantity=hours*row.consumption_per_hour if row.calculation_mode=='hours' else 0
            row.amount=row.quantity*row.unit_price if row.calculation_mode=='hours' else row.direct_amount
            row.amount_usd,row.exchange_rate,row.rate_available=monthly_usd(self.env,row.company_id,row.currency_id,row.period_date,row.amount) if row.period_date else (0,0,False)

    @api.constrains('period_date','budget_id','consumption_per_hour','unit_price','direct_amount')
    def _check_values(self):
        for row in self:
            if row.period_date not in season_months(row.budget_id.season_id) or min(row.consumption_per_hour,row.unit_price,row.direct_amount)<0:raise ValidationError(_('Use un mes de la temporada y valores no negativos.'))

    @api.model_create_multi
    def create(self,vals):
        self.env['step.management.machinery.budget'].browse([v['budget_id'] for v in vals if v.get('budget_id')])._check_edit();return super().create(vals)

    def write(self,vals):
        if vals.get('budget_id'):self.env['step.management.machinery.budget'].browse(vals['budget_id'])._check_edit()
        self.budget_id._check_edit();return super().write(vals)

    def unlink(self):
        self.budget_id._check_edit();return super().unlink()


class TemplateMachinery(models.Model):
    _inherit='step.management.budget.template.line'
    machinery_budget_id=fields.Many2one('step.management.machinery.budget',string='Presupuesto maquinaria',check_company=True)

    def action_use_machinery_budget(self):
        self.template_id._check_editable()
        for row in self:
            source=row.machinery_budget_id
            if source.state!='approved' or source.season_id!=row.template_id.season_id or source.company_id!=row.company_id:raise ValidationError(_('Seleccione un presupuesto de maquinaria aprobado de la misma empresa y temporada.'))
            row.unit_price=source.approved_rate
        return True
