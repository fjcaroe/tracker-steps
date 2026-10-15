from lxml import etree
from psycopg2 import IntegrityError
from odoo import Command
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tests.common import TransactionCase, tagged, new_test_user
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class ShippingCase(TransactionCase):
    def test_fixed_print_for_legacy_without_changing_tracking(self):
        shipment,_=self.sample()
        tracked=shipment.documentation_ids.filtered(lambda d:d.kind=='dus')
        tracked.write({'originals':9,'status':'received','instructions':'Operational note only'})
        reports=shipment.env['ir.actions.report']
        html,_=reports._render_qweb_html('step_export_shipping_design.instruction',shipment.ids)
        tree=etree.HTML(html)
        documentation=tree.xpath('//div[@data-section="documentation"]')[0]
        self.assertNotIn('Estado',''.join(documentation.itertext()))
        self.assertNotIn('Operational note only',''.join(documentation.itertext()))
        self.assertEqual(len(documentation.xpath('.//tbody/tr')),5)
        self.assertEqual(tracked.originals,9);self.assertEqual(tracked.status,'received')
        shipment.documentation_ids.unlink();shipment.freight_ids.unlink()
        html,_=reports._render_qweb_html('step_export_shipping_design.instruction',shipment.ids)
        tree=etree.HTML(html)
        self.assertEqual(len(tree.xpath('//div[@data-section="documentation"]//tbody/tr')),5)
        self.assertEqual(len(tree.xpath('//div[@data-section="freights"]//tbody/tr')),13)
        self.assertFalse(shipment.documentation_ids);self.assertFalse(shipment.freight_ids)

    def test_freight_list_copy_and_completion_preserve_payment(self):
        shipment,_=self.sample(shared=False)
        thc=shipment.freight_ids.filtered(lambda f:f.concept_id.name=='THC')
        thc.payment='prepaid'
        original=shipment.freight_ids.ids
        shipment.action_complete_instruction_freights();shipment.action_complete_instruction_freights()
        self.assertEqual(shipment.freight_ids.ids,original)
        self.assertEqual(thc.payment,'prepaid')
        copied=shipment.copy({'shipment_number':'QA83/0002'})
        self.assertEqual(len(copied.freight_ids),len(original))
        self.assertEqual(copied.freight_ids.filtered(lambda f:f.concept_id==thc.concept_id).payment,'prepaid')
        self.assertEqual(dict(thc._fields['payment']._description_selection(thc.env)),{'collect':'Collect','prepaid':'Prepaid'})

    def test_product_blocks_and_critical_fields(self):
        shipment,_=self.sample()
        shipment.line_ids.copy({'shipment_id':shipment.id,'label':'Second cargo brand'})
        html,_=shipment.env['ir.actions.report']._render_qweb_html('step_export_shipping_design.instruction',shipment.ids)
        tree=etree.HTML(html)
        products=tree.xpath('//div[@data-section="product"]')
        self.assertEqual(len(products),2)
        self.assertTrue(all(len(block.xpath('.//tr'))==6 for block in products))
        for label in ('CANTIDAD CONTENEDORES','BOOKING','PUERTO DE EMBARQUE','TEMPERATURA °C'):
            self.assertTrue(tree.xpath('//th[@class="critical" and text()="%s"]'%label))
        self.assertIn('Second cargo brand',html.decode())

    def sample(self, shared=True):
        company = self.env['res.company'].create({'name':'QA Shipping Company','currency_id':self.env.ref('base.USD').id,
            'export_folio_mode':'shared' if shared else 'document','export_folio_initial':257, 'step_export_sale_format':True})
        env = self.env(context=dict(self.env.context,allowed_company_ids=company.ids,tracking_disable=True,mail_create_nosubscribe=True,no_reset_password=True))
        receiver = env['res.partner'].create({'name':'QA Shipping Receiver','step_export_receiver':True})
        season = env['step.temporada'].create({'name':'QA Shipping Season'})
        species = env['step.especie'].create({'name':'QA Shipping Species','type_especie':'frutal','group_especie':'baya'})
        group = env['step.grupo.variedad'].create({'name':'QA Shipping Varieties','especie_id':species.id})
        variety = env['step.variedad'].create({'name':'QA Shipping Variety','cod_variedad':'QA81',
            'especie_id':species.id,'grupo_variedad_id':group.id})
        quality = env['step.management.fruit.quality'].create({'name':'QA Shipping Quality','code':'Q81','company_id':company.id})
        product = env['product.product'].create({'name':'QA Shipping Product','is_fruta':True})
        package = env['stock.package.type'].create({'name':'QA Shipping Pallet'})
        program = env['step.export.sales.program'].create({'name':'QA Shipping Program','partner_id':receiver.id,'season_id':season.id,
            'species_id':species.id,'product_id':product.id,'package_type_id':package.id,'date_start':'2026-11-02','date_end':'2026-11-16',
            'currency_id':company.currency_id.id,'rate_to_usd':1,'pallets_per_container':20,'boxes_per_pallet':480,'kg_per_box':1.5,
            'line_ids':[Command.create({'week_start':'2026-11-02','container_qty':1,'price_per_kg':1})]})
        program.action_validate(); program.action_activate()
        order = env['sale.order'].create({'partner_id':receiver.id,'company_id':company.id,'step_export_sale':True,
            'export_folio':257 if shared else 0, 'order_line':[Command.create({'product_id':product.id,'product_uom_qty':9600,'price_unit':1,
                'step_export_kg':14400,'step_export_boxes':9600})]})
        concept = env['step.export.exterior.expense.concept'].create({'name':'QA Shipping Freight','company_id':company.id})
        vals = {'name':'QA Shipping Instruction','company_id':company.id,'sales_program_id':program.id,'season_id':season.id,
            'species_id':species.id,'receiver_id':receiver.id,'booking':'QA BOOKING 81','freight_payment':'collect','temperature':-0.5,
            'ventilation':'15 CBM','thermograph_qty':2,'container_qty':1,'gross_kg':14500,'user_id':env.user.id,
            'departure_date':'2026-11-13','arrival_date':'2026-12-08','notes':'<p>QA Shipping observations</p>',
            'line_ids':[Command.create({'product_id':product.id,'variety_id':variety.id,'quality_id':quality.id,'label':'QA Brand',
                'pallet_qty':20,'boxes_per_pallet':480,'kg_per_box':1.5})],
            'freight_ids':[Command.create({'concept_id':concept.id,'payment':'collect'})]}
        if shared: vals['folio_sale_order_id']=order.id
        else: vals['shipment_number']='QA81/0001'
        shipment = env['step.export.export'].create(vals)
        order.step_export_shipment_id=shipment
        return shipment,order

    def test_shared_commercial_workflow_and_print(self):
        shipment,order=self.sample()
        self.assertEqual(order.name,'257');self.assertEqual(shipment.shipment_number,'257')
        self.assertEqual(shipment.commercial_folio,'257');self.assertEqual(order.export_document_number,'257')
        self.assertEqual(len(shipment.documentation_ids),5)
        shipment.documentation_ids[0].write({'originals':5,'status':'sent','date':'2026-11-13'})
        self.assertEqual(shipment.box_qty,9600);self.assertEqual(shipment.kg_qty,14400)
        shipment.action_validate_shipment();self.assertEqual(shipment.state,'validated')
        values=order._prepare_invoice()
        self.assertEqual(values['export_folio_sale_order_id'],order.id)
        journal=shipment.env['account.journal'].create({'name':'QA Shipping Sales','code':'Q81','type':'sale','company_id':shipment.company_id.id})
        values['journal_id']=journal.id
        invoice=shipment.env['account.move'].create(values)
        self.assertEqual(invoice.export_document_number,'257')
        self.assertEqual(invoice.state,'draft')
        self.assertIn(invoice.name,(False,'/'))
        for report in ('step_sale_export_report.sale_note','step_sale_export_report.proforma'):
            commercial,_=shipment.env['ir.actions.report']._render_qweb_html(report,order.ids)
            self.assertIn('257',commercial.decode())
        html,_=shipment.env['ir.actions.report']._render_qweb_html('step_export_shipping_design.instruction',shipment.ids)
        for text in ('QA BOOKING 81','QA Brand','QA Shipping Quality','DOCUMENTACIÓN REQUERIDA','REF'):
            self.assertIn(text,html.decode())

    def test_independent_numbering_and_ordinary_orders(self):
        shipment,order=self.sample(shared=False)
        self.assertEqual(shipment.shipment_number,'QA81/0001');self.assertFalse(order.export_folio)
        self.assertEqual(order.export_document_number,order.name)
        second=order.copy();self.assertFalse(second.export_folio)
        self.assertEqual(order.company_id.export_folio_mode,'document')

    @mute_logger('odoo.sql_db')
    def test_folio_unique_and_frozen(self):
        shipment,order=self.sample()
        with self.assertRaises(IntegrityError),self.env.cr.savepoint():
            order.copy({'export_folio':257})
        with self.assertRaises(UserError):order.export_folio=258
        with self.assertRaises(UserError):order.name='258'
        with self.assertRaises(UserError):shipment.shipment_number='258'
        with self.assertRaises(ValidationError):
            order.copy({'export_folio':256})
        with self.assertRaises(ValidationError):
            shipment.copy({'folio_sale_order_id':False})

    def test_company_rules_and_effective_form(self):
        shipment,order=self.sample()
        user=new_test_user(shipment.env,login='qa-t81-export-operator',groups='sales_team.group_sale_salesman',company_id=shipment.company_id.id,company_ids=[Command.set(shipment.company_id.ids)])
        order.user_id=user
        record=shipment.with_user(user)
        arch=etree.fromstring(record.get_view(view_id=record.env.ref('step_export.view_step_export_export_form').id,view_type='form')['arch'].encode())
        for name in ('booking','freight_payment','documentation_ids','freight_ids','quality_id','folio_sale_order_id'):
            self.assertTrue(arch.xpath('.//field[@name="%s"]'%name))
        record.documentation_ids[0].status='received'
        other=new_test_user(self.env,login='qa-t81-other-company',groups='stock.group_stock_user',company_id=self.env.company.id,company_ids=[Command.set(self.env.company.ids)])
        with self.assertRaises(AccessError):
            shipment.documentation_ids.with_user(other).with_context(allowed_company_ids=other.company_ids.ids).read(['kind'])
