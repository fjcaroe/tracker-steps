from lxml import etree
from odoo import Command
from odoo.exceptions import ValidationError, UserError
from odoo.tests.common import TransactionCase, new_test_user


class EstimateRevisionCase(TransactionCase):
    def sample(self, group='bins', kind='process'):
        env = self.env(context=dict(self.env.context, no_reset_password=True,
                                   tracking_disable=True, mail_create_nosubscribe=True))
        producer = env['res.partner'].create({'name':'QA T75 producer','is_productor':True})
        packing = env['res.partner'].create({'name':'QA T75 packing','step_export_packing':True})
        fundo = env['step.fundo'].create({'name':'QA T75 farm','partner_id':producer.id})
        season = env['step.temporada'].create({'name':'QA T75 season'})
        species = env['step.especie'].create({'name':'QA T75 species','type_especie':'frutal',
            'group_especie':'baya','kg_caja':5,'base_boxes_per_pallet':200})
        product = env['product.product'].create({'name':'QA T75 fruit','is_fruta':True})
        package = env['stock.package.type'].create({'name':'QA T74 package',
            'fruit_package_group':group,'step_export_boxes_per_pallet':35,'pallets_per_aircraft':4})
        estimate = env['step.export.estimate'].create({'name':'QA T75 estimate','producer_id':producer.id,
            'packing_partner_id':packing.id,'fundo_id':fundo.id,'season_id':season.id,
            'estimate_line_ids':[Command.create({'species_id':species.id,'product_id':product.id,
                'package_type_id':package.id,'delivery_kind':kind,'export_kg':100000,
                'export_percentage':.8,'kg_per_box':9,'boxes_per_package':999,
                'week_line_ids':[Command.create({'week_start':'2026-11-02','export_kg':40000}),
                                 Command.create({'week_start':'2026-11-09','export_kg':60000})]})]})
        return estimate

    def test_bins_and_species_use_master_denominators(self):
        line = self.sample().estimate_line_ids
        self.assertAlmostEqual(line.process_kg,125000)
        self.assertAlmostEqual(line.harvest_box_qty,125000/9)
        self.assertAlmostEqual(line.bin_qty,125000/35)
        self.assertEqual(line.process_pallet_qty,0)
        self.assertEqual(line.export_box_qty,20000)
        self.assertEqual(line.export_pallet_qty,500)

    def test_pallet_floor_and_packed(self):
        line = self.sample(group='pallet').estimate_line_ids
        self.assertEqual(line.bin_qty,0)
        self.assertAlmostEqual(line.process_pallet_qty,125000/35)
        line.package_type_id.fruit_package_group='floor'
        self.assertEqual(line.process_pallet_qty,0)
        self.assertEqual(line.bin_qty,0)
        line.delivery_kind='packed'
        self.assertEqual(line.process_kg,0)
        self.assertEqual(line.harvest_box_qty,0)
        self.assertEqual(line.export_box_qty,20000)

    def test_zero_missing_denominators_and_master_recompute(self):
        line = self.sample(group=False).estimate_line_ids
        self.assertEqual(line.bin_qty,0)
        line.package_type_id.write({'fruit_package_group':'pallet','step_export_boxes_per_pallet':0})
        self.assertEqual(line.process_pallet_qty,0)
        line.species_id.write({'kg_caja':0,'base_boxes_per_pallet':0})
        self.assertEqual(line.export_box_qty,0)
        self.assertEqual(line.export_pallet_qty,0)
        line.package_type_id.step_export_boxes_per_pallet=50
        line.species_id.write({'kg_caja':10,'base_boxes_per_pallet':100})
        self.assertEqual(line.process_pallet_qty,2500)
        self.assertEqual(line.export_box_qty,10000)
        self.assertEqual(line.export_pallet_qty,1000)

    def test_report_undefined_and_negative_denominators(self):
        line=self.sample().estimate_line_ids
        line.package_type_id.step_export_boxes_per_pallet=0
        line.species_id.write({'kg_caja':-5,'base_boxes_per_pallet':0})
        line.export_percentage=0
        self.env.flush_all()
        rows=self.env['step.producer.estimate.report'].search([('line_id','=',line.id)])
        self.assertEqual(len(rows),2)
        for field in ('process_kg','bin_qty','process_pallet_qty','export_box_qty','export_pallet_qty'):
            self.assertEqual(line[field],0)
            self.assertEqual(sum(rows.mapped(field)),0)

    def test_weekly_report_matches_line_and_pivot(self):
        line = self.sample(group='pallet').estimate_line_ids
        self.env.flush_all()
        rows=self.env['step.producer.estimate.report'].search([('line_id','=',line.id)])
        self.assertEqual(len(rows),2)
        for field in ('bin_qty','process_pallet_qty','export_box_qty','export_pallet_qty'):
            self.assertAlmostEqual(sum(rows.mapped(field)),line[field])
        total=rows.read_group([('id','in',rows.ids)],['process_pallet_qty:sum','export_box_qty:sum'],[])[0]
        self.assertAlmostEqual(total['process_pallet_qty'],125000/35)
        self.assertEqual(total['export_box_qty'],20000)

    def test_version_and_weekly_validation_preserved(self):
        estimate=self.sample()
        estimate.action_validate_estimate();estimate.action_activate_estimate()
        with self.assertRaises(UserError):estimate.estimate_line_ids.export_kg=1
        new=self.env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        self.assertEqual(new.estimate_line_ids.export_box_qty,20000)
        new.estimate_line_ids.week_line_ids[0].export_kg=39999
        with self.assertRaises(ValidationError):new.action_validate_estimate()

    def test_master_menus_and_effective_forms(self):
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),
            login='qa-t74-master-reader',groups='stock.group_stock_manager')
        visible=self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        action=self.env.ref('step_export.action_step_export_package_type')
        for key in ('packing','producer'):
            menu=self.env.ref('step_producer_estimate_revision.'+key+'_package_types')
            self.assertEqual(menu.action,action);self.assertIn(menu.id,visible)
        for xmlid in ('step_export.view_step_export_package_type_form','stock.stock_package_type_form'):
            arch=etree.fromstring(self.env['stock.package.type'].with_user(user).get_view(
                view_id=self.env.ref(xmlid).id,view_type='form')['arch'].encode())
            for name in ('fruit_package_group','pallets_per_aircraft','step_export_boxes_per_pallet'):
                self.assertTrue(arch.xpath('.//field[@name="%s"]'%name))

    def test_negative_capacities_rejected(self):
        package=self.sample().estimate_line_ids.package_type_id
        with self.assertRaises(ValidationError),self.env.cr.savepoint():package.pallets_per_aircraft=-1
        with self.assertRaises(ValidationError),self.env.cr.savepoint():package.step_export_boxes_per_pallet=-1
