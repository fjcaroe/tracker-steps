"""Odoo shell: identify exact inherited layout/employee mistakes, no data rows."""
import json
from lxml import etree

try:
    for view in env['ir.ui.view'].search([('active','=',True)]):
        arch=view.with_context(lang=None).arch_db or ''
        if (view.type=='qweb' and 'doc.x_' in arch) or (view.model=='hr.employee' and 'employee_id' in arch and 'step_work_schedule' in arch):
            print('VIEW_OVERRIDE '+json.dumps({'id':view.id,'name':view.name,'xmlid':view.get_external_id().get(view.id),'inherit':view.inherit_id.id,'arch':arch},ensure_ascii=False))
    print('PROBE_ROLLBACK_OK')
finally: env.cr.rollback()
