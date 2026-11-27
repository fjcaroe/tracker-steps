from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

DTE_STATES = [('not_sent', 'Pending To Be Sent'), ('ask_for_status', 'Ask For Status'), ('accepted', 'Accepted'),
              ('objected', 'Accepted With Objections'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled'), ('manual', 'Manual')]
QUALITY_RULE = "['|', ('company_id', 'in', company_ids), ('point_id.company_id', 'in', company_ids)]"
FISCAL = {'l10n_cl_dte_status', 'l10n_latam_document_number'}


class Picking(models.Model):
    _inherit = 'stock.picking'

    l10n_cl_dte_status = fields.Selection(DTE_STATES, string='SII DTE status', copy=False, tracking=100,
                                         help='Estado de la guía registrado en el SII.')
    l10n_latam_document_number = fields.Char(string='Delivery Guide Number', copy=False)
    quality_check_todo = fields.Boolean(string='Pending checks', compute='_compute_pending_history_checks',
                                        search='_search_pending_history_checks')
    step_external_reception_folio = fields.Char(string='Referencia externa', readonly=True, copy=False, index=True)
    step_reception_product_ids = fields.Many2many('product.product', string='Producto', compute='_compute_reception_summary')
    step_reception_packaging_ids = fields.Many2many('product.packaging', string='Embalaje', compute='_compute_reception_summary')
    step_reception_container_qty = fields.Float(string='Cantidad de envases', digits='Product Unit of Measure',
                                               compute='_compute_reception_summary')
    step_reception_net_kg = fields.Float(string='Cantidad (kg)', digits='Stock Weight', compute='_compute_reception_summary')
    step_reception_avg_kg = fields.Float(string='Peso promedio (kg/envase)', digits='Stock Weight',
                                         compute='_compute_reception_summary')

    @api.model_create_multi
    def create(self, vals_list):
        if any(any(values.get(name) for name in FISCAL) for values in vals_list):
            raise ValidationError(_('La emisión de guías requiere el proveedor de despacho.'))
        return super().create(vals_list)

    def write(self, values):
        if FISCAL.intersection(values):
            raise ValidationError(_('La emisión de guías requiere el proveedor de despacho.'))
        return super().write(values)

    def _history_check_pickings(self, pending, picking_ids=None):
        # The original company rule admits both the check's company and its control point's company.
        model = 'quality.check'
        if not self.env.su and model not in self.env['ir.model.access']._get_allowed_models('read'):
            raise AccessError(_('No tiene acceso a los controles de calidad.'))
        rules = self.env['ir.rule']._get_rules(model,'read').sudo()
        original = self.env.ref('quality.quality_check_comp_rule').sudo()
        if rules and (rules != original or original.domain_force != QUALITY_RULE):
            raise ValidationError(_('Revise las reglas de acceso de Calidad antes de consultar sus controles.'))
        self.env.cr.execute("""SELECT DISTINCT q.picking_id FROM quality_check q LEFT JOIN quality_point p ON p.id=q.point_id
            WHERE q.picking_id IS NOT NULL AND (%s OR q.picking_id=ANY(%s)) AND ((q.quality_state IS NOT DISTINCT FROM 'none')=%s)
              AND (%s OR q.company_id=ANY(%s) OR p.company_id=ANY(%s))""",
            (picking_ids is None, picking_ids or [], pending, not bool(rules), self.env.companies.ids, self.env.companies.ids))
        return {ident for ident, in self.env.cr.fetchall()}

    def _search_pending_history_checks(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError(_('El filtro de controles pendientes requiere un booleano.'))
        wanted = value if operator=='=' else not value
        # A transfer with both pending and finished checks satisfies both native filters.
        return [('id','in',list(self._history_check_pickings(wanted)))]

    @api.depends_context('uid','company','allowed_company_ids')
    def _compute_pending_history_checks(self):
        self.check_access('read')
        pending = self._history_check_pickings(True,self.ids) if self.ids else set()
        for picking in self:
            picking.quality_check_todo = picking.id in pending

    @api.depends_context('uid','company','allowed_company_ids')
    @api.depends('state','fruit_tag_line_ids.packaging_id.product_id','fruit_tag_line_ids.quantity',
                 'fruit_tag_line_ids.kilos','move_ids.state','move_ids.product_id','move_ids.product_packaging_id',
                 'move_ids.quantity','move_ids.product_uom_qty','move_ids.product_uom')
    def _compute_reception_summary(self):
        rows = self.fruit_tag_line_ids
        moves = self.move_ids.filtered(lambda move: move.state != 'cancel')
        rows.check_access('read')
        moves.check_access('read')
        # These snapshots belong to the original reception application. Use only the already-authorized rows.
        self.env.cr.execute('SELECT id,product_id FROM step_packing_picking_tag_line WHERE id=ANY(%s)', (rows.ids,))
        tag_products = dict(self.env.cr.fetchall())
        self.env.cr.execute('SELECT id,step_fruit_packaging_qty FROM stock_move WHERE id=ANY(%s)', (moves.ids,))
        container_counts = dict(self.env.cr.fetchall())
        kg = self.env.ref('uom.product_uom_kgm')
        for picking in self:
            tags = picking.fruit_tag_line_ids
            operations = picking.move_ids.filtered(lambda move: move.state != 'cancel')
            products = self.env['product.product']
            for row in tags:
                products |= self.env['product.product'].browse(tag_products.get(row.id)) or row.packaging_id.product_id
            if not products or any(not (tag_products.get(row.id) or row.packaging_id) for row in tags):
                products |= operations.product_id
            packages = tags.packaging_id
            if not packages or any(not row.packaging_id for row in tags):
                packages |= operations.product_packaging_id
            containers = sum(tags.mapped('quantity')) or sum(container_counts.get(move.id) or 0 for move in operations)
            weight = sum(tags.mapped('kilos')) or sum(move.product_uom._compute_quantity(
                move.quantity or (move.product_uom_qty if picking.state != 'done' else 0), kg, round=False)
                for move in operations if move.product_uom.category_id == kg.category_id)
            picking.step_reception_product_ids = products
            picking.step_reception_packaging_ids = packages
            picking.step_reception_container_qty = containers
            picking.step_reception_net_kg = weight
            picking.step_reception_avg_kg = weight / containers if containers else 0


class OriginalFieldHelp(models.Model):
    _inherit = 'ir.model.fields'

    def _reflect_field_params(self, field, model_id):
        values = super()._reflect_field_params(field, model_id)
        if field.model_name=='stock.picking' and field.name=='l10n_cl_dte_status':
            original = self.env.ref('l10n_cl_edi_stock.field_stock_picking__l10n_cl_dte_status')
            values['help'] = original.with_context(lang='en_US').help
        return values
