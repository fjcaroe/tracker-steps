from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError


class ShipmentReport(models.Model):
    _name = 'step.export.shipment.report'
    _description = 'Informe dinámico de embarques reales'
    _auto = False
    _order = 'date desc, shipment_id, id'
    _rec_name = 'shipment_id'
    shipment_id = fields.Many2one('step.export.export', string='Embarque', readonly=True)
    shipment_number = fields.Char(related='shipment_id.shipment_number', string='Núm. embarque', readonly=True)
    source_line_id = fields.Many2one('step.export.shipment.line', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    company_currency_id = fields.Many2one('res.currency', readonly=True)
    usd_currency_id = fields.Many2one('res.currency', readonly=True)
    date = fields.Date(string='Fecha embarque', readonly=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', readonly=True)
    transport_type = fields.Selection([('sea', 'Marítimo'), ('air', 'Aéreo'), ('land', 'Terrestre')], readonly=True, string='Tipo embarque')
    sales_program_id = fields.Many2one('step.export.sales.program', string='Programa de ventas', readonly=True)
    receiver_id = fields.Many2one('res.partner', string='Recibidor', readonly=True)
    sale_mode_id = fields.Many2one('step.export.sale.mode', string='Modalidad de venta', readonly=True)
    vessel_id = fields.Many2one('step.export.vessel', string='Nave', readonly=True)
    destination_country_id = fields.Many2one('res.country', string='País destino', readonly=True)
    destination_port_id = fields.Many2one('l10n_cl.customs_port', string='Puerto destino', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    caliber_id = fields.Many2one('step.management.fruit.caliber', string='Calibre', readonly=True)
    quality_id = fields.Many2one('step.management.fruit.quality', string='Calidad', readonly=True)
    label = fields.Char(string='Marca', readonly=True)
    container_qty = fields.Float(string='Contenedores', readonly=True)
    pallet_qty = fields.Float(string='Pallets', readonly=True)
    box_qty = fields.Float(string='Cajas', readonly=True)
    kg_qty = fields.Float(string='Kilos', readonly=True)
    amount_company = fields.Monetary(string='Venta (moneda empresa)', currency_field='company_currency_id', readonly=True)
    amount_usd = fields.Monetary(string='Venta USD', currency_field='usd_currency_id', readonly=True)
    price_per_kg = fields.Float(string='Precio por kg (USD)', aggregator='avg', readonly=True)
    shipment_count = fields.Integer(string='Embarques', readonly=True)
    allocation_missing = fields.Boolean(string='Sin kilos distribuibles', readonly=True)

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None):
        requested = list(aggregates)
        prices = [index for index, name in enumerate(requested) if name.startswith('price_per_kg:')]
        if prices and any('price_per_kg' in str(item) for item in having):
            raise UserError(_('Filtre el precio después de agrupar; el promedio se calcula con los kilos totales.'))
        native = ['shipment_id:count_distinct' if name.startswith('shipment_count:') else name for name in requested]
        if prices:
            native += ['amount_usd:sum', 'kg_qty:sum']
        values = super()._read_group(domain, groupby, native, having, offset, limit, order)
        result = []
        for value in values:
            row = list(value[:len(groupby) + len(requested)])
            if prices:
                price = value[-2] / value[-1] if value[-1] else 0.0
                for index in prices:
                    row[len(groupby) + index] = price
            result.append(tuple(row))
        return result

    def action_open_shipment(self):
        self.ensure_one()
        self.shipment_id.check_access('read')
        return {'type': 'ir.actions.act_window', 'res_model': 'step.export.export',
                'res_id': self.shipment_id.id, 'view_mode': 'form', 'target': 'current'}

    def init(self):
        usd = self.env.ref('base.USD').id
        debit = 'd.step_export_shipment_id' if 'debit_origin_id' in self.env['account.move']._fields else 'NULL::integer'
        debit_join = 'LEFT JOIN account_move d ON d.id=m.debit_origin_id' if 'debit_origin_id' in self.env['account.move']._fields else ''
        def rate(currency):
            scope = "r.currency_id=%s AND (r.company_id IS NULL OR r.company_id=COALESCE(NULLIF(split_part(c.parent_path,'/',1),'')::integer,c.id))" % currency
            return "COALESCE((SELECT r.rate FROM res_currency_rate r WHERE %s AND r.name<=COALESCE(m.invoice_date,m.date) ORDER BY r.company_id NULLS LAST,r.name DESC LIMIT 1),(SELECT r.rate FROM res_currency_rate r WHERE %s ORDER BY r.company_id NULLS LAST,r.name ASC LIMIT 1),1.0)" % (scope, scope)
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f'''
            CREATE VIEW {self._table} AS
            WITH financial AS (
                SELECT COALESCE(m.step_export_shipment_id,original.step_export_shipment_id,{debit}) shipment_id,
                       m.company_id, SUM(m.amount_untaxed_signed) amount_company,
                       SUM((CASE WHEN m.move_type='out_refund' THEN -1 ELSE 1 END)*m.amount_untaxed*
                           {rate(str(usd))}/NULLIF({rate('m.currency_id')},0)) amount_usd
                FROM account_move m JOIN res_company c ON c.id=m.company_id
                LEFT JOIN account_move original ON original.id=m.reversed_entry_id {debit_join}
                WHERE m.state='posted' AND m.move_type IN ('out_invoice','out_refund')
                GROUP BY 1,2
            ), totals AS (
                SELECT shipment_id,SUM(kg_qty) kg FROM step_export_shipment_line GROUP BY shipment_id
            ), loads AS (
                SELECT l.id,l.id source_line_id,l.shipment_id,l.product_id,l.variety_id,l.caliber_id,
                    l.quality_id,l.label,l.pallet_qty,l.box_qty,l.kg_qty,
                    CASE WHEN t.kg>0 THEN l.kg_qty/t.kg ELSE 0 END fraction,FALSE allocation_missing
                FROM step_export_shipment_line l JOIN totals t ON t.shipment_id=l.shipment_id
                UNION ALL
                SELECT -s.id,NULL,s.id,NULL,NULL,NULL,NULL,NULL,0,0,0,1,TRUE
                FROM step_export_export s LEFT JOIN totals t ON t.shipment_id=s.id WHERE COALESCE(t.kg,0)<=0
            )
            SELECT l.id,l.source_line_id,s.id shipment_id,s.company_id,c.currency_id company_currency_id,
                {usd} usd_currency_id,s.date,s.season_id,s.transport_type,s.sales_program_id,s.receiver_id,
                s.sale_mode_id,s.vessel_id,s.destination_country_id,s.destination_port_id,
                l.product_id,l.variety_id,l.caliber_id,l.quality_id,l.label,
                s.container_qty*l.fraction container_qty,l.pallet_qty,l.box_qty,l.kg_qty,
                COALESCE(f.amount_company,0)*l.fraction amount_company,
                COALESCE(f.amount_usd,0)*l.fraction amount_usd,
                COALESCE(f.amount_usd,0)*l.fraction/NULLIF(l.kg_qty,0) price_per_kg,
                1 shipment_count,l.allocation_missing
            FROM loads l JOIN step_export_export s ON s.id=l.shipment_id
            JOIN res_company c ON c.id=s.company_id
            LEFT JOIN financial f ON f.shipment_id=s.id AND f.company_id=s.company_id
            WHERE s.state IN ('dispatched','shipped','invoiced','settled')
        ''')
