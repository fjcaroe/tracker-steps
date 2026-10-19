import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SagLot(models.Model):
    _inherit = 'step.packing.inspection'

    # Stored values from the old related company column are preserved. SAG lots
    # now have their own company and may include outputs of multiple native OTs.
    company_id = fields.Many2one('res.company', related=False, compute=False, store=True,
        required=True, default=lambda self: self.env.company)
    production_id = fields.Many2one(required=False)
    sag_species_id = fields.Many2one('step.especie', related=False, compute=False, store=True, string='Especie del lote')
    sag_packing_id = fields.Many2one('res.partner', related=False, compute=False, store=True, string='Establecimiento SAG', check_company=True)
    sag_service_id = fields.Many2one('step.packing.sag.service', string='Tipo de servicio SAG', ondelete='restrict',
        default=lambda self: self.env.ref('step_packing_sag.service_inspection', raise_if_not_found=False))
    sag_fruit_type = fields.Selection([('conventional', 'Convencional'), ('organic', 'Orgánico')], string='Tipo fruta', default='conventional')
    sag_receiver_id = fields.Many2one('res.partner', string='Recibidor', check_company=True)
    sag_instruction_id = fields.Many2one('step.export.dispatch.order', string='Instructivo de despacho', check_company=True, ondelete='restrict')
    sag_variety_ids = fields.Many2many('step.variedad', relation='step_packing_sag_variety_rel', string='Variedades del filtro')
    sag_production_ids = fields.Many2many('step.packing.production', compute='_compute_sag_productions', string='OT de las tarjas')
    sag_available_package_ids = fields.Many2many('stock.quant.package', compute='_compute_available_sag_packages')
    sag_scan = fields.Char('Leer código / ingresar folios', copy=False)
    sag_multi_ot = fields.Boolean('Lote SAG ampliado T93', default=False, copy=False, readonly=True)

    def _inspection_productions(self):
        productions = self.env['step.packing.production'].search([('step_packing_output_tag_ids', 'in', self.package_ids.ids)])
        return productions | self.filtered(lambda r: not r.sag_multi_ot).production_id

    def _counts_for_dispatch(self):
        self.ensure_one()
        return super()._counts_for_dispatch() and (self.kind != 'sag' or not self.sag_service_id or self.sag_service_id.sanitary)

    @api.depends('package_ids', 'production_id')
    def _compute_sag_productions(self):
        for rec in self:
            rec.sag_production_ids = rec._inspection_productions()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            production = self.env['step.packing.production'].browse(vals.get('production_id'))
            if production:
                vals.setdefault('company_id', production.company_id.id)
                species = production.fruit_species_id or production.step_packing_output_tag_ids.especie_id
                vals.setdefault('sag_species_id', species.id if len(species) == 1 else False)
                vals.setdefault('sag_packing_id', production.packing_partner_id.id)
            if vals.get('kind', self.env.context.get('default_kind')) == 'sag':
                vals['sag_multi_ot'] = True
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        if self.kind == 'sag' and self.state != 'draft':
            default.setdefault('sag_service_id', self.env.ref('step_packing_sag.service_reinspection').id)
        return super().copy(default)

    def write(self, vals):
        if 'sag_multi_ot' in vals:
            raise UserError(_('No se modifica la identificación del lote ampliado.'))
        lot_fields = {'package_ids','sag_species_id','sag_fruit_type','sag_variety_ids','sag_instruction_id','sag_service_id'}
        promote = self.filtered(lambda r: r.kind == 'sag' and not r.sag_multi_ot and r.state == 'draft') if lot_fields & vals.keys() else self.browse()
        if promote:
            super(SagLot, promote).write(dict(vals, sag_multi_ot=True))
            remaining = self - promote
            return super(SagLot, remaining).write(vals) if remaining else True
        return super().write(vals)

    def _sag_candidates(self):
        self.ensure_one()
        if not self.sag_species_id or not self.sag_fruit_type or not self.sag_service_id:
            return self.env['stock.quant.package']
        candidates = self.env['stock.quant.package'].search([
            ('is_fruit_tag', '=', True), ('step_tag_kind', '=', 'E'),
            ('step_tag_state', '=', 'validated'), ('company_id', '=', self.company_id.id),
            ('especie_id', '=', self.sag_species_id.id), ('fruit_type', '=', self.sag_fruit_type)])
        own_id = self._origin.id if isinstance(self._origin.id, int) else 0
        prior = self.search([('kind', '=', 'sag'), ('id', '!=', own_id), ('package_ids', 'in', candidates.ids)]).filtered(lambda r: r._counts_for_dispatch())
        busy = prior.filtered(lambda r: r.state == 'draft').package_ids
        used = prior.package_ids if self.sag_service_id.sanitary and not self.sag_service_id.reinspection else busy
        return candidates.filtered(lambda tag: tag not in used
            and (not self.sag_variety_ids or tag.variedad_id in self.sag_variety_ids)
            and bool(tag.quant_ids.filtered(lambda q: q.quantity > 0 and q.location_id.usage == 'internal'))
            and (not self.sag_instruction_id or self.sag_instruction_id._matches(tag)))

    @api.depends('company_id', 'sag_species_id', 'sag_fruit_type', 'sag_variety_ids', 'sag_instruction_id', 'sag_service_id', 'package_ids')
    def _compute_available_sag_packages(self):
        for rec in self:
            rec.sag_available_package_ids = rec._sag_candidates() | rec.package_ids

    @api.onchange('sag_instruction_id')
    def _onchange_sag_instruction(self):
        for rec in self.filtered('sag_instruction_id'):
            plan = rec.sag_instruction_id
            rec.sag_receiver_id = plan.receiver_id
            rec.sag_species_id = plan.species_id
            rec.sag_country_id = plan.shipment_id.destination_country_id
            rec.sag_fruit_type = plan.shipment_id.sales_program_id.fruit_type or rec.sag_fruit_type

    @api.onchange('sag_scan')
    def _onchange_sag_scan(self):
        for rec in self:
            if not rec.sag_scan:
                continue
            tags = self.env['stock.quant.package']
            for code in filter(None, (c.strip() for c in re.split(r'[\r\n,;]+', rec.sag_scan))):
                found = tags.search([('name', '=', code), ('company_id', '=', rec.company_id.id)])
                if len(found) != 1 or found not in rec.sag_available_package_ids:
                    raise UserError(_('Folio no disponible para el lote y sus filtros: %s', code))
                tags |= found
            rec.package_ids |= tags
            rec.sag_scan = False

    @api.constrains('package_ids', 'production_id', 'company_id', 'sag_species_id', 'sag_fruit_type',
        'sag_variety_ids', 'sag_instruction_id', 'sag_service_id', 'sag_receiver_id', 'sag_country_id')
    def _check_packages(self):
        regular = self.filtered(lambda r: r.kind != 'sag' or not r.sag_multi_ot)
        if regular:
            super(SagLot, regular)._check_packages()
        for rec in self - regular:
            if not rec.package_ids or not rec.sag_species_id or not rec.sag_service_id:
                raise ValidationError(_('Defina especie, servicio y tarjas del lote SAG.'))
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(rec.package_ids.ids))])
            rec.package_ids.invalidate_recordset()
            if rec.package_ids - rec._sag_candidates():
                raise ValidationError(_('Una tarja no cumple especie, variedades, stock validado, tipo fruta, instructivo o disponibilidad de inspección.'))
            productions = rec._inspection_productions()
            if any(p.company_id != rec.company_id for p in productions):
                raise ValidationError(_('Las OT y el lote SAG deben pertenecer a la misma empresa.'))
            if any(v.especie_id != rec.sag_species_id for v in rec.sag_variety_ids):
                raise ValidationError(_('Las variedades deben pertenecer a la especie del lote.'))
            if rec.sag_instruction_id:
                plan = rec.sag_instruction_id
                if rec.sag_receiver_id != plan.receiver_id or rec.sag_country_id != plan.shipment_id.destination_country_id:
                    raise ValidationError(_('Recibidor y país deben coincidir con el instructivo.'))
                plan._check_capacity(rec.package_ids)

    def _sag_ready(self):
        self.filtered(lambda r: r.sag_multi_ot)._check_packages()
        return super()._sag_ready()
