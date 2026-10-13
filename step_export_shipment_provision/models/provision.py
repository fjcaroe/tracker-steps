"""T79: reviewed shipment expenses, frozen daily valuation and balanced entry."""
from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError

_TRANSITION = object()


class Shipment(models.Model):
    _inherit = 'step.export.export'

    provision_analytic_account_id = fields.Many2one('account.analytic.account', string='Cuenta analítica del embarque', check_company=True,
        help='Cuenta del maestro analítico existente para este embarque; no se infiere por nombre.')


class Provision(models.Model):
    _name = 'step.export.shipment.provision'
    _description = 'Provisión gastos de embarques'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    _order = 'date desc, id desc'

    name = fields.Char(string='Número', required=True, default='Nuevo', copy=False, readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company)
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    state = fields.Selection([('created','Creado'),('validated','Validado'),('costed','Costeado'),('posted','Contabilizado')], required=True, default='created', readonly=True, copy=False, tracking=True)
    season_id = fields.Many2one('step.temporada', string='Temporada', required=True, check_company=True)
    program_id = fields.Many2one('step.export.sales.program', string='Programa', required=True, check_company=True)
    receiver_id = fields.Many2one(related='program_id.partner_id', string='Recibidor')
    species_id = fields.Many2one(related='program_id.species_id', string='Especie')
    shipment_id = fields.Many2one('step.export.export', string='Embarque', required=True, check_company=True)
    shipment_date = fields.Date(related='shipment_id.departure_date', string='Fecha de embarque')
    transport_type = fields.Selection(related='shipment_id.transport_type', string='Tipo transporte')
    journal_id = fields.Many2one('account.journal', string='Diario de provisión', required=True, check_company=True, domain="[('type','=','general'),('company_id','=',company_id)]")
    credit_account_id = fields.Many2one('account.account', string='Cuenta de provisión aplicada', readonly=True, copy=False)
    analytic_distribution = fields.Json(string='Distribución analítica aplicada', readonly=True, copy=False)
    currency_id = fields.Many2one(related='company_id.currency_id')
    clp_currency_id = fields.Many2one('res.currency', default=lambda self:self.env.ref('base.CLP'), required=True)
    usd_currency_id = fields.Many2one('res.currency', default=lambda self:self.env.ref('base.USD'), required=True)
    line_ids = fields.One2many('step.export.shipment.provision.line', 'provision_id', string='Gastos', copy=True)
    amount_clp = fields.Monetary(string='Total CLP', currency_field='clp_currency_id', compute='_compute_totals')
    amount_usd = fields.Monetary(string='Total USD', currency_field='usd_currency_id', compute='_compute_totals')
    move_id = fields.Many2one('account.move', string='Asiento contable', readonly=True, copy=False, ondelete='restrict')

    _sql_constraints=[('provision_move_unique','unique(move_id)','El asiento ya está asociado a otra provisión.')]

    @api.depends('line_ids.amount_clp','line_ids.amount_usd')
    def _compute_totals(self):
        for record in self:
            record.amount_clp=sum(record.line_ids.mapped('amount_clp'))
            record.amount_usd=sum(record.line_ids.mapped('amount_usd'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('state','created')!='created' or any(vals.get(n) for n in ('move_id','credit_account_id','analytic_distribution')):
                raise UserError(_('Use las acciones del formulario para validar, costear y contabilizar.'))
            if vals.get('name','Nuevo')=='Nuevo':
                vals['name']=self.env['ir.sequence'].next_by_code('step.export.shipment.provision') or 'Nuevo'
        return super().create(vals_list)

    def _lock(self):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_export_shipment_provision WHERE id IN %s ORDER BY id FOR UPDATE',[tuple(sorted(self.ids))])
            self.invalidate_recordset()

    def write(self, vals):
        if self.env.context.get('_shipment_provision_transition') is not _TRANSITION:
            if {'state','move_id','credit_account_id','analytic_distribution'}.intersection(vals):
                raise UserError(_('Use las acciones de provisión.'))
            if set(vals).intersection({'name','company_id','date','season_id','program_id','shipment_id','journal_id','line_ids','clp_currency_id','usd_currency_id'}) and any(r.state!='created' for r in self):
                raise UserError(_('Los datos validados de la provisión quedan conservados.'))
        return super().write(vals)

    def unlink(self):
        if any(r.state!='created' for r in self):
            raise UserError(_('Solo se pueden eliminar provisiones creadas.'))
        return super().unlink()

    def _check_sources(self):
        self.ensure_one()
        if self.program_id.season_id != self.season_id or self.shipment_id.sales_program_id != self.program_id or self.shipment_id.season_id != self.season_id or self.shipment_id.species_id != self.species_id or self.shipment_id.receiver_id != self.receiver_id:
            raise ValidationError(_('El embarque debe coincidir con programa, temporada, especie y recibidor.'))
        if self.program_id.company_id!=self.company_id or self.shipment_id.company_id!=self.company_id or self.journal_id.company_id!=self.company_id or self.journal_id.type!='general':
            raise ValidationError(_('Use programa, embarque y diario general de la misma empresa.'))
        if not self.line_ids:
            raise ValidationError(_('Ingrese al menos un gasto.'))
        for line in self.line_ids:
            if line.amount_currency<=0:
                raise ValidationError(_('Los gastos deben tener importe mayor a cero.'))
            if line.document_type_id.country_id and line.vendor_id.country_id and line.document_type_id.country_id!=line.vendor_id.country_id:
                raise ValidationError(_('El tipo de documento debe corresponder al país del proveedor.'))

    def action_validate(self):
        self._lock()
        for record in self:
            if record.state!='created':raise UserError(_('Solo puede validar una provisión creada.'))
            record._check_sources()
            record.with_context(_shipment_provision_transition=_TRANSITION).write({'state':'validated'})
        return True

    def _get_analytics(self):
        accounts=self.season_id.cost_id | self.species_id.cost_id | self.shipment_id.provision_analytic_account_id
        if not self.season_id.cost_id or not self.species_id.cost_id or not self.shipment_id.provision_analytic_account_id:
            raise ValidationError(_('Configure las cuentas analíticas de temporada, especie y embarque en sus maestros.'))
        if len(accounts)!=3 or len(accounts.mapped('root_plan_id'))!=3:
            raise ValidationError(_('Temporada, especie y embarque deben tener cuentas de tres planes analíticos distintos.'))
        if any(not a.active or a.company_id and a.company_id!=self.company_id for a in accounts):
            raise ValidationError(_('Las cuentas analíticas deben estar activas y pertenecer a esta empresa o ser compartidas.'))
        return {','.join(str(i) for i in sorted(accounts.ids)):100.0}

    def action_cost(self):
        self._lock()
        with self.env.cr.savepoint():
            for record in self:
                if record.state!='validated':raise UserError(_('Valide los gastos antes de costear.'))
                record._check_sources()
                credit=record.journal_id.default_account_id
                if not credit or credit.deprecated or record.company_id not in credit.company_ids:
                    raise ValidationError(_('Configure una cuenta de provisión activa en el diario general.'))
                distribution=record._get_analytics()
                for line in record.line_ids:
                    product=line.product_id.with_company(record.company_id)
                    debit=product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
                    if not debit or debit.deprecated or record.company_id not in debit.company_ids or debit==credit:
                        raise ValidationError(_('Configure la cuenta de gasto en el producto o su categoría; debe diferir de la provisión.'))
                    for currency in line.currency_id | record.clp_currency_id | record.usd_currency_id:
                        if currency!=record.currency_id and not self.env['res.currency.rate'].search_count([('currency_id','=',currency.id),('name','<=',record.date),'|',('company_id','=',record.company_id.id),('company_id','=',False)]):
                            raise ValidationError(_('Falta tipo de cambio diario de %(currency)s para la fecha del documento.',currency=currency.name))
                    amounts={n:line.currency_id._convert(line.amount_currency,c,record.company_id,record.date)
                        for n,c in (('amount_clp',record.clp_currency_id),('amount_usd',record.usd_currency_id),('amount_company',record.currency_id))}
                    if record.currency_id.is_zero(amounts['amount_company']):
                        raise ValidationError(_('El gasto resulta cero en la moneda contable.'))
                    line.with_context(_shipment_provision_transition=_TRANSITION).write(dict(amounts,expense_account_id=debit.id))
                record.with_context(_shipment_provision_transition=_TRANSITION).write({'credit_account_id':credit.id,'analytic_distribution':distribution,'state':'costed'})
        return True

    def action_account(self):
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La contabilización requiere permisos de Contabilidad.'))
        self._lock()
        with self.env.cr.savepoint():
            for record in self:
                if record.state=='posted':
                    if record.move_id.state!='posted':raise UserError(_('El asiento de provisión debe permanecer publicado.'))
                    continue
                if record.state!='costed' or record.move_id:raise UserError(_('Costee la provisión antes de contabilizar.'))
                values=[]
                for line in record.line_ids:
                    label='%s / %s / %s' % (record.name,line.product_id.display_name,line.document_number)
                    for account,sign in ((line.expense_account_id,1),(record.credit_account_id,-1)):
                        balance=sign*line.amount_company
                        values.append(Command.create({'name':label,'account_id':account.id,'partner_id':line.vendor_id.id,
                            'debit':max(balance,0),'credit':max(-balance,0),'currency_id':line.currency_id.id,
                            'amount_currency':sign*(line.amount_company if line.currency_id==record.currency_id else line.amount_currency),
                            'analytic_distribution':record.analytic_distribution if sign==1 else False}))
                move=self.env['account.move'].with_company(record.company_id).with_context(_shipment_provision_transition=_TRANSITION).create({
                    'move_type':'entry','company_id':record.company_id.id,'journal_id':record.journal_id.id,'date':record.date,
                    'ref':record.name,'shipment_provision_id':record.id,'line_ids':values})
                move.action_post()
                record.with_context(_shipment_provision_transition=_TRANSITION).write({'move_id':move.id,'state':'posted'})
        return True


class ProvisionLine(models.Model):
    _name='step.export.shipment.provision.line'
    _description='Gasto provisionado de embarque'
    _check_company_auto=True

    provision_id=fields.Many2one('step.export.shipment.provision',required=True,ondelete='cascade',index=True)
    company_id=fields.Many2one(related='provision_id.company_id',store=True)
    grower_item_id=fields.Many2one('step.export.grower.discount',string='Ítem productor',required=True,check_company=True)
    product_id=fields.Many2one('product.product',string='Concepto gasto',required=True,check_company=True)
    vendor_id=fields.Many2one('res.partner',string='Proveedor',required=True,check_company=True)
    document_type_id=fields.Many2one('l10n_latam.document.type',string='Tipo documento',required=True)
    document_number=fields.Char(string='Número documento',required=True)
    currency_id=fields.Many2one('res.currency',string='Moneda',required=True,default=lambda self:self.env.company.currency_id)
    amount_currency=fields.Monetary(string='Monto',required=True)
    company_currency_id=fields.Many2one(related='provision_id.currency_id')
    clp_currency_id=fields.Many2one(related='provision_id.clp_currency_id')
    usd_currency_id=fields.Many2one(related='provision_id.usd_currency_id')
    amount_company=fields.Monetary(currency_field='company_currency_id',readonly=True,copy=False)
    amount_clp=fields.Monetary(string='Monto CLP',currency_field='clp_currency_id',readonly=True,copy=False)
    amount_usd=fields.Monetary(string='Monto USD',currency_field='usd_currency_id',readonly=True,copy=False)
    expense_account_id=fields.Many2one('account.account',string='Cuenta de gasto aplicada',readonly=True,copy=False)

    def _check_edit(self):
        if any(r.provision_id.state!='created' for r in self):raise UserError(_('Los gastos validados quedan conservados.'))

    @api.model_create_multi
    def create(self,vals_list):
        parents=self.env['step.export.shipment.provision'].browse([v['provision_id'] for v in vals_list if v.get('provision_id')])
        if any(r.state!='created' for r in parents) or any(set(v).intersection({'amount_company','amount_clp','amount_usd','expense_account_id'}) for v in vals_list):
            raise UserError(_('Ingrese los gastos en una provisión creada.'))
        return super().create(vals_list)

    def write(self,vals):
        if self.env.context.get('_shipment_provision_transition') is not _TRANSITION:
            self._check_edit()
            if set(vals).intersection({'amount_company','amount_clp','amount_usd','expense_account_id'}):raise UserError(_('Use Costear para calcular los importes.'))
            if vals.get('provision_id') and self.env['step.export.shipment.provision'].browse(vals['provision_id']).state!='created':raise UserError(_('Use una provisión creada.'))
        return super().write(vals)

    def unlink(self):
        self._check_edit()
        return super().unlink()


class AccountMove(models.Model):
    _inherit='account.move'
    shipment_provision_id=fields.Many2one('step.export.shipment.provision',readonly=True,copy=False,ondelete='restrict')
    _sql_constraints=[('shipment_provision_unique','unique(shipment_provision_id)','La provisión ya tiene un asiento.')]

    @api.model_create_multi
    def create(self,vals_list):
        if any(v.get('shipment_provision_id') for v in vals_list) and self.env.context.get('_shipment_provision_transition') is not _TRANSITION:
            raise UserError(_('El asiento se genera desde la provisión costeada.'))
        return super().create(vals_list)

    def write(self,vals):
        if 'shipment_provision_id' in vals and self.env.context.get('_shipment_provision_transition') is not _TRANSITION:raise UserError(_('El asiento conserva su provisión de origen.'))
        return super().write(vals)

    def button_draft(self):
        if self.shipment_provision_id:raise UserError(_('La provisión contabilizada conserva su asiento publicado.'))
        return super().button_draft()

    def button_cancel(self):
        if self.shipment_provision_id:raise UserError(_('La provisión contabilizada conserva su asiento publicado.'))
        return super().button_cancel()
