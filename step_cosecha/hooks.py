"""Retain the original warehouse harvest marker and both XML ID namespaces."""
from odoo.exceptions import UserError

FIELD_XMLID='field_stock_picking__cosecha'

def _bind(env,source,namespace):
    other=env['ir.model.data'].search([('module','=',namespace),('name','=',FIELD_XMLID)])
    if other:
        if len(other)!=1 or other.model!='ir.model.fields' or other.res_id!=source.res_id:
            raise UserError('Campo de Cosecha en conflicto: %s.%s' % (namespace,FIELD_XMLID))
    else:
        env['ir.model.data'].create({'module':namespace,'name':FIELD_XMLID,
            'model':'ir.model.fields','res_id':source.res_id,'noupdate':True})

def pre_init_hook(env):
    old=env['ir.model.data'].search([('module','=','step_hr'),('name','=',FIELD_XMLID)])
    if old:
        field=env['ir.model.fields'].browse(old.res_id).exists()
        if len(old)!=1 or old.model!='ir.model.fields' or not field or (field.model,field.name,field.ttype)!=('stock.picking','cosecha','boolean'):
            raise UserError('La bandera original de Cosecha no es compatible.')
        _bind(env,old,'step_cosecha');old.noupdate=True

def post_init_hook(env):
    current=env['ir.model.data'].search([('module','=','step_cosecha'),('name','=',FIELD_XMLID)])
    if len(current)!=1:
        raise UserError('Falta la bandera nativa de Cosecha.')
    _bind(env,current,'step_hr')
