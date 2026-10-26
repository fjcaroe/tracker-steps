from odoo.tests import TransactionCase, tagged, Form
from odoo.exceptions import UserError, ValidationError


@tagged('post_install','-at_install')
class PackingAnalyticsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env=cls.env(context=dict(cls.env.context,tracking_disable=True,mail_notrack=True,mail_notify_force_send=False,mail_create_nosubscribe=True))
        cls.company=cls.env.company
        cls.company.step_packing_require_contract=False
        cls.wh=cls.env['stock.warehouse'].search([('company_id','=',cls.company.id)],limit=1)
        cls.producer=cls.env['res.partner'].create({'name':'QA122 productor'})
        cls.species=cls.env['step.especie'].create({'name':'QA122 especie','type_especie':'frutal','group_especie':'fruta_h'})
        group=cls.env['step.grupo.variedad'].create({'name':'QA122 grupo','especie_id':cls.species.id})
        cls.variety=cls.env['step.variedad'].create({'name':'QA122 variedad','cod_variedad':'Q122',
            'especie_id':cls.species.id,'grupo_variedad_id':group.id})
        cls.season=cls.env['step.temporada'].create({'name':'QA122 temporada'})
        cls.plans={origin:cls.env['account.analytic.plan'].create({'name':'QA122 '+origin}) for origin in ('season','species','ot')}
        for origin,plan in cls.plans.items():
            cls.env['step.packing.analytic.rule'].create({'company_id':cls.company.id,'plan_id':plan.id,'origin':origin,'apply':True})
        def account(code,kind):
            return cls.env['account.account'].create({'code':code,'name':'QA122 '+kind,'account_type':kind,
                                                     'company_ids':[(6,0,cls.company.ids)]})
        cls.expense=account('QA1221','expense');cls.asset=account('QA1222','asset_current')
        cls.clearing=account('QA1223','asset_current')
        cls.journal=cls.env['account.journal'].create({'name':'QA122 stock','code':'Q122','type':'general','company_id':cls.company.id})
        cls.category=cls.env['product.category'].create({'name':'QA122 automática','property_valuation':'real_time',
            'property_cost_method':'standard','property_stock_valuation_account_id':cls.asset.id,
            'property_stock_account_input_categ_id':cls.clearing.id,'property_stock_account_output_categ_id':cls.clearing.id,
            'property_account_expense_categ_id':cls.expense.id,'property_stock_journal':cls.journal.id})
        cls.raw=cls.env['product.product'].create({'name':'QA122 fruta','is_storable':True,'categ_id':cls.category.id,'standard_price':5})
        cls.finished=cls.env['product.product'].create({'name':'QA122 exportación','is_storable':True})
        cls.material=cls.env['product.product'].create({'name':'QA122 cartón','is_storable':True,'categ_id':cls.category.id,'standard_price':2})
        cls.env['mrp.bom'].create({'product_tmpl_id':cls.finished.product_tmpl_id.id,'product_qty':1,
                                 'bom_line_ids':[(0,0,{'product_id':cls.material.id,'product_qty':1})]})

    def ot(self):
        def tag(kind,product,quantity,kilos,result=False):
            return self.env['stock.quant.package'].create({'is_fruit_tag':True,'step_tag_kind':kind,
                'step_packing_result':result,'step_producer_id':self.producer.id,'especie_id':self.species.id,
                'variedad_id':self.variety.id,'step_export_season_id':self.season.id,
                'step_tag_line_ids':[(0,0,{'product_id':product.id,'producer_id':self.producer.id,
                                         'quantity':quantity,'boxes':quantity,'kilos':kilos})]})
        incoming=tag('C',self.raw,100,100);incoming.action_step_validate_tag()
        output=tag('E',self.finished,16,80,'export')
        self.env['stock.quant']._update_available_quantity(self.raw,self.wh.lot_stock_id,100,package_id=incoming,owner_id=self.producer)
        self.env['stock.quant']._update_available_quantity(self.material,self.company.step_packing_material_location_id or self.wh.lot_stock_id,16)
        ot=self.env['step.packing.production'].create({'step_packing_input_tag_ids':[(6,0,incoming.ids)],
                                                      'step_packing_output_tag_ids':[(6,0,output.ids)]})
        ot.action_step_packing_validate();ot.action_prepare_materials();ot.action_approve_materials()
        return ot

    def test_native_posting_expense_debit_inventory_credit_three_plans(self):
        ot=self.ot()
        self.assertFalse(self.env['account.analytic.account'].search([('step_packing_production_id','=',ot.id)]))
        ot.action_step_packing_close()
        entries=ot.material_picking_id.move_ids.stock_valuation_layer_ids.account_move_id
        self.assertEqual(entries.state,'posted')
        debit=entries.line_ids.filtered(lambda line:line.debit)
        credit=entries.line_ids.filtered(lambda line:line.credit)
        self.assertEqual(debit.account_id,self.expense);self.assertEqual(credit.account_id,self.asset)
        self.assertEqual(debit.debit,32);self.assertEqual(credit.credit,32)
        ids=[int(value) for key in debit.analytic_distribution for value in key.split(',')]
        accounts=self.env['account.analytic.account'].browse(ids)
        self.assertEqual(set(accounts.plan_id.ids),set(plan.id for plan in self.plans.values()))
        self.assertEqual(len(accounts),3)
        self.assertEqual(accounts.filtered(lambda account:account.step_packing_production_id).name,ot.name)
        self.assertFalse(credit.analytic_distribution)
        self.assertFalse(ot.input_picking_id.move_ids.stock_valuation_layer_ids)
        self.assertTrue(debit.analytic_line_ids)

    def test_account_is_created_only_for_accounting_and_is_idempotent(self):
        ot=self.ot();self.assertFalse(self.env['account.analytic.account'].search([('step_packing_production_id','=',ot.id)]))
        ot.action_step_packing_close()
        account=self.env['account.analytic.account'].search([('step_packing_production_id','=',ot.id)])
        self.assertEqual(len(account),1)
        ot._packing_distribution(create=True);ot.action_apply_packing_analytics()
        self.assertEqual(self.env['account.analytic.account'].search([('step_packing_production_id','=',ot.id)]),account)
        self.assertFalse(ot.step_analytic_reclassification_ids)

    def test_product_expense_account_takes_priority_over_category(self):
        expense=self.env['account.account'].create({'name':'QA122 gasto producto','code':'QA1224',
            'account_type':'expense','company_ids':[(6,0,self.company.ids)]})
        self.material.property_account_expense_id=expense
        ot=self.ot();ot.action_step_packing_close()
        entry=ot.material_picking_id.move_ids.stock_valuation_layer_ids.account_move_id
        self.assertEqual(entry.line_ids.filtered('debit').account_id,expense)

    def test_reuses_native_species_and_season_accounts(self):
        species=self.env['account.analytic.account'].create({'name':'Centro existente','company_id':self.company.id,'plan_id':self.plans['species'].id})
        season=self.env['account.analytic.account'].create({'name':'Temporada existente','company_id':self.company.id,'plan_id':self.plans['season'].id})
        self.species.cost_id=species;self.season.cost_id=season
        ot=self.ot();distribution=ot._packing_distribution(create=True)
        ids={int(value) for key in distribution for value in key.split(',')}
        self.assertTrue({species.id,season.id}<=ids)

    def test_unselected_plans_and_existing_weighted_dimension_are_preserved(self):
        activity=self.env['account.analytic.plan'].create({'name':'QA122 actividad'})
        a=self.env['account.analytic.account'].create({'name':'A','plan_id':activity.id,'company_id':self.company.id})
        b=self.env['account.analytic.account'].create({'name':'B','plan_id':activity.id,'company_id':self.company.id})
        ot=self.ot();result=ot._packing_distribution(create=True,existing={str(a.id):60,str(b.id):40})
        self.assertEqual(sorted(result.values()),[40,60]);self.assertTrue(all(len(key.split(','))==4 for key in result))

    def test_missing_season_rolls_back_stock_and_journals(self):
        ot=self.ot();ot.step_packing_input_tag_ids.step_export_season_id=False
        before=self.env['account.move'].search_count([])
        with self.assertRaises(UserError):ot.action_step_packing_close()
        self.assertEqual(ot.state,'validated');self.assertFalse(ot.material_picking_id)
        self.assertEqual(self.env['account.move'].search_count([]),before)

    def test_conflicting_existing_plan_account_is_not_overwritten(self):
        other=self.env['account.analytic.account'].create({'name':'Otro centro','plan_id':self.plans['species'].id,'company_id':self.company.id})
        ot=self.ot()
        with self.assertRaises(UserError):ot._packing_distribution(create=True,existing={str(other.id):100})

    def test_archived_source_account_is_not_duplicated(self):
        ot=self.ot();ot._packing_distribution(create=True)
        account=self.env['account.analytic.account'].search([('step_packing_production_id','=',ot.id)])
        account.active=False
        count=self.env['account.analytic.account'].with_context(active_test=False).search_count([])
        with self.assertRaises(UserError):ot._packing_distribution(create=True)
        self.assertEqual(self.env['account.analytic.account'].with_context(active_test=False).search_count([]),count)

    def test_rules_reject_duplicate_origin_and_non_root_plan(self):
        other=self.env['account.analytic.plan'].create({'name':'QA122 otro'})
        with self.assertRaises(ValidationError),self.cr.savepoint():
            self.env['step.packing.analytic.rule'].create({'company_id':self.company.id,'plan_id':other.id,'origin':'season','apply':True})
        child=self.env['account.analytic.plan'].create({'name':'QA122 hijo','parent_id':other.id})
        with self.assertRaises(ValidationError),self.cr.savepoint():
            self.env['step.packing.analytic.rule'].create({'company_id':self.company.id,'plan_id':child.id})

    def test_historical_clearing_account_has_one_draft_reclassification(self):
        ot=self.ot();ot.action_step_packing_close()
        entry=ot.material_picking_id.move_ids.stock_valuation_layer_ids.account_move_id
        # Build a separate posted legacy journal; never rewrite a real posted entry.
        legacy=self.env['account.move'].create({'journal_id':self.journal.id,'line_ids':[
            (0,0,{'account_id':self.clearing.id,'product_id':self.material.id,'debit':32,'credit':0}),
            (0,0,{'account_id':self.asset.id,'product_id':self.material.id,'debit':0,'credit':32})]})
        legacy.action_post()
        layer=ot.material_picking_id.move_ids.stock_valuation_layer_ids
        layer.account_move_id=legacy
        ot.action_apply_packing_analytics();ot.action_apply_packing_analytics()
        correction=ot.step_analytic_reclassification_ids
        self.assertEqual(len(correction),1);self.assertEqual(correction.state,'draft')
        self.assertEqual(legacy.state,'posted');self.assertEqual(legacy.line_ids.filtered('debit').account_id,self.clearing)
        self.assertEqual(correction.line_ids.filtered('debit').account_id,self.expense)
        self.assertEqual(correction.line_ids.filtered('credit').account_id,self.clearing)
        self.assertTrue(correction.line_ids.filtered('debit').analytic_distribution)
        correction.action_post();self.assertEqual(correction.state,'posted')
        self.assertEqual(entry.state,'posted')

    def test_native_form_shows_analytic_configuration_and_review_action(self):
        ot=self.ot();Form(ot,view='step_packing_operations.view_packing_production_form')
        self.assertEqual(ot.step_effective_season_id,self.season)

    def test_native_material_return_reverses_original_expense_and_analytics(self):
        ot=self.ot();ot.action_step_packing_close()
        original=ot.material_picking_id.move_ids
        distribution=original.stock_valuation_layer_ids.account_move_id.line_ids.filtered('debit').analytic_distribution
        picking=self.env['stock.picking'].create({'picking_type_id':self.wh.int_type_id.id,
            'location_id':original.location_dest_id.id,'location_dest_id':original.location_id.id,
            'move_ids':[(0,0,{'name':'QA122 devolución','product_id':self.material.id,
                'product_uom':self.material.uom_id.id,'product_uom_qty':16,
                'location_id':original.location_dest_id.id,'location_dest_id':original.location_id.id,
                'origin_returned_move_id':original.id})]})
        picking.action_confirm();picking.move_ids.quantity=16;picking.button_validate()
        entry=picking.move_ids.stock_valuation_layer_ids.account_move_id
        self.assertEqual(entry.state,'posted')
        self.assertEqual(entry.line_ids.filtered('debit').account_id,self.asset)
        self.assertEqual(entry.line_ids.filtered('credit').account_id,self.expense)
        self.assertEqual(entry.line_ids.filtered('credit').analytic_distribution,distribution)
