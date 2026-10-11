"""T70-T72: extend native species and read original receipt tag rows once."""
from odoo import fields, models, tools


class Species(models.Model):
    _inherit = 'step.especie'
    sag_code = fields.Char(string='Código SAG')
    base_boxes_per_pallet = fields.Float(string='Caja Base x pallet', digits=(16, 2))
    _sql_constraints = [('base_boxes_per_pallet_nonnegative', 'CHECK(base_boxes_per_pallet >= 0)', 'Caja Base x pallet no puede ser negativa.')]


class FruitReceptionReport(models.Model):
    _name = 'step.fruit.reception.report'
    _description = 'Informe de recepciones de fruta'
    _auto = False
    _rec_name = 'picking_id'
    _order = 'reception_date desc, id desc'
    picking_id = fields.Many2one('stock.picking', string='Recepción', readonly=True)
    tag_line_id = fields.Many2one('step.packing.picking.tag.line', string='Detalle original', readonly=True)
    company_id = fields.Many2one('res.company', string='Empresa', readonly=True)
    reception_kind = fields.Selection([('process','Fruta a proceso'),('packed','Fruta embalada')], string='Tipo de recepción', readonly=True)
    reception_date = fields.Datetime(string='Fecha recepción', readonly=True)
    state = fields.Selection([('draft','Borrador'),('waiting','Esperando'),('confirmed','En espera'),('assigned','Preparado'),('done','Hecho'),('cancel','Cancelado')], string='Estado', readonly=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', readonly=True)
    producer_id = fields.Many2one('res.partner', string='Productor', readonly=True)
    fundo_id = fields.Many2one('step.fundo', string='Fundo', readonly=True)
    species_id = fields.Many2one('step.especie', string='Especie', readonly=True)
    variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Lote de stock', readonly=True)
    lot_reference = fields.Char(string='Lote declarado en recepción', readonly=True)
    ambiguous_lot = fields.Boolean(string='Varios lotes en la tarja', readonly=True)
    package_id = fields.Many2one('stock.quant.package', string='Tarja', readonly=True)
    product_id = fields.Many2one('product.product', string='Producto', readonly=True)
    packaging_id = fields.Many2one('product.packaging', string='Embalaje', readonly=True)
    packaging_qty = fields.Float(string='Cantidad de embalajes', readonly=True)
    kilos = fields.Float(string='Kilos', readonly=True)
    boxes = fields.Float(string='Cajas registradas', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UdM', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr,self._table)
        self.env.cr.execute("""CREATE VIEW step_fruit_reception_report AS
            SELECT l.id,l.id AS tag_line_id,l.picking_id,p.company_id,p.step_fruit_reception_kind AS reception_kind,
                COALESCE(p.date_done,p.scheduled_date,p.date) AS reception_date,p.state,
                p.fruit_season_id AS season_id,f.partner_id AS producer_id,p.fruit_fundo_id AS fundo_id,
                p.fruit_species_id AS species_id,p.fruit_variety_id AS variety_id,
                COALESCE(l.stock_lot_id,CASE WHEN lots.lot_count=1 THEN lots.lot_id END) AS lot_id,
                p.fruit_lot AS lot_reference,
                (l.stock_lot_id IS NULL AND lots.lot_count>1) AS ambiguous_lot,
                l.package_id,l.product_id,l.packaging_id,l.quantity AS packaging_qty,l.kilos,l.box_count AS boxes,l.uom_id
            FROM step_packing_picking_tag_line l
            JOIN stock_picking p ON p.id=l.picking_id
            JOIN stock_picking_type pt ON pt.id=p.picking_type_id
            LEFT JOIN step_fundo f ON f.id=p.fruit_fundo_id
            LEFT JOIN LATERAL (
                SELECT count(DISTINCT ml.lot_id) AS lot_count,min(ml.lot_id) AS lot_id FROM stock_move_line ml
                WHERE ml.picking_id=p.id AND ml.result_package_id=l.package_id AND ml.product_id=l.product_id AND ml.company_id=p.company_id
            ) lots ON TRUE
            WHERE pt.code='incoming' AND p.step_fruit_reception_kind IN ('process','packed')
        """)
