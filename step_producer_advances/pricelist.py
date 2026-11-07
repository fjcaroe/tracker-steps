"""Producer prices on native pricelists and their original product relations."""
from odoo import api, Command, fields, models, _
from odoo.exceptions import UserError, ValidationError


def company_commands(current, commands):
    selected = set(current)
    for command in commands:
        if command[0] == Command.SET:
            selected = set(command[2])
        elif command[0] == Command.LINK:
            selected.add(command[1])
        elif command[0] == Command.UNLINK:
            selected.discard(command[1])
        elif command[0] == Command.CLEAR:
            selected.clear()
        else:
            raise UserError(_('Seleccione compañías existentes; no se modifican compañías desde una lista.'))
    return sorted(selected)


class Pricelist(models.Model):
    _inherit = 'product.pricelist'

    step_advance_price = fields.Boolean('Lista de anticipos productor', default=False, copy=True, index=True)
    step_advance_company_ids = fields.Many2many('res.company',
        'step_advance_pricelist_company_rel', 'pricelist_id', 'company_id',
        string='Compañías', default=lambda self: self.env.company if self.env.context.get('default_step_advance_price') else self.env['res.company'])

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('step_advance_price', self.env.context.get('default_step_advance_price')):
                companies = company_commands([], values.get('step_advance_company_ids',
                    [Command.set(self.env.company.ids)]))
                self._advance_check_companies(companies)
                values.update(step_advance_price=True, company_id=companies[0] if len(companies) == 1 else False,
                    step_advance_company_ids=[Command.set(companies)], group_type=False, partner_id=False,
                    partner_ids=[Command.clear()], escalonado=False, cost_ids=[Command.clear()], cosecha=False)
        return super().create(values_list)

    def write(self, values):
        if 'step_advance_price' in values and any(row.step_advance_price != bool(values['step_advance_price']) for row in self):
            raise UserError(_('Cree una lista de productores nueva; no cambie el uso de una tarifa existente.'))
        for record in self.filtered('step_advance_price'):
            if 'step_advance_company_ids' in values:
                companies = company_commands(record.step_advance_company_ids.ids, values['step_advance_company_ids'])
                self._advance_check_companies(companies)
                own = dict(values, company_id=companies[0] if len(companies) == 1 else False)
                super(Pricelist, record).write(own)
            else:
                super(Pricelist, record).write(values)
        ordinary = self.filtered(lambda row: not row.step_advance_price)
        return super(Pricelist, ordinary).write(values) if ordinary else True

    def _advance_check_companies(self, companies):
        if not companies or set(companies) - set(self.env.user.company_ids.ids):
            raise ValidationError(_('Seleccione una o más compañías autorizadas para su usuario.'))

    @api.constrains('step_advance_price', 'company_id', 'step_advance_company_ids', 'date_init', 'date_end')
    def _advance_check_scope(self):
        for record in self.filtered('step_advance_price'):
            if not record.step_advance_company_ids:
                raise ValidationError(_('La lista requiere al menos una compañía.'))
            expected = record.step_advance_company_ids if len(record.step_advance_company_ids) == 1 else self.env['res.company']
            if record.company_id != expected:
                raise ValidationError(_('La compañía nativa debe coincidir con la selección de la lista.'))
            if record.date_init and record.date_end and record.date_end < record.date_init:
                raise ValidationError(_('Revise las fechas de vigencia de la lista.'))

    def _advance_price(self, product, market, packaging, kilos, day, species):
        self.ensure_one()
        if (not self.step_advance_price or not self.active or self.env.company not in self.step_advance_company_ids
                or self.date_init and day < self.date_init or self.date_end and day > self.date_end
                or self.especie_id and self.especie_id != species
                or self.grupo_variedad_id and self.grupo_variedad_id.id != self.env.context.get('advance_variety_group')):
            raise UserError(_('La lista no está vigente para la compañía, especie y fecha de recepción seleccionadas.'))
        kg = self.env.ref('uom.product_uom_kgm')
        candidates = []
        for rule in self.item_ids:
            if (rule.date_start and day < rule.date_start.date() or rule.date_end and day > rule.date_end.date()
                    or rule.step_advance_market_id and rule.step_advance_market_id != market
                    or rule.step_advance_packaging_id and rule.step_advance_packaging_id != packaging):
                continue
            qty = kg._compute_quantity(kilos, rule.uom_id, round=False)
            if not rule._is_applicable_for(product, qty) or rule.can_max and qty > rule.can_max:
                continue
            key = (rule.applied_on, -len(rule.categ_id.parent_path or ''), -sum(bool(value) for value in
                   (rule.step_advance_market_id, rule.step_advance_packaging_id)), -rule.min_quantity,
                   -(rule.date_start.toordinal() if rule.date_start else 0))
            candidates.append((key, rule))
        if not candidates:
            raise UserError(_('No hay precio de anticipo para %(product)s, mercado %(market)s, embalaje %(packaging)s y fecha %(date)s. Revise la lista y el mercado de la tarja.',
                product=product.display_name, market=market.display_name or '-',
                packaging=packaging.display_name or '-', date=day))
        candidates.sort(key=lambda value: value[0])
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            raise UserError(_('Hay reglas de precio igualmente específicas; ajuste su vigencia o selección.'))
        rule = candidates[0][1]
        # Prices use the explicit rule's native UoM. This also supports cartons
        # priced by kilogram without pretending their stock unit is a weight.
        if rule.compute_price == 'fixed':
            price = rule.uom_id._compute_price(rule.fixed_price, kg)
        else:
            if product.uom_id.category_id != kg.category_id:
                raise UserError(_('Las reglas de descuento o fórmula requieren un producto con unidad de peso. Use precio fijo por kg para embalajes contados en cajas.'))
            price = rule._compute_price(product, kilos, kg, fields.Datetime.to_datetime(day), currency=self.currency_id)
        if price <= 0:
            raise UserError(_('El precio por kilo debe ser mayor a cero.'))
        return price, rule


class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    # The legacy contractor extension made this product alias globally NOT NULL.
    # A category/global producer rule has no single labor. Preserve the original
    # requirement for every non-producer rule with a conditional constraint.
    labor_id = fields.Many2one(required=False)
    step_advance_market_id = fields.Many2one('step.fruit.market', string='Mercado', ondelete='restrict')
    step_advance_packaging_id = fields.Many2one('product.packaging', string='Embalaje', ondelete='restrict')

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            parent = self.env['product.pricelist'].browse(values.get('pricelist_id') or self.env.context.get('default_pricelist_id'))
            if parent.step_advance_price:
                values.setdefault('uom_id', self.env.ref('uom.product_uom_kgm').id)
                product = self.env['product.product'].browse(values.get('product_id'))
                values.setdefault('labor_id', product.product_tmpl_id.id or values.get('product_tmpl_id'))
        return super().create(values_list)

    @api.constrains('labor_id', 'pricelist_id', 'uom_id', 'step_advance_packaging_id', 'product_id', 'product_tmpl_id', 'can_max', 'min_quantity')
    def _advance_check_rule(self):
        kg = self.env.ref('uom.product_uom_kgm')
        for rule in self:
            if not rule.pricelist_id.step_advance_price:
                if not rule.labor_id:
                    raise ValidationError(_('La tarifa ordinaria conserva su labor/producto obligatorio.'))
                continue
            if rule.uom_id.category_id != kg.category_id:
                raise ValidationError(_('El precio de anticipo requiere una unidad de peso.'))
            if rule.can_max and rule.can_max < rule.min_quantity:
                raise ValidationError(_('La cantidad máxima no puede ser menor que la mínima.'))
            product = rule.product_id or rule.product_tmpl_id.product_variant_id
            if rule.step_advance_packaging_id and product and rule.step_advance_packaging_id.product_id != product:
                raise ValidationError(_('El embalaje debe corresponder al producto de la regla.'))
