from odoo.tests import TransactionCase,tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import UserError

@tagged('post_install','-at_install')
class HarvestCommunityCase(TransactionCase):
    def test_no_unknown_relations_in_harvest_models(self):
        models=self.env['ir.model'].search([('model','=like','step.cosecha.%')])
        self.assertTrue(models)
        for meta in models:
            for name,field in self.env[meta.model]._fields.items():
                if field.relational:
                    self.assertNotEqual(field.comodel_name,'_unknown',(meta.model,name))
                    self.assertIn(field.comodel_name,self.env.registry.models)

    def test_preserve_custom_sequence_parameters_on_repeated_upgrade_protection(self):
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('harvest_pre',Path(__file__).parents[1]/'migrations/18.0.1.8.0/pre-migration.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        seq=self.env.ref('step_cosecha.seq_step_cosecha_propio')
        seq.write({'prefix':'PRIVATE/','padding':9,'number_increment':3})
        before=seq.read(['prefix','padding','number_increment','number_next','company_id'])
        migration.migrate(self.env.cr,'18.0.1.6.1');migration.migrate(self.env.cr,'18.0.1.6.1')
        seq.invalidate_recordset()
        self.assertEqual(seq.read(['prefix','padding','number_increment','number_next','company_id']),before)
        data=self.env['ir.model.data'].search([('module','=','step_cosecha'),('name','=','seq_step_cosecha_propio')])
        self.assertTrue(data.noupdate)

    def test_portal_denied_and_posted_harvest_guard(self):
        portal=new_test_user(self.env,login='private_harvest_portal',groups='base.group_portal')
        for model in ('step.cosecha.registry','step.cosecha.registry.line','step.history.cosecha'):
            self.assertFalse(self.env[model].with_user(portal).has_access('read'))
        harvest=self.env['step.cosecha.registry'].with_context(default_type_tarea='contratista').create({'name':'Private protected harvest','product_uom_id':self.env.ref('uom.product_uom_kgm').id})
        harvest.write({'state':'cont'})
        with self.assertRaises(UserError):harvest.unlink()

    def test_original_warehouse_marker_and_receipt_workflow(self):
        from odoo.addons.step_cosecha.hooks import pre_init_hook,post_init_hook
        self.assertEqual(self.env.ref('step_hr.field_stock_picking__cosecha'),
                         self.env.ref('step_cosecha.field_stock_picking__cosecha'))
        pre_init_hook(self.env);post_init_hook(self.env)
        company=self.env['res.company'].create({'name':'Private harvest receipt company'})
        scoped=self.env(context=dict(self.env.context,allowed_company_ids=company.ids))
        warehouse=(scoped['stock.warehouse'].search([('company_id','=',company.id)],limit=1) or
            scoped['stock.warehouse'].create({'name':'Private harvest warehouse','code':'HQA','company_id':company.id}))
        partner=scoped['res.partner'].create({'name':'Private harvest contractor'})
        kg=scoped.ref('uom.product_uom_kgm')
        product=scoped['product.product'].create({'name':'Private harvest fruit','grupo_labor':'pack','type':'consu','uom_id':kg.id,'uom_po_id':kg.id})
        operator=new_test_user(scoped,login='private_harvest_receipt_operator',
            groups='base.group_user,hr.group_hr_user,stock.group_stock_user',
            company_id=company.id,company_ids=[(6,0,company.ids)])
        harvest=scoped['step.cosecha.registry'].with_user(operator).with_context(default_type_tarea='contratista').create({
            'name':'Private warehouse harvest','company_id':company.id,'partner_id':partner.id,
            'product_id':product.product_tmpl_id.id,'product_uom_id':kg.id,
            'tarja_registry_line':[(0,0,{'qty_kg':20})]})
        harvest.recibir_cosecha()
        picking=harvest.reception_picking_id
        self.assertTrue(picking.cosecha)
        self.assertEqual(picking.harvest_registry_id,harvest)
        self.assertEqual(picking.company_id,company)
        self.assertEqual(picking.move_ids.product_id,product)
        self.assertEqual(picking.move_ids.product_uom_qty,20)
        self.assertEqual(harvest.total_kilos,20)
        self.assertFalse(harvest.env.su)
        self.assertEqual(picking.location_dest_id,warehouse.in_type_id.default_location_dest_id)
        with self.assertRaises(UserError):harvest.recibir_cosecha()
        picking.action_confirm()
        for move in picking.move_ids:move.quantity=move.product_uom_qty
        picking.button_validate()
        self.assertEqual(picking.state,'done')
        self.assertTrue(harvest.cos_recibida)

    def test_contractor_costing_uses_native_analytic_links_and_balances(self):
        company=self.env['res.company'].create({'name':'Private harvest accounting company'})
        scoped=self.env(context=dict(self.env.context,allowed_company_ids=company.ids))
        Account=scoped['account.account']
        liability=Account.create({'name':'Private harvest liability','code':'989900',
            'account_type':'liability_current','company_ids':[(6,0,company.ids)]})
        expense=Account.create({'name':'Private harvest expense','code':'989901',
            'account_type':'expense','company_ids':[(6,0,company.ids)]})
        journal=scoped['account.journal'].create({'name':'Private harvest costing','code':'HQA',
            'type':'general','company_id':company.id,'default_account_id':expense.id,
            'account_control_ids':[(6,0,(liability+expense).ids)]})
        company.step_cosecha_journal_id=journal
        accounts=[]
        for label in ('Season','Center','Activity'):
            plan=scoped['account.analytic.plan'].create({'name':'Private harvest '+label})
            accounts.append(scoped['account.analytic.account'].create({'name':'Private harvest '+label,
                'plan_id':plan.id,'company_id':company.id}))
        season,center,activity=accounts
        scoped['step.temporada'].create({'name':'Private harvest season','start_date':'2098-01-01',
            'end_date':'2098-12-31','company_id':company.id,'cost_id':season.id})
        labor=scoped['product.template'].create({'name':'Private harvest labor','is_labor':True,
            'grupo_labor':'cosecha','actividad_id':activity.id})
        partner=scoped['res.partner'].create({'name':'Private harvest accounting contractor'})
        operator=new_test_user(scoped,login='private_harvest_accounting_operator',
            groups='base.group_user,hr.group_hr_user,account.group_account_manager',
            company_id=company.id,company_ids=[(6,0,company.ids)])
        harvest=scoped['step.cosecha.registry'].with_user(operator).with_context(default_type_tarea='contratista').create({
            'name':'Private costed harvest','date':'2098-06-01','company_id':company.id,
            'partner_id':partner.id,'cost_id':center.id,'labor_id':labor.id,
            'product_uom_id':scoped.ref('uom.product_uom_kgm').id,
            'registry_tarja_line':[(0,0,{'quantity':3,'tarifa':20})]})
        self.assertFalse(harvest.env.su)
        self.assertEqual(harvest.registry_tarja_line.trato_total,60)
        harvest.action_apro();harvest.action_costeo();harvest.action_conta()
        move=harvest.invoice_id
        self.assertEqual(harvest.state,'cont');self.assertEqual(move.state,'draft')
        self.assertEqual(sum(move.line_ids.mapped('debit')),60)
        self.assertEqual(sum(move.line_ids.mapped('credit')),60)
        debit=move.line_ids.filtered(lambda line:line.debit)
        self.assertEqual(debit.account_id,expense)
        self.assertEqual(move.line_ids.filtered(lambda line:line.credit).account_id,liability)
        self.assertEqual(debit.analytic_distribution,{','.join(str(a.id) for a in accounts):100})
        self.assertEqual(harvest.cost_id,center);self.assertEqual(harvest.labor_id.actividad_id,activity)
        with self.assertRaises(UserError):harvest.action_conta()
        self.assertEqual(harvest.invoice_id,move)
