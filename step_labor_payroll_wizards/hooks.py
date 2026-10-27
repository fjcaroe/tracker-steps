"""Adopt existing metadata and SQL relation ownership; never copy business rows."""
from odoo.exceptions import UserError
from .ownership import CORE, LEGACY, MODELS, RECORDS, RELATIONS

def owned(env,row):
    if row.name in RECORDS:
        if row.model != RECORDS[row.name] or not env[row.model].browse(row.res_id).exists():
            raise UserError('Identificador incompatible: %s.%s' % (row.module,row.name))
        return True
    if row.model == 'ir.model.fields':
        return env[row.model].browse(row.res_id).model in MODELS
    if row.model == 'ir.model.fields.selection':
        return env[row.model].browse(row.res_id).field_id.model in MODELS
    return row.model == 'ir.model' and env[row.model].browse(row.res_id).model in MODELS

def alias(env,row,namespace):
    other=env['ir.model.data'].search([('module','=',namespace),('name','=',row.name)])
    if other:
        if len(other)!=1 or (other.model,other.res_id)!=(row.model,row.res_id):
            raise UserError('Identificador en conflicto: %s.%s' % (namespace,row.name))
    else:
        env['ir.model.data'].create({'module':namespace,'name':row.name,'model':row.model,
            'res_id':row.res_id,'noupdate': row.noupdate if namespace==CORE else True})

def pre_init_hook(env):
    modules=env['ir.module.module']
    target=modules.search([('name','=',CORE)])
    old=modules.search([('name','in',LEGACY)])
    env['ir.model.relation'].search([('module','in',old.ids),('name','in',RELATIONS)]).write({'module':target.id})
    for row in env['ir.model.data'].search([('module','in',LEGACY)]):
        if owned(env,row):
            alias(env,row,CORE)
            row.noupdate=True

def post_init_hook(env):
    for row in env['ir.model.data'].search([('module','=',CORE)]):
        if owned(env,row):
            for namespace in LEGACY:
                alias(env,row,namespace)
