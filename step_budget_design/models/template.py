from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


def season_months(season):
    if not season.start_date or not season.end_date or season.end_date < season.start_date:
        raise ValidationError(_('Defina las fechas de inicio y término en la temporada.'))
    current=season.start_date.replace(day=1);end=season.end_date.replace(day=1);months=[]
    while current<=end:
        months.append(current);current+=relativedelta(months=1)
    if len(months)>12:
        raise ValidationError(_('El presupuesto anual admite hasta doce meses; revise el período de la temporada.'))
    return months


def monthly_usd(env, company, currency, period, amount):
    usd=env.ref('base.USD')
    if currency==usd:return amount,1.0,True
    rate=env['step.management.exchange.rate'].search([('company_id','=',company.id),('currency_id','=',usd.id),('year','=',period.year),('month','=',str(period.month).zfill(2))],limit=1)
    if currency!=company.currency_id:return 0,0,False
    value=rate.company_value_per_unit
    return (amount/value,value,True) if value>0 else (0,0,False)


class Origin(models.Model):
    _name='step.management.budget.origin'
    _description='Origen de gasto o ingreso presupuestario'
    code=fields.Char(string='Código',required=True)
    name=fields.Char(string='Nombre',required=True)
    category=fields.Selection([('labor','Mano de obra'),('input','Insumos'),('machinery','Maquinarias'),('service','Gastos y servicios'),('other','Ingresos')],required=True)
    flow_type=fields.Selection([('cost','Costo'),('income','Ingreso')],required=True)
    _sql_constraints=[('origin_code_unique','unique(code)','El código ya existe.')]


class Version(models.Model):
    _name='step.management.budget.version'
    _description='Versión de presupuesto'
    _check_company_auto=True
    code=fields.Char(string='Código',required=True)
    name=fields.Char(string='Nombre',required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    deadline=fields.Date(string='Fecha límite')
    active=fields.Boolean(default=True)
    _sql_constraints=[('version_code_company_unique','unique(company_id,code)','La versión ya existe en esta empresa.')]


class CalculationUom(models.Model):
    _name='step.management.budget.calculation.uom'
    _description='Unidad de cálculo de presupuesto'
    code=fields.Char(string='Código',required=True)
    name=fields.Char(string='Nombre',required=True)
    basis=fields.Selection([('hectares','Hectáreas'),('plants','Plantas'),('days','Jornadas'),('units','Unidad'),('kg','Kilo')],required=True)
    product_uom_id=fields.Many2one('uom.uom',string='UdM producto sugerida')
    _sql_constraints=[('calculation_code_unique','unique(code)','El código ya existe.')]


class BudgetGroup(models.Model):
    _inherit='step.management.budget.group'
    origin_id=fields.Many2one('step.management.budget.origin',string='Origen presupuesto')
    phenology_id=fields.Many2one('x_estado_fenologico',string='Estado fenológico BPA')


class Template(models.Model):
    _inherit='step.management.budget.template'
    line_ids=fields.One2many(copy=True)
    season_id=fields.Many2one('step.temporada',string='Temporada',check_company=True)
    budget_version_id=fields.Many2one('step.management.budget.version',string='Versión presupuesto',check_company=True)
    species_id=fields.Many2one('step.especie',string='Especie',check_company=True)
    variety_id=fields.Many2one('step.variedad',string='Variedad')
    base_plants=fields.Float(string='Plantas base',digits=(16,4))
    base_kg=fields.Float(string='Kilos totales base',digits=(16,4))
    fruit_share_ids=fields.One2many('step.management.budget.fruit.share','template_id',string='Distribución de fruta',copy=True)
    period_ids=fields.One2many('step.management.budget.template.month','template_id',string='Distribución mensual')

    def _check_editable(self):
        if any(r.season_id and r.state!='draft' for r in self):raise UserError(_('Duplique la plantilla aprobada para editar otra.'))

    def write(self,vals):
        if vals.get('state')=='active':self.filtered('season_id')._validate_design()
        if vals.get('state')=='draft' and any(r.season_id and r.state!='draft' for r in self):raise UserError(_('Duplique la plantilla para conservar la aprobada.'))
        if set(vals).intersection({'name','season_id','budget_version_id','species_id','variety_id','base_plants','base_kg','base_hectares','expected_yield_kg_ha','fruit_share_ids','line_ids','period_ids','company_id','currency_id'}):self._check_editable()
        return super().write(vals)

    def action_set_draft(self):
        if any(r.season_id for r in self):raise UserError(_('Duplique la plantilla para conservar la aprobada.'))
        return super().action_set_draft()

    def action_duplicate_template(self):
        self.ensure_one();record=self.copy({'name':self.name+' (copia)','state':'draft','active':True})
        return {'type':'ir.actions.act_window','res_model':self._name,'res_id':record.id,'view_mode':'form'}

    def action_create_periods(self):
        self._check_editable()
        for record in self:
            periods=season_months(record.season_id)
            for line in record.line_ids:
                present=set(line.month_ids.mapped('period_date'))
                self.env['step.management.budget.template.month'].create([{'line_id':line.id,'period_date':p} for p in periods if p not in present])
        return True

    def _validate_design(self):
        for record in self:
            periods=set(season_months(record.season_id))
            if not record.line_ids:raise ValidationError(_('Ingrese las labores de la plantilla.'))
            if record.fruit_share_ids and float_compare(sum(record.fruit_share_ids.mapped('percentage')),100,precision_digits=4):raise ValidationError(_('Los porcentajes de fruta deben sumar 100 %.'))
            for line in record.line_ids:
                if not line.calculation_uom_id or not line.product_id or not line.uom_id or not line.origin_id or not line.activity_id:raise ValidationError(_('Complete origen, actividad, producto-labor y unidades de cálculo y producto.'))
                if line.origin_id.flow_type!=line.group_id.flow_type:raise ValidationError(_('El origen y el grupo deben tener la misma naturaleza: costo o ingreso.'))
                if line.calculation_uom_id.basis in ('plants','kg') and line.yield_quantity<=0:raise ValidationError(_('El rendimiento debe ser mayor que cero para plantas o kilos.'))
                if set(line.month_ids.mapped('period_date'))-periods:raise ValidationError(_('La distribución contiene meses fuera de la temporada.'))
                if float_compare(sum(line.month_ids.mapped('quantity')),line.calculation_quantity,precision_digits=4):raise ValidationError(_('Distribuya el 100 %% de la cantidad de %(line)s.',line=line.indicator))
        return True

    def action_activate(self):
        self.filtered('season_id')._validate_design()
        return super().action_activate()


class FruitShare(models.Model):
    _name='step.management.budget.fruit.share'
    _description='Distribución de kilos presupuestados por categoría de fruta'
    template_id=fields.Many2one('step.management.budget.template',required=True,ondelete='cascade')
    company_id=fields.Many2one(related='template_id.company_id',store=True)
    category_id=fields.Many2one('step.management.fruit.category',string='Categoría de fruta',required=True,check_company=True)
    percentage=fields.Float(string='Porcentaje',required=True)
    kg=fields.Float(string='Kilos',compute='_compute_kg')
    _sql_constraints=[('share_category_unique','unique(template_id,category_id)','La categoría ya tiene un porcentaje.'),('share_percent_range','check(percentage>=0 AND percentage<=100)','El porcentaje debe estar entre 0 y 100.')]

    @api.depends('percentage','template_id.base_kg','template_id.expected_yield_kg_ha','template_id.base_hectares')
    def _compute_kg(self):
        for row in self:row.kg=(row.template_id.base_kg or row.template_id.base_hectares*row.template_id.expected_yield_kg_ha)*row.percentage/100

    @api.model_create_multi
    def create(self,vals):
        self.env['step.management.budget.template'].browse([v['template_id'] for v in vals if v.get('template_id')])._check_editable()
        return super().create(vals)

    def write(self,vals):
        self.template_id._check_editable();return super().write(vals)

    def unlink(self):
        self.template_id._check_editable();return super().unlink()


class TemplateLine(models.Model):
    _inherit='step.management.budget.template.line'
    origin_id=fields.Many2one('step.management.budget.origin',string='Origen presupuesto')
    activity_id=fields.Many2one('account.analytic.account',string='Actividad',check_company=True)
    calculation_uom_id=fields.Many2one('step.management.budget.calculation.uom',string='UdM cálculo')
    yield_quantity=fields.Float(string='Rendimiento UdM',default=1,digits=(16,6))
    fruit_category_id=fields.Many2one('step.management.fruit.category',string='Categoría de fruta',check_company=True)
    month_ids=fields.One2many('step.management.budget.template.month','line_id',string='Distribución cantidades',copy=True)
    calculation_quantity=fields.Float(string='Cantidad UdM producto',compute='_compute_calculation',store=True,digits=(16,4))
    calculation_amount=fields.Monetary(string='Valor temporada',compute='_compute_calculation',store=True,currency_field='currency_id')
    calculation_unit_price=fields.Float(string='Unitario UdM',compute='_compute_calculation',store=True,digits=(16,8))

    @api.depends('calculation_uom_id.basis','yield_quantity','base_quantity','unit_price','fruit_category_id',
        'template_id.base_hectares','template_id.base_plants','template_id.base_kg','template_id.expected_yield_kg_ha',
        'template_id.fruit_share_ids.percentage','template_id.fruit_share_ids.category_id','group_id.flow_type')
    def _compute_calculation(self):
        for row in self:
            basis=row.calculation_uom_id.basis;template=row.template_id
            quantity=row.base_quantity;amount=quantity*row.unit_price
            if basis=='hectares':quantity=template.base_hectares*row.yield_quantity;amount=quantity*row.unit_price
            elif basis in ('plants','kg'):
                base=template.base_plants if basis=='plants' else (template.base_kg or template.base_hectares*template.expected_yield_kg_ha)
                if basis=='kg' and row.fruit_category_id:
                    share=template.fruit_share_ids.filtered(lambda r:r.category_id==row.fruit_category_id)
                    base=sum(share.mapped('kg'))
                quantity=base if row.flow_type=='income' else base/row.yield_quantity if row.yield_quantity>0 else 0
                amount=base*row.unit_price
            row.calculation_quantity=quantity;row.calculation_amount=amount
            row.calculation_unit_price=amount/quantity if quantity else 0

    @api.depends('base_quantity','unit_price','template_id.base_hectares','template_id.season_id','calculation_quantity','calculation_amount',
                 'may','jun','jul','aug','sep','oct','nov','dec','jan','feb','mar','apr')
    def _compute_amounts(self):
        super()._compute_amounts()
        for row in self.filtered(lambda r:r.template_id.season_id and r.calculation_uom_id):
            row.quantity_per_ha=row.calculation_quantity/row.template_id.base_hectares
            row.cost_per_ha=row.calculation_amount/row.template_id.base_hectares

    @api.onchange('product_id')
    def _onchange_design_product(self):
        for row in self:
            if row.product_id:
                group=row.product_id.product_tmpl_id._get_management_budget_group(row.company_id)
                if group:row.group_id=group
                row.uom_id=row.product_id.uom_id
                if row.product_id.actividad_id:row.activity_id=row.product_id.actividad_id

    @api.model_create_multi
    def create(self,vals):
        self.env['step.management.budget.template'].browse([v['template_id'] for v in vals if v.get('template_id')])._check_editable()
        return super().create(vals)

    def write(self,vals):
        self.template_id._check_editable();return super().write(vals)

    def unlink(self):
        self.template_id._check_editable();return super().unlink()


class TemplateMonth(models.Model):
    _name='step.management.budget.template.month'
    _description='Mes de distribución de plantilla presupuestaria'
    _order='period_date,line_id'
    line_id=fields.Many2one('step.management.budget.template.line',string='Labor',required=True,ondelete='cascade')
    template_id=fields.Many2one(related='line_id.template_id',store=True)
    company_id=fields.Many2one(related='template_id.company_id',store=True)
    period_date=fields.Date(string='Año-mes',required=True)
    quantity=fields.Float(string='Cantidad',digits=(16,4))
    unit_price=fields.Float(related='line_id.calculation_unit_price',string='Unitario UdM')
    currency_id=fields.Many2one(related='line_id.currency_id')
    amount=fields.Monetary(string='Valor presupuesto',compute='_compute_value',currency_field='currency_id')
    usd_currency_id=fields.Many2one('res.currency',default=lambda self:self.env.ref('base.USD'))
    amount_usd=fields.Monetary(string='Valor USD',compute='_compute_value',currency_field='usd_currency_id')
    exchange_rate=fields.Float(string='Dólar estimado',compute='_compute_value')
    rate_available=fields.Boolean(compute='_compute_value')
    _sql_constraints=[('template_period_unique','unique(line_id,period_date)','El mes ya existe para esta labor.'),('template_qty_positive','check(quantity>=0)','La cantidad no puede ser negativa.')]

    @api.depends('quantity','unit_price','period_date','currency_id','company_id')
    def _compute_value(self):
        for row in self:
            row.amount=row.quantity*row.unit_price
            row.amount_usd,row.exchange_rate,row.rate_available=monthly_usd(self.env,row.company_id,row.currency_id,row.period_date,row.amount) if row.period_date else (0,0,False)

    @api.constrains('period_date','line_id')
    def _check_period(self):
        for row in self:
            if row.period_date not in season_months(row.template_id.season_id):raise ValidationError(_('Seleccione el primer día de un mes de la temporada.'))

    @api.model_create_multi
    def create(self,vals):
        self.env['step.management.budget.template.line'].browse([v['line_id'] for v in vals if v.get('line_id')]).template_id._check_editable()
        return super().create(vals)

    def write(self,vals):
        self.template_id._check_editable();return super().write(vals)

    def unlink(self):
        self.template_id._check_editable();return super().unlink()
