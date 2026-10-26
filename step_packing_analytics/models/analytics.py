from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_ORIGIN=object()


def root_plan(plan):
    while plan.parent_id:
        plan = plan.parent_id
    return plan


class Rule(models.Model):
    _name = 'step.packing.analytic.rule'
    _description = 'Aplicación de planes analíticos a Packing'
    _check_company_auto = True
    _rec_name = 'plan_id'
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company)
    plan_id = fields.Many2one('account.analytic.plan', required=True, ondelete='restrict')
    apply = fields.Boolean('Aplicar Packing')
    origin = fields.Selection([('season','Temporada de la OT'),('species','Especie de la OT'),('ot','Número de OT')], string='Origen de la cuenta')
    _sql_constraints = [('company_plan_unique','unique(company_id,plan_id)','El plan ya está configurado para esta empresa.')]

    @api.constrains('apply','origin','plan_id','company_id')
    def _check_rule(self):
        for rule in self:
            if rule.plan_id.parent_id:
                raise ValidationError(_('Seleccione un plan analítico principal.'))
            if rule.apply and not rule.origin:
                raise ValidationError(_('Indique el origen de cada plan aplicado a Packing.'))
            if rule.apply and self.search_count([('id','!=',rule.id),('company_id','=',rule.company_id.id),
                                                ('apply','=',True),('origin','=',rule.origin)]):
                raise ValidationError(_('Use un solo plan aplicado por cada origen de Packing.'))

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_('La configuración analítica requiere administración de Contabilidad.'))

    @api.model_create_multi
    def create(self, values):
        self._check_manager(); return super().create(values)

    def write(self, values):
        self._check_manager(); return super().write(values)

    def unlink(self):
        self._check_manager(); return super().unlink()


class AnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    step_packing_production_id = fields.Many2one('step.packing.production', copy=False, readonly=True, ondelete='restrict')
    step_packing_species_id = fields.Many2one('step.especie', copy=False, readonly=True, ondelete='restrict')
    step_packing_season_id = fields.Many2one('step.temporada', copy=False, readonly=True, ondelete='restrict')
    _sql_constraints = [
        ('packing_ot_plan_unique','unique(company_id,plan_id,step_packing_production_id)','La OT ya tiene cuenta en este plan.'),
        ('packing_species_plan_unique','unique(company_id,plan_id,step_packing_species_id)','La especie ya tiene cuenta en este plan.'),
        ('packing_season_plan_unique','unique(company_id,plan_id,step_packing_season_id)','La temporada ya tiene cuenta en este plan.')]


class Production(models.Model):
    _inherit = 'step.packing.production'
    step_analytic_season_id = fields.Many2one('step.temporada', string='Temporada para analítica')
    step_effective_season_id = fields.Many2one('step.temporada', compute='_compute_analytic_season', string='Temporada de la OT')
    step_analytic_distribution = fields.Json(compute='_compute_analytic_preview', string='Distribución analítica de consumos')
    step_analytic_summary = fields.Text(compute='_compute_analytic_preview', string='Cuentas analíticas de consumo')
    step_analytic_message = fields.Char(compute='_compute_analytic_preview', string='Configuración analítica')
    step_analytic_reclassification_ids = fields.One2many('account.move','step_packing_reclassification_ot_id', string='Reclasificaciones')

    @api.depends('step_analytic_season_id','step_packing_input_tag_ids.step_export_season_id')
    def _compute_analytic_season(self):
        for ot in self:
            seasons=ot.step_packing_input_tag_ids.step_export_season_id
            ot.step_effective_season_id=ot.step_analytic_season_id or (seasons if len(seasons)==1 else False)

    @api.depends('step_analytic_season_id','step_packing_input_tag_ids','fruit_species_id')
    def _compute_analytic_preview(self):
        for ot in self:
            try:
                ot.step_analytic_distribution=ot._packing_distribution(create=False)
                ids={int(value) for key in (ot.step_analytic_distribution or {}) for value in key.split(',') if value}
                accounts=ot.env['account.analytic.account'].sudo().browse(list(ids)).exists()
                ot.step_analytic_summary='; '.join('%s: %s'%(a.plan_id.display_name,a.name) for a in accounts)
                ot.step_analytic_message=_('Se completa al generar el comprobante de consumo.')
            except UserError as exc:
                ot.step_analytic_distribution=False; ot.step_analytic_summary=False; ot.step_analytic_message=str(exc)

    def _packing_distribution(self, create=False, existing=None):
        self.ensure_one()
        rules=self.env['step.packing.analytic.rule'].sudo().search([('company_id','=',self.company_id.id),('apply','=',True)])
        if not rules:return existing or {}
        chosen={}
        # Both concurrent consumptions and native accounting preparation reuse
        # one account per source, company and plan, without changing masters.
        if create:self.env.cr.execute('SELECT id FROM step_packing_production WHERE id=%s FOR UPDATE',[self.id])
        for rule in rules.sorted('id'):
            species=self.fruit_species_id or (self.step_packing_input_tag_ids.especie_id if len(self.step_packing_input_tag_ids.especie_id)==1 else self.env['step.especie'])
            source=self if rule.origin=='ot' else self.step_effective_season_id if rule.origin=='season' else species
            if not source:
                raise UserError(_('Falta %(origin)s para el plan %(plan)s de Packing.') % {'origin':dict(rule._fields['origin'].selection)[rule.origin],'plan':rule.plan_id.display_name})
            if rule.origin=='season' and source.company_ids and self.company_id not in source.company_ids:
                raise UserError(_('La temporada no está habilitada para la empresa de la OT.'))
            linked_field={'ot':'step_packing_production_id','species':'step_packing_species_id','season':'step_packing_season_id'}[rule.origin]
            accounts=self.env['account.analytic.account'].sudo().with_company(self.company_id).with_context(active_test=False)
            preferred=source.sudo().cost_id if rule.origin!='ot' else accounts.browse()
            if preferred and preferred.company_id in (self.company_id,self.env['res.company']) and root_plan(preferred.plan_id)==rule.plan_id:
                account=preferred
            else:
                if create:
                    self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',[
                        'packing-analytic:%s:%s:%s:%s'%(self.company_id.id,rule.plan_id.id,rule.origin,source.id)])
                account=accounts.search([('company_id','=',self.company_id.id),('plan_id','=',rule.plan_id.id),(linked_field,'=',source.id)])
                if not account and rule.origin!='ot':
                    account=accounts.search([('company_id','in',[False,self.company_id.id]),('plan_id','=',rule.plan_id.id),('name','=',source.name)])
                if len(account)>1:raise UserError(_('Hay cuentas analíticas ambiguas para %s; revise el maestro.')%source.display_name)
                if not account and create:
                    account=accounts.create({'name':source.name,'plan_id':rule.plan_id.id,'company_id':self.company_id.id,linked_field:source.id})
            if account and not account.active:
                raise UserError(_('La cuenta analítica %s está archivada; reactive el registro existente.')%account.display_name)
            if account:chosen[rule.plan_id.id]=account.id
        if not chosen:return existing or {}
        result={}
        for key,percent in (existing or {'':100.0}).items():
            ids={int(value) for value in key.split(',') if value}
            for account in self.env['account.analytic.account'].sudo().browse(list(ids)).exists():
                plan=root_plan(account.plan_id)
                if account.company_id and account.company_id!=self.company_id:
                    raise UserError(_('La distribución contiene una cuenta de otra empresa.'))
                if plan.id in chosen and account.id!=chosen[plan.id]:
                    raise UserError(_('La distribución existente contradice el origen automático del plan %s.')%plan.display_name)
            ids.update(chosen.values()); combined=','.join(map(str,sorted(ids)))
            result[combined]=result.get(combined,0)+percent
        return result

    def _packing_move_extra_values(self, product, qty, source, dest, lines):
        values=super()._packing_move_extra_values(product,qty,source,dest,lines)
        values['step_analytic_production_id']=self.id
        values['step_packing_consumption']=source.usage=='internal' and dest.usage=='production'
        return values

    def _create_packing_move(self,warehouse,source,dest,lines):
        return super(Production,self.with_context(_packing_analytic_origin=_ORIGIN))._create_packing_move(warehouse,source,dest,lines)

    def action_apply_packing_analytics(self):
        if not self.env.user.has_group('account.group_account_user') or not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(_('La revisión de comprobantes requiere Contabilidad y administración de Inventario.'))
        self._lock_process()
        with self.env.cr.savepoint():
            for ot in self:
                if ot.state not in ('closed','costed','accounted'):
                    raise UserError(_('Cierre la OT antes de revisar sus comprobantes existentes.'))
                distribution=ot._packing_distribution(create=True)
                moves=ot.input_picking_id.move_ids | ot.material_picking_id.move_ids
                for move in moves:
                    expense=move.with_company(ot.company_id).product_id.product_tmpl_id.get_product_accounts().get('expense')
                    entries=move.stock_valuation_layer_ids.account_move_id.filtered(lambda entry:entry.state=='posted')
                    for entry in entries:
                        lines=entry.line_ids.filtered(lambda line:line.debit>0 and line.product_id==move.product_id)
                        for line in lines:
                            merged=ot._packing_distribution(create=True,existing=line.analytic_distribution)
                            if line.account_id==expense:
                                if line.analytic_distribution!=merged:line.analytic_distribution=merged
                            else:
                                if not expense:raise UserError(_('Configure la cuenta de gasto del producto %s.')%move.product_id.display_name)
                                correction=self.env['account.move'].search([('step_packing_reclassification_source_id','=',line.id)])
                                if not correction:
                                    self.env['account.move'].create({'move_type':'entry','company_id':ot.company_id.id,
                                        'journal_id':entry.journal_id.id,'date':fields.Date.context_today(ot),
                                        'ref':_('Reclasificación Packing %s')%ot.name,
                                        'step_packing_reclassification_ot_id':ot.id,'step_packing_reclassification_source_id':line.id,
                                        'line_ids':[(0,0,{'name':line.name,'product_id':line.product_id.id,'account_id':expense.id,
                                            'debit':line.debit,'credit':0,'analytic_distribution':merged}),
                                            (0,0,{'name':line.name,'product_id':line.product_id.id,'account_id':line.account_id.id,
                                            'debit':0,'credit':line.debit})]})
            return {'type':'ir.actions.act_window','name':_('Reclasificaciones Packing'), 'res_model':'account.move',
                    'view_mode':'list,form','domain':[('step_packing_reclassification_ot_id','in',self.ids)]}


class Move(models.Model):
    _inherit='stock.move'
    step_analytic_production_id=fields.Many2one('step.packing.production',copy=False,readonly=True,check_company=True,index=True)
    step_packing_consumption=fields.Boolean(copy=False,readonly=True)

    @api.model_create_multi
    def create(self,values):
        if not self.env.su and self.env.context.get('_packing_analytic_origin') is not _ORIGIN and any(row.get('step_analytic_production_id') for row in values):
            raise AccessError(_('El vínculo contable con la OT se genera desde el flujo de Packing.'))
        return super().create(values)

    def write(self,values):
        if not self.env.su and self.env.context.get('_packing_analytic_origin') is not _ORIGIN and {'step_analytic_production_id','step_packing_consumption'}&values.keys():
            raise AccessError(_('El vínculo contable con la OT se genera desde el flujo de Packing.'))
        return super().write(values)

    def _get_dest_account(self, accounts_data):
        if self.step_analytic_production_id and self.step_packing_consumption:
            expense=accounts_data.get('expense')
            if not expense:raise UserError(_('Configure la cuenta de gasto del producto o categoría: %s.')%self.product_id.display_name)
            return expense.id
        return super()._get_dest_account(accounts_data)

    def _packing_return_expense_lines(self):
        self.ensure_one()
        original=self.origin_returned_move_id
        if not original.step_analytic_production_id or not original.step_packing_consumption:
            return self.env['account.move.line']
        if original.company_id!=self.company_id:
            raise UserError(_('La devolución y el consumo original pertenecen a empresas distintas.'))
        return original.sudo().stock_valuation_layer_ids.account_move_id.line_ids.filtered(
            lambda line:line.product_id==self.product_id and line.debit>0)

    def _get_src_account(self, accounts_data):
        if self.location_id.usage=='production' and self.location_dest_id.usage=='internal':
            lines=self._packing_return_expense_lines()
            if lines:
                if len(lines.account_id)!=1:raise UserError(_('Revise las cuentas del consumo original antes de devolverlo.'))
                return lines.account_id.id
        return super()._get_src_account(accounts_data)

    def _prepare_account_move_line(self,qty,cost,credit_account_id,debit_account_id,svl_id,description):
        values=super()._prepare_account_move_line(qty,cost,credit_account_id,debit_account_id,svl_id,description)
        if self.step_analytic_production_id and self.step_packing_consumption:
            distribution=self.step_analytic_production_id._packing_distribution(create=True,existing=self.analytic_distribution)
            for command in values:
                line=command[2]
                if line.get('account_id')==debit_account_id:
                    line['analytic_distribution']=distribution
        elif self.location_id.usage=='production' and self.location_dest_id.usage=='internal':
            original=self._packing_return_expense_lines()
            distributions=[line.analytic_distribution for line in original if line.analytic_distribution]
            if distributions:
                if any(value!=distributions[0] for value in distributions):
                    raise UserError(_('Revise la distribución del consumo original antes de devolverlo.'))
                for command in values:
                    if command[2].get('account_id')==credit_account_id:
                        command[2]['analytic_distribution']=distributions[0]
        return values


class AccountMove(models.Model):
    _inherit='account.move'
    step_packing_reclassification_ot_id=fields.Many2one('step.packing.production',copy=False,readonly=True,check_company=True)
    step_packing_reclassification_source_id=fields.Many2one('account.move.line',copy=False,readonly=True,ondelete='restrict',check_company=True)
    _sql_constraints=[('packing_reclassification_source_unique','unique(step_packing_reclassification_source_id)','El apunte ya tiene una reclasificación Packing.')]
