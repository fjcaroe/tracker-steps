from datetime import date
from lxml import etree
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.step_export_client_revision.models.revision import ROLES
from odoo.addons.step_export_client_revision.hooks import pre_init_hook, post_init_hook


@tagged('post_install', '-at_install')
class ClientRevisionCase(TransactionCase):
    def program(self):
        receiver = self.env['res.partner'].create({'name':'QA commercial receiver','step_export_receiver':True})
        season = self.env['step.temporada'].create({'name':'QA commercial season'})
        species = self.env['step.especie'].create({'name':'QA commercial species','type_especie':'frutal','group_especie':'seco'})
        product = self.env['product.product'].create({'name':'QA fruit','is_fruta':True,'step_export_enabled':True,'grupo_labor':'pack'})
        pallet = self.env['stock.package.type'].create({'name':'QA pallet'})
        return self.env['step.export.sales.program'].create({'name':'QA programme','partner_id':receiver.id,
            'season_id':season.id,'species_id':species.id,'product_id':product.id,'package_type_id':pallet.id,
            'date_start':date(2026,11,2),'date_end':date(2026,11,15),'transport_type':'air',
            'pallets_per_container':20,'boxes_per_pallet':10,'kg_per_box':5,'rate_to_usd':1,
            'line_ids':[(0,0,{'week_start':date(2026,11,2),'container_qty':2,'price_per_kg':3}),
                        (0,0,{'week_start':date(2026,11,9),'container_qty':1,'price_per_kg':4})]})

    def test_transport_is_versioned_and_copied(self):
        program=self.program(); program.action_validate(); program.action_activate()
        with self.assertRaises(UserError), self.cr.savepoint():program.transport_type='land'
        new=self.env[program._name].browse(program.action_new_version()['res_id'])
        self.assertEqual(new.transport_type,'air')
        new.transport_type='land';self.assertEqual(program.transport_type,'air')

    def test_installation_preserves_week_audit(self):
        program=self.program();line=program.line_ids[0]
        self.env.flush_all()
        before=(line.write_uid.id,line.write_date)
        pre_init_hook(self.env)
        self.cr.execute("UPDATE step_export_sales_program_line SET write_date='2020-01-01' WHERE id=%s",[line.id])
        post_init_hook(self.env)
        self.assertEqual((line.write_uid.id,line.write_date),before)
        self.assertEqual(line.transport_type,'air')

    def test_weekly_report_quantities_usd_and_dimensions(self):
        program=self.program();lines=program.line_ids
        self.assertEqual(lines[0].week_end,date(2026,11,9))
        self.assertEqual(lines[0].species_id,program.species_id)
        self.assertEqual(lines[0].transport_type,'air')
        result=lines.read_group([('id','in',lines.ids)],['container_qty:sum','pallet_qty:sum','box_qty:sum','kg_qty:sum','amount_usd:sum'],[])[0]
        self.assertEqual(result['container_qty'],3);self.assertEqual(result['pallet_qty'],60)
        self.assertEqual(result['box_qty'],600);self.assertEqual(result['kg_qty'],3000)
        self.assertEqual(result['amount_usd'],10000)
        action=self.env.ref('step_export_client_revision.program_report')
        self.assertEqual(action.view_mode,'gantt,pivot,list')
        for kind in ('gantt','pivot','list'):
            view=self.env.ref('step_export_client_revision.week_'+kind)
            tree=etree.fromstring(lines.get_view(view_id=view.id,view_type=kind)['arch'].encode())
            self.assertEqual(tree.tag,kind)

    def test_contacts_have_specific_selection_domains(self):
        shipment=self.env['step.export.export'].new({'name':'QA role domains'})
        tree=etree.fromstring(shipment.get_view(view_type='form')['arch'].encode())
        for field,flag in ROLES.items():
            partner=self.env['res.partner'].create({'name':'QA '+flag,flag:True})
            self.assertTrue(partner.step_export)
            self.assertIn(flag,tree.xpath(".//field[@name='%s']" % field)[0].get('domain'))
            self.assertIn(partner,self.env['res.partner'].search(shipment._fields[field].domain))
            self.assertNotIn(partner,self.env['res.partner'].search(shipment._fields[next(k for k in ROLES if k != field)].domain))

    def test_quality_menu_reuses_existing_action(self):
        action=self.env.ref('step_inventory_fruit_tag.action_fruit_quality')
        for name in ('export_quality','packing_quality'):
            self.assertEqual(self.env.ref('step_export_client_revision.'+name).action,action)
        self.assertEqual(self.env.ref('step_export_client_revision.export_color').action,
                         self.env.ref('step_export_client_revision.packing_color').action)

    def test_color_isolated_by_company(self):
        color=self.env['step.fruit.color'].create({'name':'QA Red','code':'QA_RED'})
        other=self.env['res.company'].create({'name':'QA other company'})
        foreign=self.env['step.fruit.color'].create({'name':'QA Other Red','code':'QA_RED','company_id':other.id})
        user=new_test_user(self.env,login='qa-client-color',groups='sales_team.group_sale_manager',company_id=self.env.company.id,company_ids=[(6,0,self.env.company.ids)])
        available=self.env['step.fruit.color'].with_user(user).with_context(allowed_company_ids=self.env.company.ids).search([])
        self.assertIn(color,available);self.assertNotIn(foreign,available)

    def test_sale_header_relations_and_english_titles(self):
        tree=etree.fromstring(self.env['sale.order'].get_view(view_type='form')['arch'].encode())
        self.assertEqual(len(tree.xpath(".//field[@name='incoterm']")),1)
        self.assertFalse(tree.xpath(".//page//field[@name='incoterm']"))
        self.assertTrue(tree.xpath(".//field[@name='step_export_sale_mode_id']"))
        self.assertEqual(self.env['sale.order']._step_export_report_title(False),'Sales Order')
        self.assertEqual(self.env['sale.order']._step_export_report_title(True),'Invoice')
