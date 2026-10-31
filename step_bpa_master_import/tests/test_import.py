import io
from pathlib import Path
import zipfile
from lxml import etree
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.safe_eval import safe_eval


def workbook_row(filename, values):
    """Fill the shipped, empty XLSX template with an isolated test row."""
    target = io.BytesIO()
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(filename) as source, zipfile.ZipFile(target, 'w') as dest:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if entry.filename == 'xl/worksheets/sheet1.xml':
                root = etree.fromstring(data)
                sheet = root.find('{%s}sheetData' % ns)
                for row in list(sheet):
                    if int(row.get('r')) > 1:
                        sheet.remove(row)
                row = etree.SubElement(sheet, '{%s}row' % ns, r='2')
                for index, value in enumerate(values):
                    cell = etree.SubElement(row, '{%s}c' % ns, r=chr(65+index)+'2', t='inlineStr')
                    etree.SubElement(etree.SubElement(cell, '{%s}is' % ns), '{%s}t' % ns).text = value
                data = etree.tostring(root)
            dest.writestr(entry, data)
    return target.getvalue()


@tagged('post_install', '-at_install')
class ImportCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)),
                                 login='private-t146-import', groups='base.group_user,stock.group_stock_manager')
        cls.scope = cls.env(user=cls.user, su=False)

    def do_import(self, model, fields, values, dryrun=False):
        template = self.scope[model].get_import_templates()[0]['template']
        filename = Path(__file__).resolve().parents[1]/'static/xlsx'/Path(template).name
        wizard = self.scope['base_import.import'].create({
            'res_model': model, 'file': workbook_row(filename, values),
            'file_name': filename.name,
            'file_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        result = wizard.execute_import(fields, fields, {'has_headers': True, 'keep_matches': False}, dryrun=dryrun)
        self.assertFalse([m for m in result.get('messages', []) if m['type']=='error'], result)
        return result

    def test_substance_xlsx_dry_run_create_update_archive(self):
        model = 'step.agriculture.active.ingredient'
        fields = ['name','cdigo','observacin','active','id']
        row = ['Private T146 substance','00394','Observación áéí','True','private_t146.substance']
        self.do_import(model, fields, row, dryrun=True)
        self.assertFalse(self.env.ref('private_t146.substance', raise_if_not_found=False))
        self.do_import(model, fields, row)
        item = self.env.ref('private_t146.substance')
        self.assertEqual(item.cdigo,'00394')
        self.assertIn('Observación áéí',item.observacin)
        self.assertTrue(item.active)
        row[2]='Observación corregida'; row[3]='False'
        self.do_import(model, fields, row)
        self.assertEqual(self.env.ref('private_t146.substance').id,item.id)
        self.assertFalse(item.active)
        self.assertIn('corregida',item.observacin)

    def test_aptitude_xlsx_updates_native_product_relation(self):
        model = 'step.agriculture.pesticide.aptitude'
        fields = ['name','code','notes','id']
        row = ['Private T146 aptitude','0013','Observación de prueba','private_t146.aptitude']
        self.do_import(model, fields, row)
        item = self.env.ref('private_t146.aptitude')
        product = self.scope['product.template'].create({'name':'Private T146 product','is_bpa':True,'registration_aptitude_id':item.id})
        row[2]='Observación actualizada'
        self.do_import(model, fields, row)
        self.assertEqual(product.registration_aptitude_id.id,item.id)
        self.assertEqual(item.code,'0013')
        self.assertIn('actualizada',item.notes)

    def test_products_menu_filters_existing_bpa_flag_and_defaults_create(self):
        action=self.scope.ref('step_bpa_master_import.action_bpa_products')
        domain=safe_eval(action.domain)
        product=self.scope['product.template'].create({'name':'Private T146 BPA','is_bpa':True})
        other=self.scope['product.template'].create({'name':'Private T146 ordinary','is_bpa':False})
        found=self.scope['product.template'].search(domain+[('id','in',(product|other).ids)])
        self.assertEqual(found,product)
        self.assertTrue(safe_eval(action.context)['default_is_bpa'])

    def test_native_menus_list_form_and_import_permissions(self):
        visible=self.scope['ir.ui.menu']._visible_menu_ids()
        for menu in ('step_bpa_master_import.menu_bpa_products','step_bpa_master_import.menu_bpa_active_ingredients','step_product_bpa.menu_aptitudes'):
            self.assertIn(self.scope.ref(menu).id,visible)
        self.assertEqual(self.scope.ref('step_product_bpa.menu_aptitudes').parent_id,
                         self.scope.ref('step_bpa_master_import.menu_bpa_configuration'))
        for model,fields in [('step.agriculture.active.ingredient',('name','cdigo','observacin','active')),
                             ('step.agriculture.pesticide.aptitude',('name','code','notes'))]:
            self.scope[model].check_access('create')
            self.scope[model].check_access('write')
            for kind in ('list','form'):
                arch=etree.fromstring(self.scope[model].get_view(view_type=kind)['arch'])
                self.assertNotEqual(arch.get('import'),'0')
                self.assertNotEqual(arch.get('create'),'0')
                for field in fields:
                    self.assertTrue(arch.xpath("//field[@name='%s']" % field))

    def test_existing_substance_product_relation_survives_native_update(self):
        model='step.agriculture.active.ingredient'
        fields=['name','cdigo','observacin','active','id']
        row=['Private T146 linked','0001','Inicial','True','private_t146.linked']
        self.do_import(model,fields,row)
        item=self.env.ref('private_t146.linked')
        product=self.scope['product.template'].create({'name':'Private T146 linked product','is_bpa':True,'agriculture_active_ingredient_id':item.id})
        row[2]='Actualizada'
        self.do_import(model,fields,row)
        self.assertEqual(product.agriculture_active_ingredient_id,item)
        self.assertEqual(item.cdigo,'0001')
        self.assertIn('Actualizada',item.observacin)
