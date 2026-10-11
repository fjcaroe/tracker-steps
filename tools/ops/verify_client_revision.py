"""Exercise T63-T67 with real native forms/actions and roll back all samples."""
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval
from odoo.addons.step_export_client_revision.tests.test_revision import ClientRevisionCase
from odoo.addons.step_export_client_revision.models.revision import ROLES

try:
    for name, version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        runtime=importlib.import_module('odoo.addons.'+name)
        assert Path(runtime.__file__).resolve().parent==Path(ROOT)/name
    user=new_test_user(env,login='qa-t63-t67-client',groups='sales_team.group_sale_manager,sale.group_proforma_sales,stock.group_stock_manager')
    company=env.company
    ctx={'allowed_company_ids':company.ids,'tracking_disable':True,'mail_create_nosubscribe':True}
    quality=env.ref('step_inventory_fruit_tag.action_fruit_quality')
    for name,parent in [('export_quality','step_export.menu_step_export_config_fruit'),('packing_quality','step_packing_operations.menu_packing_config_fruit')]:
        menu=env.ref('step_export_client_revision.'+name)
        assert menu.action==quality and menu.parent_id==env.ref(parent)
        env[quality.res_model].with_user(user).search([],limit=1)
    color=env['step.fruit.color'].with_user(user).with_context(**ctx).create({'name':'QA COLOR ONLY','code':'QA_T63'})
    assert color in env['step.fruit.color'].with_user(user).with_context(**ctx).search([])
    for name in ('export_color','packing_color'):
        assert env.ref('step_export_client_revision.'+name).action==env.ref('step_export_client_revision.color_action')
    program=ClientRevisionCase.program(SimpleNamespace(env=env)).with_user(user)
    form=etree.fromstring(program.get_view(view_type='form')['arch'].encode())
    assert form.xpath(".//field[@name='company_id']/following-sibling::field[1][@name='transport_type']")
    program.action_validate();program.action_activate()
    action=env.ref('step_export_client_revision.program_report')
    assert action.view_mode=='gantt,pivot,list'
    lines=program.line_ids.with_user(user)
    for kind in ('gantt','pivot','list'):
        xmlid='step_export_client_revision.week_'+kind
        assert etree.fromstring(lines.get_view(view_id=env.ref(xmlid).id,view_type=kind)['arch'].encode()).tag==kind
    grouped=lines.read_group([('id','in',lines.ids)],['container_qty:sum','kg_qty:sum','amount_usd:sum'],[])[0]
    assert grouped['container_qty']==3 and grouped['kg_qty']==3000 and grouped['amount_usd']==10000
    new=env[program._name].browse(program.action_new_version()['res_id']);new.action_validate();new.action_activate()
    current=env['step.export.sales.program.line'].with_user(user).search([('program_id','in',[program.id,new.id]),('program_state','=','current')])
    assert len(current)==2 and set(current.program_id.ids)=={new.id}, 'Do not count replaced versions twice'
    values={'name':'QA ROLE INSTRUCTION','sales_program_id':new.id}
    for field,flag in ROLES.items():
        participant=env['res.partner'].create({'name':'QA ROLE '+flag,flag:True})
        values[field]=participant.id
    shipment=env['step.export.export'].with_user(user).with_context(**ctx).create(values)
    shipment_form=etree.fromstring(shipment.get_view(view_type='form')['arch'].encode())
    for field,flag in ROLES.items():
        domain=safe_eval(shipment_form.xpath(".//field[@name='%s']" % field)[0].get('domain'))
        assert shipment[field] in env['res.partner'].with_user(user).search(domain)
        assert program.partner_id not in env['res.partner'].with_user(user).search(domain)
    sale_mode=env['step.export.sale.mode'].create({'name':'QA MODALITY','company_id':company.id})
    order=env['sale.order'].with_user(user).with_context(**ctx).create({'partner_id':program.partner_id.id,
        'step_export_sale':True,'step_export_sale_mode_id':sale_mode.id,
        'incoterm':env['account.incoterms'].search([('code','=','FOB')],limit=1).id,
        'order_line':[(0,0,{'product_id':program.product_id.id,'product_uom_qty':2,'price_unit':50,'tax_id':[(5,0,0)]})]})
    sale_form=etree.fromstring(order.get_view(view_type='form')['arch'].encode())
    assert len(sale_form.xpath(".//field[@name='incoterm']"))==1
    assert not sale_form.xpath(".//page//field[@name='incoterm']")
    assert sale_form.xpath(".//field[@name='step_export_sale_mode_id']")
    for report,title in [('action_sale_note',b'Sales Order'),('action_proforma',b'Invoice')]:
        action=env.ref('step_sale_export_report.'+report).with_user(user)
        html,_=action._render_qweb_html(action.report_name,order.ids)
        assert title in html and b'QA fruit' in html
        pdf,_=action._render_qweb_pdf(action.report_name,order.ids)
        assert pdf.startswith(b'%PDF-')
        (Path(OUTPUT)/(report+'.pdf')).write_bytes(pdf)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'tickets':[63,64,65,66,67],
        'quality_shared':True,'color_crud':True,'program_transport':True,'gantt_pivot_list':True,
        'report_quantities_usd':10000,'current_version_only':True,'role_domains':True,
        'native_incoterm_and_sale_mode':True,'pdf_titles':['Sales Order','Invoice'],'samples':'rolled back'}),flush=True)
finally:
    env.cr.rollback()
