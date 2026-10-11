"""Inspect installed masters and Gantt support for T63-T67 without customer data."""
import importlib
from pathlib import Path

try:
    for model in ('step.export.sales.program', 'step.export.export', 'res.partner', 'step.management.fruit.quality'):
        print('MODEL', model, model in env)
        if model in env:
            print('RELEVANT_FIELDS', [(n,f.type,getattr(f,'comodel_name',None)) for n,f in env[model]._fields.items()
                  if any(s in n for s in ('transport','quality','color','step_export','carrier','consignee','notify','sale_mode'))])
    print('COLOR_MODELS', env['ir.model'].search([('model','ilike','color')]).mapped('model'))
    print('VERSIONS', [(m.name,m.latest_version,m.state) for m in env['ir.module.module'].search([('name','in',[
        'web_gantt','step_export','step_packing_operations','step_sale_export_report','step_management_costs_agriculture'])])])
    for action in env['ir.actions.act_window'].search([('name','ilike','Calidades de fruta')]):
        print('QUALITY_ACTION',action.get_external_id(),action.res_model)
    if env['ir.module.module'].search_count([('name','=','web_gantt'),('state','=','installed')]):
        root=Path(importlib.import_module('odoo.addons.web_gantt').__file__).parent
        for file in root.rglob('*.rng'):
            print('GANTT_SCHEMA',file.name,file.read_text()[:16000])
finally:
    env.cr.rollback()
