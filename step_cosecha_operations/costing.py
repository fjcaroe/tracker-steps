"""Preview native harvest costs without writing historical worksheet inputs."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


OWN_OUTPUTS = ('cost_id_domain', 'hrs_total', 'total_trato', 'valor_hrs_extra',
    'variable_trato', 'sem_corrida', 'sab_dom', 'gratifica', 'cost_sueldo',
    'seguro', 'feriado', 'ias', 'cost_empresa')
CONTRACT_OUTPUTS = ('cost_id_domain', 'employee_id_domain', 'trato_total')


def preview(line):
    # Unsaved form lines and the dashboard's virtual lines may themselves have
    # NewIds. Copy their inputs explicitly: a NewId is not a database origin.
    names = ('registry_id', 'employee_id', 'contract_id', 'cost_id', 'labor_id',
        'uom_id', 'quantity', 'hrs', 'hrs_extra', 'cant_minima', 'tarifa', 'sueldo_base')
    values = {name: line[name] for name in names if name in line._fields}
    # Give the preview its own NewId. Reusing an origin would alias the
    # dashboard's existing virtual record while that field is being computed.
    virtual = line.with_context(step_harvest_native_cost_preview=True).new(values)
    registry = line.registry_id
    if registry.state != 'cont':
        virtual.labor_id = line.labor_id or registry.labor_id
        virtual.uom_id = line.uom_id or registry.product_uom_id
        if registry.pricelist_id.cosecha:
            virtual.tarifa = 0
            virtual.cant_minima = 0
    return virtual


class HarvestCosting(models.Model):
    _inherit = 'step.cosecha.registry'

    def _harvest_cost_rate(self, labor, quantity, uom):
        """The harvest rate's unit can differ from the labor product's unit.

        Harvest minimum output is displayed even below that target; the piece
        amount remains rate × actual output, with the salary guarantee handled
        by the native positive-only variable component.
        """
        self.ensure_one()
        empty = self.env['product.pricelist.item']
        if not labor or not uom or not self.pricelist_id.cosecha:
            return empty, 0.0, 0.0
        if self.pricelist_id.company_id and self.pricelist_id.company_id != self.company_id:
            raise UserError(_('La tarifa de cosecha debe pertenecer a la empresa del registro o ser compartida.'))
        moment = fields.Datetime.to_datetime(self.date or fields.Datetime.now())
        rules = self.pricelist_id.item_ids.filtered(lambda item:
            ((item.product_id and item.product_id == labor.product_variant_id) or
             (not item.product_id and (item.product_tmpl_id or item.labor_id) == labor))
            and (not item.date_start or item.date_start <= moment)
            and (not item.date_end or item.date_end >= moment))
        exact = rules.filtered(lambda item: (item.uom_id or labor.uom_id) == uom)
        compatible = rules.filtered(lambda item: (item.uom_id or labor.uom_id).category_id == uom.category_id)
        rules = exact or compatible
        if not rules:
            return empty, 0.0, 0.0
        def threshold(item):
            return (item.uom_id or labor.uom_id)._compute_quantity(item.min_quantity, uom, round=False)
        eligible = rules.filtered(lambda item: threshold(item) <= float(quantity or 0))
        # Preserve variant precedence and quantity breaks. Below every target,
        # show the first target instead of silently falling back to product price.
        ordered = (eligible or rules).sorted(key=lambda item:
            (not bool(item.product_id), -threshold(item) if eligible else threshold(item), -item.id))
        item = ordered[0]
        unit = item.uom_id or labor.uom_id
        if item.compute_price == 'fixed':
            price = unit._compute_price(item.fixed_price, uom)
        else:
            # Non-fixed legacy rules retain the native formula calculation.
            qty = uom._compute_quantity(quantity or 0, unit, round=False)
            price = unit._compute_price(item._compute_price(labor.product_variant_id, qty, unit,
                moment, currency=self.pricelist_id.currency_id), uom)
        return item, price, threshold(item)

    def _get_cosecha_unit_price(self, labor, quantity, uom=False):
        self.ensure_one()
        if self.state == 'cont':
            # Posting snapshots the inputs before the native action changes the
            # state. Later reads must use those inputs, not today's tariff.
            return self.env['product.pricelist.item'], 0.0
        if self.pricelist_id.cosecha:
            item, price, minimum = self._harvest_cost_rate(labor, quantity, uom or self.product_uom_id)
            return item, price
        return super()._get_cosecha_unit_price(labor, quantity, uom)

    def _snapshot_harvest_costing(self):
        for registry in self:
            lines = registry.registry_line if registry.type_tarea == 'propio' else registry.registry_tarja_line
            for line in lines:
                labor = line.labor_id or registry.labor_id
                unit = line.uom_id or registry.product_uom_id
                if registry.pricelist_id.cosecha:
                    item, price, minimum = registry._harvest_cost_rate(labor, line.quantity, unit)
                    if not item:
                        raise UserError(_('Falta una tarifa vigente para la labor y unidad de medida de esta cosecha.'))
                values = {'labor_id': labor.id, 'uom_id': unit.id,
                    'tarifa': line.harvest_unit_price, 'cant_minima': line.harvest_min_quantity}
                if registry.pricelist_id.cosecha:
                    values.update(tarifa=price, cant_minima=minimum)
                if registry.type_tarea == 'propio':
                    values['sueldo_base'] = line.harvest_salary_base
                line.write(values)

    def action_costeo(self):
        if any(record.state != 'apro' for record in self):
            raise UserError(_('Sólo un registro aprobado puede pasar a Costeo.'))
        self._snapshot_harvest_costing()
        return super().action_costeo()

    def action_conta(self):
        if any(record.state != 'costo' or record.invoice_id for record in self):
            raise UserError(_('Sólo una cosecha en Costeo sin contabilización asociada puede contabilizarse.'))
        self._snapshot_harvest_costing()
        return super().action_conta()

    def action_return_approved(self):
        self.check_access('write')
        if any(record.state != 'costo' or record.invoice_id or record.reception_picking_id
               or record.purchase_id or record.cos_recibida for record in self):
            raise UserError(_('Sólo una cosecha en Costeo sin documentos asociados puede volver a Aprobado.'))
        self.write({'state': 'apro'})
        return True


class HarvestOwnCosting(models.Model):
    _inherit = 'step.cosecha.registry.line'

    harvest_min_quantity = fields.Float('Cant Mínima', compute='_compute_total_hrs')
    harvest_unit_price = fields.Float('Tarifa', compute='_compute_total_hrs')
    harvest_salary_base = fields.Float('Sueldo Base', compute='_compute_total_hrs')

    @api.depends('hrs', 'hrs_extra', 'quantity', 'tarifa', 'labor_id', 'uom_id', 'contract_id',
        'sueldo_base', 'registry_id.date', 'registry_id.state', 'registry_id.fundo_id',
        'registry_id.especie_id', 'registry_id.grupo_variedad_id', 'registry_id.labor_id',
        'registry_id.product_uom_id', 'registry_id.pricelist_id',
        'registry_id.pricelist_id.item_ids.fixed_price', 'registry_id.pricelist_id.item_ids.min_quantity',
        'registry_id.pricelist_id.item_ids.uom_id', 'registry_id.pricelist_id.item_ids.date_start',
        'registry_id.pricelist_id.item_ids.date_end', 'registry_id.pricelist_id.item_ids.product_tmpl_id',
        'registry_id.pricelist_id.item_ids.product_id', 'registry_id.pricelist_id.item_ids.labor_id',
        'registry_id.pricelist_id.item_ids.compute_price')
    def _compute_total_hrs(self):
        # Enter the native compute through the field engine, which protects its
        # sibling outputs while the native method assigns rate/salary inputs.
        # A caller-supplied context cannot bypass preservation on real records.
        if self.env.context.get('step_harvest_native_cost_preview') and all(
                not isinstance(line.id, int) for line in self):
            super()._compute_total_hrs()
            for line in self:
                line.harvest_min_quantity = line.cant_minima
                line.harvest_unit_price = line.tarifa
                line.harvest_salary_base = line.sueldo_base
            return
        for line in self:
            virtual = preview(line)
            virtual.cost_empresa
            for name in OWN_OUTPUTS:
                line[name] = virtual[name]
            line.harvest_min_quantity = virtual.cant_minima
            line.harvest_unit_price = virtual.tarifa
            line.harvest_salary_base = virtual.sueldo_base
            if line.registry_id.state != 'cont' and line.registry_id.pricelist_id.cosecha:
                item, price, minimum = line.registry_id._harvest_cost_rate(
                    virtual.labor_id, line.quantity, line.uom_id or line.registry_id.product_uom_id)
                line.harvest_min_quantity = minimum


class HarvestContractorCosting(models.Model):
    _inherit = 'step.cosecha.tarja.line'

    harvest_min_quantity = fields.Float('Cant Mínima', compute='compute_total_trato')
    harvest_unit_price = fields.Float('Tarifa', compute='compute_total_trato')

    @api.depends('employee_id', 'quantity', 'tarifa', 'labor_id', 'uom_id', 'registry_id.date',
        'registry_id.state', 'registry_id.fundo_id', 'registry_id.especie_id',
        'registry_id.grupo_variedad_id_domain', 'registry_id.partner_id', 'registry_id.labor_id', 'registry_id.product_uom_id',
        'registry_id.pricelist_id', 'registry_id.pricelist_id.item_ids.fixed_price',
        'registry_id.pricelist_id.item_ids.min_quantity', 'registry_id.pricelist_id.item_ids.uom_id',
        'registry_id.pricelist_id.item_ids.date_start', 'registry_id.pricelist_id.item_ids.date_end',
        'registry_id.pricelist_id.item_ids.product_tmpl_id', 'registry_id.pricelist_id.item_ids.product_id',
        'registry_id.pricelist_id.item_ids.labor_id', 'registry_id.pricelist_id.item_ids.compute_price')
    def compute_total_trato(self):
        if self.env.context.get('step_harvest_native_cost_preview') and all(
                not isinstance(line.id, int) for line in self):
            super().compute_total_trato()
            for line in self:
                line.harvest_min_quantity = line.cant_minima
                line.harvest_unit_price = line.tarifa
            return
        for line in self:
            virtual = preview(line)
            virtual.trato_total
            for name in CONTRACT_OUTPUTS:
                line[name] = virtual[name]
            line.harvest_min_quantity = virtual.cant_minima
            line.harvest_unit_price = virtual.tarifa
            if line.registry_id.state != 'cont' and line.registry_id.pricelist_id.cosecha:
                item, price, minimum = line.registry_id._harvest_cost_rate(
                    virtual.labor_id, line.quantity, line.uom_id or line.registry_id.product_uom_id)
                line.harvest_min_quantity = minimum
