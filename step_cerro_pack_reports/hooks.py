from odoo.exceptions import ValidationError

from . import models


OWNER='step_cerro_pack_reports'
OWNERS=('step_inventory_packing','step_packing_operations','step_packing_overweight',
        'step_export_document_revision','step_packing_ticket_revision')
CLASSES=(models.PackingOrder,models.PackingProduction,models.Downtime,models.FruitPackageLine)
SYSTEM_FIELDS={'id','display_name','create_uid','create_date','write_uid','write_date'}


def adopt_originals(env):
    if env['ir.module.module'].search_count([('name','in',list(OWNERS)),('state','in',['installed','to install','to upgrade'])]):
        raise ValidationError('Las consultas de Cerro requieren el perfil Community de Packing.')
    records=[]
    data=env['ir.model.data']
    def link(name,kind,record):
        if not record.exists():
            raise ValidationError('Falta una referencia original de Packing: '+name)
        owners=list(OWNERS)
        if kind=='ir.model.fields.selection' and '__activity_' in name:
            owners.append('mail')
        source=data.search([('module','in',owners),('name','=',name),('model','=',kind)])
        current=env.ref(OWNER+'.'+name,raise_if_not_found=False)
        if not source or set(source.mapped('res_id'))!={record.id} or (current and current!=record):
            raise ValidationError('Cambió el propietario original de '+name)
        records.append(dict(xml_id=OWNER+'.'+name,record=record,noupdate=True))

    def field(model,name):
        key=model.replace('.','_')
        record=env['ir.model.fields'].search([('model','=',model),('name','=',name)])
        link('field_'+key+'__'+name,'ir.model.fields',record)
        if record.ttype=='selection':
            for choice in env['ir.model.fields.selection'].search([('field_id','=',record.id)]):
                link('selection__'+key+'__'+name+'__'+choice.value.lower(),'ir.model.fields.selection',choice)

    for cls in CLASSES:
        name=cls._name
        record=env['ir.model']._get(name)
        link('model_'+name.replace('.','_'),'ir.model',record)
        names={item.name for item in cls._field_definitions}|SYSTEM_FIELDS
        if cls in (models.PackingOrder,models.PackingProduction):
            for mixin in ('mail.thread','mail.activity.mixin'):
                names.update(set(env[mixin]._fields) & set(env['ir.model.fields'].search([('model','=',name)]).mapped('name')))
        for key in sorted(names):
            field(name,key)
    for key in sorted(models.REPORT_FIELDS):
        field('stock.quant.package',key)
    data._update_xmlids(records)
