"""T74-T75: native package masters and the formulas explicitly requested."""
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class PackageType(models.Model):
    _inherit = 'stock.package.type'

    step_export_boxes_per_pallet = fields.Float(string='Cajas por pallet/bins', digits=(12, 2))
    fruit_package_group = fields.Selection([
        ('bins', 'Bins'), ('pallet', 'Pallet'), ('floor', 'A piso'),
    ], string='Grupo paquete', help='Seleccione el grupo; no se infiere por el nombre del envase.')
    pallets_per_aircraft = fields.Float(string='Pallet por avión', digits=(12, 2),
                                      help='Capacidad para embarques aéreos.')

    @api.constrains('step_export_boxes_per_pallet', 'pallets_per_aircraft')
    def _check_fruit_capacity(self):
        for record in self:
            if record.step_export_boxes_per_pallet < 0 or record.pallets_per_aircraft < 0:
                raise ValidationError(_('Las capacidades del envase no pueden ser negativas.'))


class EstimateLine(models.Model):
    _inherit = 'step.export.estimate.line'

    process_pallet_qty = fields.Float(string='Pallets proceso', compute='_compute_quantities', store=True,
                                    readonly=True)

    @api.depends('delivery_kind', 'export_kg', 'export_percentage', 'kg_per_box', 'boxes_per_package',
                 'package_type_id.fruit_package_group', 'package_type_id.step_export_boxes_per_pallet',
                 'species_id.kg_caja', 'species_id.base_boxes_per_pallet')
    def _compute_quantities(self):
        super()._compute_quantities()
        for line in self:
            capacity = line.package_type_id.step_export_boxes_per_pallet
            group = line.package_type_id.fruit_package_group
            process_kg = (line.export_kg / line.export_percentage
                          if line.delivery_kind == 'process' and line.export_percentage > 0 else 0)
            line.process_kg = process_kg
            line.harvest_box_qty = process_kg / line.kg_per_box if line.kg_per_box > 0 else 0
            # The customer's T75 denominators are used literally, without
            # multiplying by kg per harvest box or by kg per base box.
            line.bin_qty = process_kg / capacity if group == 'bins' and capacity > 0 else 0
            line.process_pallet_qty = process_kg / capacity if group == 'pallet' and capacity > 0 else 0
            line.export_box_qty = line.export_kg / line.species_id.kg_caja if line.species_id.kg_caja > 0 else 0
            line.export_pallet_qty = (line.export_kg / line.species_id.base_boxes_per_pallet
                                      if line.species_id.base_boxes_per_pallet > 0 else 0)


class EstimateReport(models.Model):
    _inherit = 'step.producer.estimate.report'

    process_pallet_qty = fields.Float(string='Pallets proceso', readonly=True)

    def init(self):
        super().init()
        # Preserve the original valuation, weekly rows, access rules and IDs.
        # Redefine this same SQL view with the shared master denominators.
        self.env.cr.execute('SELECT pg_get_viewdef(%s::regclass, true)', (self._table,))
        original = self.env.cr.fetchone()[0].rstrip().rstrip(';')
        self.env.cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum", (self._table,))
        columns = [row[0] for row in self.env.cr.fetchall()]
        formulas = {
            'process_kg': "CASE WHEN l.delivery_kind='process' AND l.export_percentage>0 THEN r.export_kg/l.export_percentage ELSE 0 END",
            'export_box_qty': 'CASE WHEN s.kg_caja>0 THEN r.export_kg/s.kg_caja ELSE 0 END',
            'export_pallet_qty': 'CASE WHEN s.base_boxes_per_pallet>0 THEN r.export_kg/s.base_boxes_per_pallet ELSE 0 END',
            'bin_qty': "CASE WHEN l.delivery_kind='process' AND l.export_percentage>0 AND p.fruit_package_group='bins' AND p.step_export_boxes_per_pallet>0 THEN r.export_kg/l.export_percentage/p.step_export_boxes_per_pallet ELSE 0 END",
        }
        # Columns are checked against the model before quoting, not supplied
        # by a caller or by any business record.
        assert all(name in self._fields and name.replace('_','').isalnum() for name in columns)
        select = ','.join(formulas.get(name, 'r."'+name+'"')+' AS "'+name+'"' for name in columns)
        select += ",CASE WHEN l.delivery_kind='process' AND l.export_percentage>0 AND p.fruit_package_group='pallet' AND p.step_export_boxes_per_pallet>0 THEN r.export_kg/l.export_percentage/p.step_export_boxes_per_pallet ELSE 0 END AS process_pallet_qty"
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('CREATE VIEW step_producer_estimate_report AS SELECT '+select+
            ' FROM ('+original+') r JOIN step_export_estimate_line l ON l.id=r.line_id'
            ' JOIN step_especie s ON s.id=l.species_id LEFT JOIN stock_package_type p ON p.id=l.package_type_id')
