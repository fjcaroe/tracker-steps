"""T91 links native instructions, fruit packages, dispatch guides and packing lists."""
import math
import re
from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_compare


class Instruction(models.Model):
    _inherit = 'step.export.dispatch.order'
    _check_company_auto = True
    shipment_id = fields.Many2one('step.export.export', string='Embarque', check_company=True, ondelete='restrict')
    date = fields.Date(string='Fecha', default=fields.Date.context_today)
    season_id = fields.Many2one(related='shipment_id.season_id', string='Temporada')
    species_id = fields.Many2one(related='shipment_id.species_id', string='Especie')
    vessel_id = fields.Many2one(related='shipment_id.vessel_id', string='Nave')
    receiver_id = fields.Many2one(related='shipment_id.receiver_id', string='Recibidor')
    transport_type = fields.Selection(related='shipment_id.transport_type', string='Tipo embarque')
    port_id = fields.Many2one(related='shipment_id.origin_port_id', string='Puerto embarque')
    load_line_ids = fields.One2many('step.export.dispatch.load', 'instruction_id', string='Carga solicitada', copy=True)
    pallets_per_truck = fields.Integer(string='Pallets por camión', default=20)
    pallet_qty = fields.Integer(compute='_totals', string='Pallets')
    box_qty = fields.Float(compute='_totals', string='Cajas')
    kg_qty = fields.Float(compute='_totals', string='Kilos')
    truck_qty = fields.Integer(compute='_totals', string='Cantidad camiones')
    guide_ids = fields.One2many('step.dispatch.guide', 'dispatch_instruction_id', string='Guías de despacho')

    @api.depends('load_line_ids.pallet_qty', 'load_line_ids.box_qty', 'load_line_ids.kg_qty', 'pallets_per_truck')
    def _totals(self):
        for r in self:
            r.pallet_qty = sum(r.load_line_ids.mapped('pallet_qty'))
            r.box_qty = sum(r.load_line_ids.mapped('box_qty'))
            r.kg_qty = sum(r.load_line_ids.mapped('kg_qty'))
            r.truck_qty = math.ceil(r.pallet_qty/r.pallets_per_truck) if r.pallets_per_truck else 0

    @api.constrains('pallets_per_truck', 'shipment_id', 'company_id')
    def _check_instruction(self):
        for r in self:
            if r.pallets_per_truck <= 0:
                raise ValidationError(_('Pallets por camión debe ser positivo.'))
            if r.shipment_id and r.shipment_id.company_id != r.company_id:
                raise ValidationError(_('El instructivo y el embarque deben ser de la misma empresa.'))

    def _check_editable(self):
        if self:
            self.env.cr.execute('SELECT id FROM step_export_dispatch_order WHERE id IN %s ORDER BY id FOR UPDATE',[tuple(sorted(self.ids))])
        if self.env['step.dispatch.guide'].search_count([('dispatch_instruction_id','in',self.ids),('state','!=','cancelled')]):
            raise UserError(_('El instructivo ya tiene una guía vigente; conserve sus filtros.'))

    def write(self, vals):
        if {'shipment_id','company_id','load_line_ids','pallets_per_truck'} & vals.keys():
            self._check_editable()
        return super().write(vals)

    def action_import_shipment_load(self):
        self.ensure_one(); self.check_access('write'); self._check_editable()
        if self.load_line_ids:
            raise UserError(_('Ya hay carga solicitada. Se conserva; no se reemplaza automáticamente.'))
        if not self.shipment_id.line_ids:
            raise UserError(_('Seleccione un embarque con resumen de carga.'))
        values=[]
        for line in self.shipment_id.line_ids:
            if not float(line.pallet_qty).is_integer():
                raise ValidationError(_('El despacho selecciona pallets completos; revise la cantidad del embarque.'))
            values.append(Command.create({'product_id':line.product_id.id,'packaging_id':line.packaging_id.id,
                'variety_id':line.variety_id.id,'caliber_id':line.caliber_id.id,'quality_id':line.quality_id.id,
                'label':line.label,'pallet_qty':int(line.pallet_qty),'boxes_per_pallet':line.boxes_per_pallet,
                'kg_per_box':line.kg_per_box}))
        self.load_line_ids=values
        return True

    def _ready(self):
        self.ensure_one()
        if not self.shipment_id or not self.season_id or not self.species_id or not self.load_line_ids:
            raise UserError(_('Complete embarque, temporada, especie y carga solicitada.'))

    def _check_capacity(self,tags):
        """Match pallets to line capacities, including overlapping filters."""
        choices={t.id:[l.id for l in self.load_line_ids if l._matches(t,
            t.quant_ids.filtered(lambda q:q.quantity>0 and q.location_id.usage=='internal'),t._step_producer_shares())] for t in tags}
        assigned={l.id:[] for l in self.load_line_ids}
        capacity={l.id:l.pallet_qty for l in self.load_line_ids}
        def place(tag_id,seen):
            for line_id in choices[tag_id]:
                if line_id in seen:continue
                seen.add(line_id)
                if len(assigned[line_id])<capacity[line_id]:
                    assigned[line_id].append(tag_id);return True
                for index,previous in enumerate(assigned[line_id]):
                    if place(previous,seen):
                        assigned[line_id][index]=tag_id;return True
            return False
        if any(not place(t.id,set()) for t in tags):
            raise ValidationError(_('Los pallets exceden la cantidad solicitada de una combinación de filtros.'))

    def _matches(self, tag):
        self.ensure_one()
        if (not tag.is_fruit_tag or tag.step_tag_kind != 'E' or tag.step_tag_state != 'validated'
                or tag.company_id != self.company_id or tag.especie_id != self.species_id
                or tag.step_export_season_id != self.season_id):
            return False
        quants=tag.quant_ids.filtered(lambda q:q.quantity>0 and q.location_id.usage=='internal')
        if not quants or any(q.reserved_quantity for q in quants):
            return False
        program=self.shipment_id.sales_program_id
        producers=tag._step_producer_shares()
        if tag.variedad_id in program.forbidden_variety_ids or any(p in program.forbidden_producer_ids for p,_ in producers):
            return False
        return any(line._matches(tag,quants,producers) for line in self.load_line_ids)

    def action_create_guide(self):
        self.ensure_one();self._ready()
        return {'type':'ir.actions.act_window','name':_('Crear guía de despacho'),'res_model':'step.dispatch.guide',
            'view_mode':'form','target':'current','context':{'default_dispatch_instruction_id':self.id,
            'default_step_export_shipment_id':self.shipment_id.id,'default_company_id':self.company_id.id,
            'default_partner_id':self.receiver_id.id}}


class Load(models.Model):
    _name = 'step.export.dispatch.load'
    _description = 'Carga solicitada en instructivo de despacho'
    _check_company_auto = True
    instruction_id=fields.Many2one('step.export.dispatch.order',required=True,ondelete='cascade')
    company_id=fields.Many2one(related='instruction_id.company_id',store=True)
    product_id=fields.Many2one('product.product',required=True,string='Producto',check_company=True)
    packaging_id=fields.Many2one('product.packaging',string='Embalaje',check_company=True)
    producer_id=fields.Many2one('res.partner',string='Productor',check_company=True,domain=[('is_productor','=',True)])
    variety_id=fields.Many2one('step.variedad',string='Variedad')
    label=fields.Char(string='Marca')
    caliber_id=fields.Many2one('step.management.fruit.caliber',string='Calibre')
    quality_id=fields.Many2one('step.management.fruit.quality',string='Calidad')
    pallet_qty=fields.Integer(string='Pallets',required=True,default=1)
    boxes_per_pallet=fields.Float(string='Cajas por pallet',required=True)
    kg_per_box=fields.Float(string='Kg por caja',required=True)
    box_qty=fields.Float(compute='_totals',string='Cajas')
    kg_qty=fields.Float(compute='_totals',string='Kilos')

    @api.depends('pallet_qty','boxes_per_pallet','kg_per_box')
    def _totals(self):
        for r in self:r.box_qty=r.pallet_qty*r.boxes_per_pallet;r.kg_qty=r.box_qty*r.kg_per_box

    @api.constrains('pallet_qty','boxes_per_pallet','kg_per_box','packaging_id','product_id')
    def _check_load(self):
        for r in self:
            if min(r.pallet_qty,r.boxes_per_pallet,r.kg_per_box)<=0:
                raise ValidationError(_('Pallets, cajas y kilos por caja deben ser positivos.'))
            if r.packaging_id and r.packaging_id.product_id != r.product_id:
                raise ValidationError(_('El embalaje debe corresponder al producto.'))

    def _matches(self,tag,quants,producers):
        return (quants.product_id==self.product_id
            and (not self.packaging_id or tag.step_packaging_id==self.packaging_id)
            and (not self.producer_id or all(p==self.producer_id for p,_ in producers))
            and (not self.variety_id or tag.variedad_id==self.variety_id)
            and (not self.label or tag.label==self.label)
            and (not self.caliber_id or tag.fruit_caliber_id==self.caliber_id)
            and (not self.quality_id or tag.fruit_quality_id==self.quality_id)
            and float_compare(tag.box_count,self.boxes_per_pallet,precision_digits=3)==0
            and float_compare(tag.step_actual_kg,tag.box_count*self.kg_per_box,precision_digits=3)==0)

    @api.model_create_multi
    def create(self,vals_list):
        self.env['step.export.dispatch.order'].browse([v['instruction_id'] for v in vals_list if v.get('instruction_id')])._check_editable()
        return super().create(vals_list)

    def write(self,vals):
        self.instruction_id._check_editable()
        if vals.get('instruction_id'):self.env['step.export.dispatch.order'].browse(vals['instruction_id'])._check_editable()
        return super().write(vals)

    def unlink(self):
        self.instruction_id._check_editable()
        return super().unlink()


class Guide(models.Model):
    _inherit='step.dispatch.guide'
    dispatch_instruction_id=fields.Many2one('step.export.dispatch.order',string='Número instructivo despacho',check_company=True,ondelete='restrict',copy=False)
    load_tag_ids=fields.Many2many('stock.quant.package',relation='step_dispatch_guide_load_tag_rel',string='Folio Pallet',copy=False)
    available_load_tag_ids=fields.Many2many('stock.quant.package',compute='_available_tags')
    scan_code=fields.Char(string='Leer o anotar folio pallet',copy=False)

    @api.depends('dispatch_instruction_id','load_tag_ids')
    def _available_tags(self):
        for g in self:
            plan=g.dispatch_instruction_id
            used=self.search([('state','!=','cancelled'),('id','!=',g._origin.id or 0)]).load_tag_ids
            candidates=self.env['stock.quant.package'].search([('is_fruit_tag','=',True),('step_tag_state','=','validated'),('company_id','=',g.company_id.id)]) if plan else self.env['stock.quant.package']
            g.available_load_tag_ids=candidates.filtered(lambda t:t not in used and plan._matches(t)) | g.load_tag_ids

    @api.onchange('dispatch_instruction_id')
    def _onchange_dispatch_instruction(self):
        if self.dispatch_instruction_id:
            self.step_export_shipment_id=self.dispatch_instruction_id.shipment_id

    @api.onchange('scan_code')
    def _scan(self):
        if not self.scan_code:return
        self.dispatch_instruction_id._ready()
        tags=self.env['stock.quant.package']
        for code in filter(None,(c.strip() for c in re.split(r'[\n,;]+',self.scan_code))):
            found=tags.search([('name','=',code),('company_id','=',self.company_id.id)])
            if len(found)!=1 or found not in self.available_load_tag_ids:
                raise UserError(_('Folio no disponible o no coincide con el instructivo: %s',code))
            tags|=found
        self.load_tag_ids|=tags
        self.scan_code=False

    def _validate_load(self):
        for g in self:
            if not g.dispatch_instruction_id:
                if g.load_tag_ids:raise ValidationError(_('Seleccione el instructivo de despacho.'))
                continue
            plan=g.dispatch_instruction_id;plan._ready()
            if g.step_export_shipment_id!=plan.shipment_id or g.company_id!=plan.company_id:
                raise ValidationError(_('La guía debe usar el mismo embarque y empresa del instructivo.'))
            if not g.load_tag_ids:continue
            self.env.cr.execute('SELECT id FROM step_export_dispatch_order WHERE id=%s FOR UPDATE',[plan.id])
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE',[tuple(sorted(g.load_tag_ids.ids))])
            g.load_tag_ids.invalidate_recordset()
            others=self.search([('id','!=',g.id),('state','!=','cancelled'),('load_tag_ids','in',g.load_tag_ids.ids)])
            if others:raise ValidationError(_('Una tarja ya está asignada a otra guía vigente.'))
            if any(not plan._matches(t) for t in g.load_tag_ids):
                raise ValidationError(_('Una tarja no está vigente, no tiene stock libre o no coincide con los filtros de carga.'))
            total=len(self.search([('dispatch_instruction_id','=',plan.id),('state','!=','cancelled')]).load_tag_ids)
            if total>plan.pallet_qty or len(g.load_tag_ids)>plan.pallets_per_truck:
                raise ValidationError(_('La carga excede los pallets solicitados o la capacidad por camión.'))
            plan._check_capacity(self.search([('dispatch_instruction_id','=',plan.id),('state','!=','cancelled')]).load_tag_ids)

    def _sync_load(self):
        for g in self.filtered('load_tag_ids'):
            shipment=g.dispatch_instruction_id.shipment_id
            missing=g.load_tag_ids-shipment.tag_ids
            if missing:shipment.write({'tag_ids':[Command.link(t.id) for t in missing]})

    @api.model_create_multi
    def create(self,vals_list):
        for v in vals_list:
            if v.get('dispatch_instruction_id'):
                plan=self.env['step.export.dispatch.order'].browse(v['dispatch_instruction_id'])
                v.setdefault('step_export_shipment_id',plan.shipment_id.id)
        records=super().create(vals_list)
        records._validate_load();records._sync_load()
        return records

    def write(self,vals):
        if {'dispatch_instruction_id','load_tag_ids','step_export_shipment_id','company_id'} & vals.keys():
            if any(g.state!='draft' for g in self) or self.env['step.export.packing.list'].search_count([('guide_id','in',self.ids)]):
                raise UserError(_('La carga de una guía confirmada o con packing list se conserva.'))
        result=super().write(vals)
        if {'dispatch_instruction_id','load_tag_ids','step_export_shipment_id','company_id','state'} & vals.keys():
            self.filtered(lambda g:g.state!='cancelled')._validate_load()
            self._sync_load()
        return result

    def action_confirm(self):
        self._validate_load()
        for g in self.filtered('dispatch_instruction_id'):
            if not g.load_tag_ids:raise UserError(_('Seleccione Folio Pallet antes de confirmar.'))
            g.dispatch_instruction_id.shipment_id._check_tag_load()
        return super().action_confirm()

    def action_create_packing_list(self):
        self.ensure_one()
        if not self.dispatch_instruction_id or not self.load_tag_ids or self.state=='cancelled':
            raise UserError(_('Seleccione una guía vigente con instructivo y tarjas.'))
        existing=self.env['step.export.packing.list'].search([('guide_id','=',self.id)])
        record=existing or self.env['step.export.packing.list'].create({'shipment_id':self.dispatch_instruction_id.shipment_id.id,'guide_id':self.id})
        return {'type':'ir.actions.act_window','res_model':record._name,'res_id':record.id,'view_mode':'form','target':'current'}

    def action_load_pallet_detail(self):
        self.ensure_one();self._validate_load()
        if self.state!='draft' or self.line_ids or not self.load_tag_ids:
            raise UserError(_('Use una guía en borrador con pallets seleccionados y detalle vacío; se conserva el detalle existente.'))
        values=[]
        for product in self.load_tag_ids.step_tag_line_ids.product_id:
            content=self.load_tag_ids.step_tag_line_ids.filtered(lambda l:l.product_id==product)
            values.append(Command.create({'product_id':product.id,'description':product.display_name,
                'product_uom_id':product.uom_id.id,'quantity':sum(content.mapped('quantity')),
                'quantity_kg':sum(content.mapped('kilos')),'price_unit':0}))
        self.line_ids=values
        return True


class PackingList(models.Model):
    _inherit='step.export.packing.list'
    guide_has_dispatch_instruction=fields.Many2one(related='guide_id.dispatch_instruction_id')

    @api.onchange('guide_id')
    def _onchange_guide_tags(self):
        if self.guide_id.dispatch_instruction_id:self.tag_ids=self.guide_id.load_tag_ids

    @api.model_create_multi
    def create(self,vals_list):
        for v in vals_list:
            guide=self.env['step.dispatch.guide'].browse(v.get('guide_id'))
            if guide.dispatch_instruction_id:
                v.setdefault('tag_ids',[Command.set(guide.load_tag_ids.ids)])
        return super().create(vals_list)

    def write(self,vals):
        if vals.get('guide_id') and 'tag_ids' not in vals:
            guide=self.env['step.dispatch.guide'].browse(vals['guide_id'])
            if guide.dispatch_instruction_id:vals=dict(vals,tag_ids=[Command.set(guide.load_tag_ids.ids)])
        return super().write(vals)

    @api.constrains('guide_id','tag_ids')
    def _check_guide_tags(self):
        for r in self:
            if r.guide_id.dispatch_instruction_id and (not r.tag_ids or r.tag_ids!=r.guide_id.load_tag_ids or r.guide_id.state=='cancelled'):
                raise ValidationError(_('El packing list debe usar exactamente los folios pallet de la guía vigente.'))
