"""Read-only payment schedule projection; native contract and catalog relations."""
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.addons.step_producers.calendar import inclusive_end_domain


class PurchaseContract(models.Model):
    _inherit = 'step.producer.purchase.contract'

    season_id = fields.Many2one('step.temporada', string='Temporada', check_company=True,
        domain="['|',('company_ids','=',False),('company_ids','in',[company_id])]",
        help='Temporada del contrato. Los históricos quedan sin asignar hasta clasificarlos expresamente.')

    @api.model_create_multi
    def create(self, vals_list):
        vals_list=[dict(values) for values in vals_list]
        for values in vals_list:
            if values.get('parent_id') and 'season_id' not in values:
                values['season_id']=self.browse(values['parent_id']).season_id.id
        return super().create(vals_list)

    def write(self, values):
        if 'season_id' in values and any(c.state!='draft' and c.season_id and c.season_id.id!=values['season_id'] for c in self):
            raise UserError(_('Cree una revisión para cambiar la temporada de un contrato confirmado.'))
        return super().write(values)


class ContractReport(models.Model):
    _name = 'step.producer.contract.report'
    _description = 'Informe de calendario de pagos de contratos de productores'
    _auto = False
    _rec_name = 'contract_id'
    _order = 'date_due, id'

    contract_id = fields.Many2one('step.producer.purchase.contract', string='Folio contrato', readonly=True)
    product_line_id = fields.Many2one('step.producer.purchase.contract.product', string='Producto contratado', readonly=True)
    installment_id = fields.Many2one('step.producer.purchase.contract.installment', string='Cuota', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    producer_id = fields.Many2one('res.partner', string='Productor', readonly=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', readonly=True)
    species_id = fields.Many2one('step.especie', string='Especie', readonly=True)
    variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    product_id = fields.Many2one('product.product', string='Fruta de referencia', readonly=True)
    date_due = fields.Date(string='Vencimiento', readonly=True)
    date_stop = fields.Date(string='Fin vencimiento', readonly=True)
    calendar_end = fields.Date(string='Fin visual calendario', compute='_compute_calendar_end', search='_search_calendar_end')

    @api.depends('date_stop')
    def _compute_calendar_end(self):
        for row in self:
            row.calendar_end = fields.Date.subtract(row.date_stop, days=1) if row.date_stop else False

    @api.model
    def _search_calendar_end(self, operator, value):
        return inclusive_end_domain('date_stop', operator, value)

    quantity = fields.Float(string='Cantidad original', readonly=True, aggregator=False)
    uom_id = fields.Many2one('uom.uom', string='UdM original', readonly=True)
    quantity_kg = fields.Float(string='Cantidad kilos', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda contrato', readonly=True)
    amount = fields.Monetary(string='Neto a pago original', currency_field='currency_id', readonly=True, aggregator=False)
    usd_currency_id = fields.Many2one('res.currency', string='USD', readonly=True)
    amount_usd = fields.Monetary(string='Neto a pago USD', currency_field='usd_currency_id', readonly=True)
    valuation_status = fields.Selection([('valued','Convertida a USD'),('rate','Sin tipo de cambio')], string='Conversión USD', readonly=True)
    unconverted_qty = fields.Integer(string='Cuotas sin convertir a USD', readonly=True)
    unit_status = fields.Selection([('weight','Convertida a kilos'),('unit','UdM sin equivalencia a kilos')], string='Conversión kilos', readonly=True)
    unconverted_kg_qty = fields.Integer(string='Cuotas sin equivalencia a kilos', readonly=True)
    installment_state = fields.Selection([('created','Creado'),('approved','Aprobado'),('accounted','Contabilizado')], string='Estado cuota', readonly=True)
    contract_state = fields.Selection([('draft','Borrador'),('confirmed','Confirmado'),('closed','Cerrado')], string='Estado contrato', readonly=True)
    active = fields.Boolean(string='Cuota vigente', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr,self._table)
        self.env.cr.execute("""CREATE VIEW step_producer_contract_report AS
            SELECT i.id,i.id AS installment_id,i.contract_id,i.product_line_id,c.company_id,c.partner_id AS producer_id,
                c.season_id,p.species_id,p.variety_id,p.product_id,i.date_due,(i.date_due+1) AS date_stop,
                i.quantity,p.uom_id,
                CASE WHEN u.category_id=kg.category_id THEN i.quantity/u.factor*kg.factor END AS quantity_kg,
                c.currency_id,i.amount,usd.id AS usd_currency_id,
                CASE WHEN c.currency_id=usd.id THEN i.amount WHEN sr.rate IS NOT NULL AND ur.rate IS NOT NULL THEN i.amount*ur.rate/sr.rate END AS amount_usd,
                CASE WHEN c.currency_id=usd.id OR (sr.rate IS NOT NULL AND ur.rate IS NOT NULL) THEN 'valued' ELSE 'rate' END AS valuation_status,
                CASE WHEN c.currency_id=usd.id OR (sr.rate IS NOT NULL AND ur.rate IS NOT NULL) THEN 0 ELSE 1 END AS unconverted_qty,
                CASE WHEN u.category_id=kg.category_id THEN 'weight' ELSE 'unit' END AS unit_status,
                CASE WHEN u.category_id=kg.category_id THEN 0 ELSE 1 END AS unconverted_kg_qty,
                i.state AS installment_state,c.state AS contract_state,i.active
            FROM step_producer_purchase_contract_installment i
            JOIN step_producer_purchase_contract c ON c.id=i.contract_id
            JOIN step_producer_purchase_contract_product p ON p.id=i.product_line_id
            JOIN uom_uom u ON u.id=p.uom_id
            CROSS JOIN uom_uom kg CROSS JOIN res_currency usd
            LEFT JOIN LATERAL (SELECT rate FROM res_currency_rate WHERE currency_id=c.currency_id
                AND (company_id=c.company_id OR company_id IS NULL) AND name<=i.date_due ORDER BY company_id NULLS LAST,name DESC LIMIT 1) sr ON TRUE
            LEFT JOIN LATERAL (SELECT rate FROM res_currency_rate WHERE currency_id=usd.id
                AND (company_id=c.company_id OR company_id IS NULL) AND name<=i.date_due ORDER BY company_id NULLS LAST,name DESC LIMIT 1) ur ON TRUE
            WHERE usd.id=%s AND kg.id=%s
        """,(self.env.ref('base.USD').id,self.env.ref('uom.product_uom_kgm').id))
