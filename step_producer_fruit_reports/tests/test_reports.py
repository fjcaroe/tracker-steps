from uuid import uuid4
from datetime import datetime
from odoo import Command
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import AccessError
from odoo.tools import mute_logger
from psycopg2 import IntegrityError


class FruitReportsCase(TransactionCase):
    def sample(self, kind='process', done=True):
        env=self.env(context=dict(self.env.context,no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True))
        company=env.company
        company.step_fruit_inventory_enabled=True
        producer=env['res.partner'].create({'name':'QA T70-T72 producer','is_productor':True})
        fundo=env['step.fundo'].create({'name':'QA T70-T72 farm','partner_id':producer.id,'company_id':company.id})
        species=env['step.especie'].create({'name':'QA T70-T72 fruit','type_especie':'frutal','group_especie':'baya','sag_code':'SAG-QA','base_boxes_per_pallet':60})
        group=env['step.grupo.variedad'].create({'name':'QA T70-T72 group','especie_id':species.id})
        variety=env['step.variedad'].create({'name':'QA T70-T72 variety','cod_variedad':'QA-7072','especie_id':species.id,'grupo_variedad_id':group.id})
        season=env['step.temporada'].create({'name':'QA T70-T72 season'})
        product=env['product.product'].create({'name':'QA T70-T72 fruit','is_storable':True,'weight':5,'tracking':'lot'})
        packaging=env['product.packaging'].create({'name':'QA T70-T72 packaging','product_id':product.id,'qty':1})
        warehouse=env['stock.warehouse'].search([('company_id','=',company.id)],limit=1)
        if not warehouse:warehouse=env['stock.warehouse'].create({'name':'QA FRUIT WH','code':uuid4().hex[:5].upper(),'company_id':company.id})
        lot=env['stock.lot'].create({'name':'QA-LOT-'+uuid4().hex[:8],'product_id':product.id,'company_id':company.id})
        tags=env['stock.quant.package'].create([{'name':'QA-TAG-'+uuid4().hex[:8],'is_fruit_tag':True,'step_tag_kind':'C' if kind=='process' else 'E'} for n in (1,2)])
        picking=env['stock.picking'].create({'partner_id':producer.id,'picking_type_id':warehouse.in_type_id.id,
            'location_id':warehouse.in_type_id.default_location_src_id.id,'location_dest_id':warehouse.lot_stock_id.id,
            'step_fruit_reception_kind':kind,'fruit_fundo_id':fundo.id,'fruit_species_id':species.id,'fruit_variety_id':variety.id,
            'fruit_season_id':season.id,'fruit_lot':'QA DECLARED LOT','step_fruit_gross_kg':150,
            'fruit_tag_line_ids':[Command.create({'tag_number':tag.name,'package_id':tag.id,'product_id':product.id,
                'packaging_id':packaging.id,'stock_lot_id':lot.id,'uom_id':product.uom_id.id,'quantity':qty,'kilos':qty*5,'box_count':qty}) for tag,qty in zip(tags,(10,20))]})
        if done:
            picking.action_prepare_fruit_stock();picking.button_validate()
            assert picking.state=='done'
            picking.date_done=datetime(2026,11,30,15)
        env.flush_all()
        return picking

    def rows(self,picking):
        self.env.flush_all()
        return self.env['step.fruit.reception.report'].search([('picking_id','=',picking.id)])

    def test_process_and_packed_receipt_totals_and_dimensions(self):
        for kind in ('process','packed'):
            picking=self.sample(kind);rows=self.rows(picking)
            self.assertEqual(len(rows),2)
            self.assertEqual(sum(rows.mapped('packaging_qty')),30)
            self.assertEqual(sum(rows.mapped('kilos')),150)
            self.assertEqual(set(rows.mapped('reception_kind')),{kind})
            self.assertEqual(rows.product_id,picking.fruit_tag_line_ids.product_id)
            self.assertEqual(rows.packaging_id,picking.fruit_tag_line_ids.packaging_id)
            self.assertEqual(rows.lot_id,picking.fruit_tag_line_ids.stock_lot_id)
            self.assertEqual(rows.producer_id,picking.fruit_fundo_id.partner_id)
            self.assertEqual(rows.season_id,picking.fruit_season_id)
            self.assertEqual(rows.variety_id,picking.fruit_variety_id)

    def test_pending_receipts_are_separate_from_done(self):
        picking=self.sample(done=False);rows=self.rows(picking)
        self.assertEqual(len(rows),2)
        self.assertFalse(self.env['step.fruit.reception.report'].search([('picking_id','=',picking.id),('state','=','done')]))
        picking.fruit_tag_line_ids[0].kilos=45;self.env.flush_all();rows.invalidate_recordset()
        self.assertEqual(sum(rows.mapped('kilos')),145)

    def test_multiple_stock_lines_do_not_duplicate_tag_quantities(self):
        picking=self.sample();line=picking.fruit_tag_line_ids[0]
        move_line=picking.move_line_ids.filtered(lambda row:row.result_package_id==line.package_id)[0]
        move_line.quantity-=1
        move_line.copy({'quantity':1})
        self.assertEqual(sum(picking.move_line_ids.mapped('quantity')),30)
        line.stock_lot_id=False;self.env.flush_all()
        rows=self.rows(picking)
        self.assertEqual(len(rows),2);self.assertEqual(sum(rows.mapped('kilos')),150)
        self.assertTrue(rows.filtered(lambda row:row.tag_line_id==line).lot_id)

    def test_ambiguous_lots_are_not_guessed(self):
        picking=self.sample();line=picking.fruit_tag_line_ids[0];line.stock_lot_id=False
        lot=self.env['stock.lot'].create({'name':'QA-LOT-OTHER','product_id':line.product_id.id,'company_id':picking.company_id.id})
        move_line=picking.move_line_ids.filtered(lambda row:row.result_package_id==line.package_id)[0]
        move_line.quantity-=1
        move_line.copy({'quantity':1,'lot_id':lot.id})
        self.assertEqual(sum(picking.move_line_ids.mapped('quantity')),30)
        self.env.flush_all();row=self.rows(picking).filtered(lambda row:row.tag_line_id==line)
        self.assertTrue(row.ambiguous_lot);self.assertFalse(row.lot_id)
        self.assertEqual(row.kilos,50)

    def test_company_rule_and_read_only_permissions(self):
        picking=self.sample();rows=self.rows(picking)
        ctx=dict(self.env.context,no_reset_password=True)
        user=new_test_user(self.env(context=ctx),login='qa-fruit-reader',groups='stock.group_stock_user',company_id=picking.company_id.id,company_ids=[Command.set(picking.company_id.ids)])
        with self.assertRaises(AccessError):rows.with_user(user).write({'kilos':0})
        other=self.env['res.company'].create({'name':'QA fruit other'})
        outsider=new_test_user(self.env(context=ctx),login='qa-fruit-other',groups='stock.group_stock_user',company_id=other.id,company_ids=[Command.set(other.ids)])
        self.assertFalse(rows.with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)]))

    def test_species_fields_are_persisted_and_nonnegative(self):
        picking=self.sample();species=picking.fruit_species_id
        self.assertEqual(species.sag_code,'SAG-QA');self.assertEqual(species.base_boxes_per_pallet,60)
        with mute_logger('odoo.sql_db'),self.assertRaises(IntegrityError),self.env.cr.savepoint():species.base_boxes_per_pallet=-1

    def test_stock_profile_can_consult_the_eight_shared_masters(self):
        user=new_test_user(self.env(context=dict(self.env.context,no_reset_password=True)),login='qa-fruit-catalogs',groups='stock.group_stock_manager',company_id=self.env.company.id,company_ids=[Command.set(self.env.company.ids)])
        visible=self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()
        for key in ('species','variety_group','variety','caliber_group','caliber','category','quality','color'):
            menu=self.env.ref('step_producer_fruit_reports.config_'+key)
            self.assertIn(menu.id,visible,key)
            self.env[menu.action.res_model].with_user(user).search([],limit=1)
        for name in ('step.management.caliber.group','step.management.fruit.caliber','step.management.fruit.category'):
            self.assertFalse(self.env[name].with_user(user).has_access('write'))
