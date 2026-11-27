"""Retire the unused sales-sheet extension from Steps forms when its provider is absent."""
import re


VIEWS = {
    'sale_order_template_view_form': (1443, 'sale.order.template', 'form', 1427),
    'sale_order_view_form': (1444, 'sale.order', 'form', 1384),
    'sale_order_spreadsheet_view_list': (1445, 'sale.order.spreadsheet', 'list', None),
    'sale_order_spreadsheet_view_search': (1446, 'sale.order.spreadsheet', 'search', None),
}
MODULE = 'spreadsheet_sale_management'
MENU = 'menu_technical_spreadsheet_sale_order_template'
ARCHITECTURES = {
    1443:'1d9768e0813f0dcd08772fd47d68e6b4a3d200dcec79a7a8b86b286aa4cca655',
    1444:'126f97ac76f393128f8baa32d14760807eb5c146d8174bde5f22161344da976e',
    1445:'fd52616b04053431c03c7397aeb1d02a76cd5c843a42962a753dd43803a07e1d',
    1446:'d9b9d061aabf8b56bda7c6917e80a41ac4b603236fbdcdd2bbe66ace3bb6e68c',
}


def prepare(cr):
    cr.execute('SELECT current_database()')
    database, = cr.fetchone()
    if not re.fullmatch(r'COMMUNITY_STEPS_CRM_QUOTE_[A-Z0-9_]+', database):
        raise ValueError('Use a new private copy dedicated to the Steps quotations.')
    cr.execute('SELECT name,state,license FROM ir_module_module WHERE name IN (%s,%s,%s) ORDER BY name FOR UPDATE',
               ['sale_management','sale_crm',MODULE])
    if cr.fetchall() != [('sale_crm','installed','LGPL-3'), ('sale_management','installed','LGPL-3'),
                         (MODULE,'uninstalled','OEEL-1')]:
        raise ValueError('The installed quotation providers differ from the qualified Steps configuration.')
    cr.execute("""SELECT (SELECT count(*) FROM sale_order_spreadsheet),
                         (SELECT count(*) FROM sale_order_template WHERE spreadsheet_template_id IS NOT NULL),
                         (SELECT count(*) FROM ir_attachment WHERE res_model='sale.order.spreadsheet'),
                         (SELECT count(*) FROM ir_module_module WHERE state='installed'),
                         (SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %')""")
    if cr.fetchone() != (0,0,0,157,0):
        raise ValueError('A stored workbook, a template assignment or an unexpected module needs review.')
    cr.execute("""SELECT x.name,v.id,v.model,v.type,v.inherit_id,v.active FROM ir_model_data x
                  JOIN ir_ui_view v ON v.id=x.res_id WHERE x.module=%s AND x.model='ir.ui.view' FOR UPDATE OF v""",
               [MODULE])
    views = cr.fetchall()
    if {name:(ident, model, kind, parent) for name,ident,model,kind,parent,_ in views} != VIEWS:
        raise ValueError('The original sales-sheet views changed.')
    cr.execute("""SELECT x.name,m.id,m.parent_id,m.action,m.active FROM ir_model_data x JOIN ir_ui_menu m ON m.id=x.res_id
                  WHERE x.module=%s AND x.model='ir.ui.menu' FOR UPDATE OF m""", [MODULE])
    menus = cr.fetchall()
    if len(menus) != 1 or menus[0][:4] != (MENU,329,233,'ir.actions.act_window,481'):
        raise ValueError('The original sales-sheet menu changed.')
    ids = [row[0] for row in VIEWS.values()]
    cr.execute("SELECT id,encode(sha256(convert_to(arch_db::text,'UTF8')),'hex') FROM ir_ui_view WHERE id=ANY(%s)", [ids])
    if dict(cr.fetchall()) != ARCHITECTURES:
        raise ValueError('The original sales-sheet interface has been edited.')
    cr.execute("""SELECT EXISTS(SELECT FROM ir_ui_view WHERE inherit_id=ANY(%s)),
                         EXISTS(SELECT FROM ir_ui_menu WHERE parent_id=329),
                         EXISTS(SELECT FROM ir_act_window a JOIN ir_model_data d ON d.res_id=a.id
                           WHERE a.id=481 AND a.res_model='sale.order.spreadsheet' AND d.model='ir.actions.act_window'
                             AND d.module=%s AND d.name='sale_order_spreadsheet_action')""", [ids,MODULE])
    if cr.fetchone() != (False,False,True):
        raise ValueError('Another view or route depends on the unavailable workbook interface.')
    flags = {row[-1] for row in views+menus}
    if len(flags) != 1:
        raise ValueError('The sales-sheet views and menu have inconsistent availability.')
    if flags == {True}:
        cr.execute('UPDATE ir_ui_view SET active=false WHERE id=ANY(%s) AND active', [ids])
        if cr.rowcount != len(ids):
            raise ValueError('The selected quotation views changed concurrently.')
        cr.execute('UPDATE ir_ui_menu SET active=false WHERE id=329 AND active')
        if cr.rowcount != 1:
            raise ValueError('The selected quotation menu changed concurrently.')
    return {'database':database, 'inactive_views':sorted(ids), 'inactive_menu':329,
            'stored_sales_workbooks':0, 'assigned_workbooks':0, 'original_action_retained':481}
