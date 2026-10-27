"""Live weekly projection over native estimates; no copied business records."""
from odoo import api, fields, models, tools
from odoo.addons.step_producers.calendar import inclusive_end_domain

class EstimateReport(models.Model):
    _name = 'step.producer.estimate.report'
    _description = 'Informe semanal de estimaciones de cosecha'
    _auto = False
    _rec_name = 'estimate_id'
    _order = 'week_start, id'

    estimate_id = fields.Many2one('step.export.estimate', string='Estimación', readonly=True)
    line_id = fields.Many2one('step.export.estimate.line', string='Fruta estimada', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', readonly=True)
    species_id = fields.Many2one('step.especie', string='Especie', readonly=True)
    variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    producer_id = fields.Many2one('res.partner', string='Productor', readonly=True)
    delivery_kind = fields.Selection([('process','Para proceso'),('packed','Embalada')], string='Delivery Kind', readonly=True)
    state = fields.Selection([('created','Creada'),('validated','Validada'),('current','Vigente'),('replaced','Reemplazada')], string='Estado', readonly=True)
    week_start = fields.Date(string='Semana', readonly=True)
    week_end = fields.Date(string='Fin de semana', readonly=True)
    calendar_end = fields.Date(string='Fin visual calendario', compute='_compute_calendar_end', search='_search_calendar_end')

    @api.depends('week_end')
    def _compute_calendar_end(self):
        for row in self:
            row.calendar_end = fields.Date.subtract(row.week_end, days=1) if row.week_end else False

    @api.model
    def _search_calendar_end(self, operator, value):
        return inclusive_end_domain('week_end', operator, value)

    export_kg = fields.Float(string='Kilos exportación', readonly=True)
    process_kg = fields.Float(string='Kilos a proceso', readonly=True)
    export_box_qty = fields.Float(string='Cajas exportación', readonly=True)
    export_pallet_qty = fields.Float(string='Pallets exportación', readonly=True)
    bin_qty = fields.Float(string='Bins', readonly=True)

    price_line_id = fields.Many2one('step.producer.preliq.price.line', string='Precio aplicado', readonly=True)
    usd_currency_id = fields.Many2one('res.currency', string='Moneda USD', readonly=True)
    price_usd_per_kg = fields.Float(string='Precio USD/kg', readonly=True, aggregator=False)
    amount_usd = fields.Monetary(string='Valor FOB estimado USD', currency_field='usd_currency_id', readonly=True)
    valuation_status = fields.Selection([('valued','Valorizada'),('missing','Sin precio'),('ambiguous','Precio ambiguo'),('unit','UdM incompatible'),('rate','Sin tipo de cambio')], string='Valorización', readonly=True)
    unvalued_week_qty = fields.Integer(string='Semanas sin valorizar', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE VIEW step_producer_estimate_report AS
            SELECT w.id,w.line_id,l.estimate_id,e.company_id,e.season_id,e.producer_id,
                l.species_id,l.variety_id,l.delivery_kind,e.state,w.week_start,
                (w.week_start+7) AS week_end,w.export_kg,
                CASE WHEN l.delivery_kind='process' THEN w.export_kg/nullif(l.export_percentage,0) ELSE 0 END AS process_kg,
                w.export_kg/nullif(l.kg_per_box,0) AS export_box_qty,
                w.export_kg/nullif(l.kg_per_box,0)/nullif(l.boxes_per_package,0) AS export_pallet_qty,
                CASE WHEN l.delivery_kind='process' THEN w.export_kg/nullif(l.export_percentage,0)/nullif(l.kg_per_box,0)/nullif(l.boxes_per_package,0) ELSE 0 END AS bin_qty,
                usd.id AS usd_currency_id, CASE WHEN p.matches=1 THEN p.id END AS price_line_id,
                CASE WHEN p.matches=1 AND pu.category_id=kg.category_id AND (p.currency_id=usd.id OR (sr.rate IS NOT NULL AND ur.rate IS NOT NULL))
                    THEN p.price*pu.factor/kg.factor*CASE WHEN p.currency_id=usd.id THEN 1 ELSE ur.rate/sr.rate END END AS price_usd_per_kg,
                CASE WHEN p.matches=1 AND pu.category_id=kg.category_id AND (p.currency_id=usd.id OR (sr.rate IS NOT NULL AND ur.rate IS NOT NULL))
                    THEN w.export_kg*p.price*pu.factor/kg.factor*CASE WHEN p.currency_id=usd.id THEN 1 ELSE ur.rate/sr.rate END END AS amount_usd,
                CASE WHEN p.id IS NULL THEN 'missing' WHEN p.matches>1 THEN 'ambiguous'
                    WHEN pu.category_id<>kg.category_id THEN 'unit'
                    WHEN p.currency_id<>usd.id AND (sr.rate IS NULL OR ur.rate IS NULL) THEN 'rate' ELSE 'valued' END AS valuation_status,
                CASE WHEN p.matches=1 AND pu.category_id=kg.category_id AND (p.currency_id=usd.id OR (sr.rate IS NOT NULL AND ur.rate IS NOT NULL)) THEN 0 ELSE 1 END AS unvalued_week_qty
            FROM step_export_estimate_week w
            JOIN step_export_estimate_line l ON l.id=w.line_id
            JOIN step_export_estimate e ON e.id=l.estimate_id
            CROSS JOIN res_currency usd
            CROSS JOIN uom_uom kg
            LEFT JOIN LATERAL (
                SELECT ranked.*,count(*) OVER (PARTITION BY score,valid_from) AS matches FROM (
                    SELECT pl.id,pl.price,pl.currency_id,pl.uom_id,pr.valid_from,
                        (CASE WHEN pl.product_id IS NOT NULL THEN 1 ELSE 0 END+
                         CASE WHEN pl.packaging_id IS NOT NULL THEN 1 ELSE 0 END+
                         CASE WHEN pl.week_number<>0 THEN 1 ELSE 0 END) AS score
                    FROM step_producer_preliq_price_line pl JOIN step_producer_preliq_price pr ON pr.id=pl.price_id
                    WHERE pr.active AND pr.company_id=e.company_id AND pr.season_id=e.season_id AND pr.species_id=l.species_id
                        AND w.week_start BETWEEN pr.valid_from AND pr.valid_to AND pl.variety_id=l.variety_id
                        AND (pl.product_id IS NULL OR pl.product_id=l.product_id)
                        AND (pl.packaging_id IS NULL OR pl.packaging_id=l.packaging_id)
                        AND pl.caliber_id IS NULL AND (pl.week_number=0 OR pl.week_number=EXTRACT(WEEK FROM w.week_start))
                ) ranked ORDER BY score DESC,valid_from DESC,id LIMIT 1
            ) p ON TRUE
            LEFT JOIN uom_uom pu ON pu.id=p.uom_id
            LEFT JOIN LATERAL (SELECT rate FROM res_currency_rate WHERE currency_id=p.currency_id
                AND (company_id=e.company_id OR company_id IS NULL) AND name<=w.week_start ORDER BY company_id NULLS LAST,name DESC LIMIT 1) sr ON TRUE
            LEFT JOIN LATERAL (SELECT rate FROM res_currency_rate WHERE currency_id=usd.id
                AND (company_id=e.company_id OR company_id IS NULL) AND name<=w.week_start ORDER BY company_id NULLS LAST,name DESC LIMIT 1) ur ON TRUE
            WHERE usd.id=%s AND kg.id=%s
        """, (self.env.ref('base.USD').id,self.env.ref('uom.product_uom_kgm').id))
