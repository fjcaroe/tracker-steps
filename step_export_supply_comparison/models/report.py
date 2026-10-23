"""Live UNION of weekly demand and supply; never join their unrelated rows."""
from odoo import fields, models, tools


class SupplyComparison(models.Model):
    _name = 'step.export.supply.comparison'
    _description = 'Comparativo de programas de ventas y estimaciones'
    _auto = False
    _rec_name = 'week_start'
    _order = 'week_start, id'

    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', readonly=True)
    species_id = fields.Many2one('step.especie', string='Especie', readonly=True)
    variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    producer_id = fields.Many2one('res.partner', string='Productor', readonly=True)
    program_id = fields.Many2one('step.export.sales.program', string='Programa', readonly=True)
    estimate_id = fields.Many2one('step.export.estimate', string='Estimación', readonly=True)
    week_start = fields.Date(string='Semana', readonly=True)
    source = fields.Selection([('sale', 'Programa de ventas'), ('estimate', 'Estimación')],
                              string='Origen', readonly=True)
    sale_kg = fields.Float(string='Kg venta', readonly=True)
    estimate_kg = fields.Float(string='Kg estimación', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('''CREATE VIEW step_export_supply_comparison AS
            SELECT w.id::bigint*2 AS id, p.company_id, p.season_id, p.species_id, p.variety_id,
                NULL::integer AS producer_id, p.id AS program_id, NULL::integer AS estimate_id,
                w.week_start, 'sale'::varchar AS source,
                w.kg_qty AS sale_kg, 0::double precision AS estimate_kg
            FROM step_export_sales_program_line w
            JOIN step_export_sales_program p ON p.id=w.program_id
            WHERE p.state='current'
            UNION ALL
            SELECT w.id::bigint*2+1 AS id, e.company_id, e.season_id, l.species_id, l.variety_id,
                e.producer_id, NULL::integer AS program_id, e.id AS estimate_id,
                w.week_start, 'estimate'::varchar AS source,
                0::double precision AS sale_kg, w.export_kg AS estimate_kg
            FROM step_export_estimate_week w
            JOIN step_export_estimate_line l ON l.id=w.line_id
            JOIN step_export_estimate e ON e.id=l.estimate_id
            WHERE e.state='current'
        ''')
