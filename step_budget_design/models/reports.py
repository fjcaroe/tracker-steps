from odoo import fields,models,tools


class BudgetData(models.Model):
    _name='step.management.budget.data.report'
    _description='Data presupuesto por año-mes'
    _auto=False
    _order='period_date,budget_id,center_id,id'
    budget_id=fields.Many2one('step.management.operational.budget',string='Presupuesto',readonly=True)
    company_id=fields.Many2one('res.company',readonly=True)
    season_id=fields.Many2one('step.temporada',string='Temporada',readonly=True)
    budget_version_id=fields.Many2one('step.management.budget.version',string='Versión presupuesto',readonly=True)
    legacy_version=fields.Char(string='Versión histórica',readonly=True)
    state=fields.Selection([('draft','Ingresado'),('calculated','Calculado'),('approved','Aprobado'),('closed','Cerrado'),('superseded','Reemplazado'),('cancelled','Anulado')],string='Estado',readonly=True)
    period_date=fields.Date(string='Año-mes',readonly=True)
    center_id=fields.Many2one('account.analytic.account',string='Centro de costos',readonly=True)
    cost_type=fields.Char(string='Tipo CCosto',readonly=True)
    farm_id=fields.Many2one('step.fundo',string='Fundo',readonly=True)
    species_id=fields.Many2one('step.especie',string='Especie',readonly=True)
    variety_id=fields.Many2one('step.variedad',string='Variedad',readonly=True)
    origin_id=fields.Many2one('step.management.budget.origin',string='Origen',readonly=True)
    group_id=fields.Many2one('step.management.budget.group',string='Grupo presupuesto',readonly=True)
    activity_id=fields.Many2one('account.analytic.account',string='Actividad',readonly=True)
    product_id=fields.Many2one('product.product',string='Producto-labor',readonly=True)
    uom_id=fields.Many2one('uom.uom',string='UdM',readonly=True)
    quantity=fields.Float(string='Cantidad',readonly=True)
    currency_id=fields.Many2one('res.currency',readonly=True)
    amount=fields.Monetary(string='Valor Ppto',currency_field='currency_id',readonly=True)
    usd_currency_id=fields.Many2one('res.currency',readonly=True)
    amount_usd=fields.Monetary(string='Valor Ppto USD',currency_field='usd_currency_id',readonly=True)
    exchange_rate=fields.Float(string='TC Ppto',readonly=True,aggregator=False)
    rate_available=fields.Boolean(string='TC disponible',readonly=True)
    jornadas=fields.Float(string='Jornadas estimadas',readonly=True)
    flow_type=fields.Selection([('cost','Costo'),('income','Ingreso')],string='Naturaleza',readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr,self._table)
        self.env.cr.execute('''CREATE VIEW step_management_budget_data_report AS
          SELECT m.id,b.id budget_id,b.company_id,b.season_id,b.budget_version_id,b.budget_version legacy_version,b.state,m.period_date,
            l.center_id,COALESCE(c.type_costo,c.cost_type) cost_type,c.fundo_id farm_id,c.especie_id species_id,c.variedad_id variety_id,
            l.origin_id,l.group_id,l.activity_id,l.product_id,l.uom_id,m.quantity,m.currency_id,m.amount,
            usd.id usd_currency_id,CASE WHEN m.currency_id=usd.id THEN m.amount WHEN m.currency_id=co.currency_id AND r.company_value_per_unit>0 THEN m.amount/r.company_value_per_unit ELSE 0 END amount_usd,
            CASE WHEN m.currency_id=usd.id THEN 1 ELSE r.company_value_per_unit END exchange_rate,
            (m.currency_id=usd.id OR m.currency_id=co.currency_id AND r.company_value_per_unit>0) rate_available,
            CASE WHEN o.category='labor' AND (l.uom_id=cu.product_uom_id OR cu.basis='days') THEN m.quantity ELSE 0 END jornadas,
            g.flow_type
          FROM step_management_budget_month m JOIN step_management_budget_line l ON l.id=m.budget_line_id
          JOIN step_management_operational_budget b ON b.id=l.budget_id
          JOIN account_analytic_account c ON c.id=l.center_id JOIN res_company co ON co.id=b.company_id
          JOIN step_management_budget_group g ON g.id=l.group_id
          LEFT JOIN step_management_budget_origin o ON o.id=l.origin_id
          LEFT JOIN step_management_budget_calculation_uom cu ON cu.id=l.calculation_uom_id
          CROSS JOIN res_currency usd
          LEFT JOIN step_management_exchange_rate r ON r.company_id=b.company_id AND r.currency_id=usd.id
            AND r.active AND r.year=EXTRACT(YEAR FROM m.period_date) AND r.month=to_char(m.period_date,'MM')
          WHERE usd.id=%s
        ''',(self.env.ref('base.USD').id,))


class BudgetSummary(models.Model):
    _name='step.management.budget.summary.report'
    _description='Resumen presupuesto por centro de costos'
    _auto=False
    budget_id=fields.Many2one('step.management.operational.budget',string='Presupuesto',readonly=True)
    company_id=fields.Many2one('res.company',readonly=True)
    season_id=fields.Many2one('step.temporada',string='Temporada',readonly=True)
    center_id=fields.Many2one('account.analytic.account',string='Centro costos',readonly=True)
    currency_id=fields.Many2one('res.currency',readonly=True)
    hectares=fields.Float(string='Hectáreas',readonly=True)
    expected_kg=fields.Float(string='Kg estimados',readonly=True)
    income=fields.Monetary(string='Ingresos',currency_field='currency_id',readonly=True)
    cost=fields.Monetary(string='Costos',currency_field='currency_id',readonly=True)
    margin=fields.Monetary(string='Margen',currency_field='currency_id',readonly=True)
    income_per_kg=fields.Float(string='Ingreso / kg',readonly=True,aggregator=False)
    cost_per_kg=fields.Float(string='Costo / kg',readonly=True,aggregator=False)
    margin_per_kg=fields.Float(string='Margen / kg',readonly=True,aggregator=False)
    cost_per_ha=fields.Float(string='Costo / ha',readonly=True,aggregator=False)
    margin_percentage=fields.Float(string='% margen',readonly=True,aggregator=False)

    def init(self):
        tools.drop_view_if_exists(self.env.cr,self._table)
        self.env.cr.execute('''CREATE VIEW step_management_budget_summary_report AS
          SELECT r.*,income-cost margin,COALESCE(income/nullif(expected_kg,0),0) income_per_kg,
            COALESCE(cost/nullif(expected_kg,0),0) cost_per_kg,COALESCE((income-cost)/nullif(expected_kg,0),0) margin_per_kg,
            COALESCE(cost/nullif(hectares,0),0) cost_per_ha,COALESCE((income-cost)/nullif(income,0)*100,0) margin_percentage
          FROM (SELECT min(l.id) id,b.id budget_id,b.company_id,b.season_id,l.center_id,b.currency_id,
            max(COALESCE(a.hectares,l.hectares,0)) hectares,max(l.expected_kg) expected_kg,
            sum(CASE WHEN g.flow_type='income' THEN l.amount ELSE 0 END) income,
            sum(CASE WHEN g.flow_type='cost' THEN l.amount ELSE 0 END) cost
          FROM step_management_budget_line l JOIN step_management_operational_budget b ON b.id=l.budget_id
          JOIN step_management_budget_group g ON g.id=l.group_id
          LEFT JOIN step_management_budget_center a ON a.budget_id=b.id AND a.center_id=l.center_id
          GROUP BY b.id,b.company_id,b.season_id,l.center_id,b.currency_id) r
        ''')
