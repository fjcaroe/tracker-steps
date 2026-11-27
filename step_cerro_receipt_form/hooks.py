from odoo.exceptions import ValidationError

from . import models

OWNER='step_cerro_receipt_form'
SOURCES=('quality','quality_control','l10n_cl_edi_stock','step_packing_interplant','step_dispatch_guide',
         'step_harvest_container_control','step_packing_reception_revision')


def adopt_originals(env):
    if env['ir.module.module'].search_count([('name','in',SOURCES),('state','in',('installed','to install','to upgrade'))]):
        raise ValidationError('Hay otro proveedor activo del detalle de la recepción.')
    data=env['ir.model.data']
    aliases={}
    def add(row,xml):
        if len(row)!=1:
            raise ValidationError('No se encontró la referencia histórica '+xml)
        origins=data.search([('module','in',(*SOURCES,'mail','base')),('name','=',xml),('model','=',row._name)])
        previous=env.ref(OWNER+'.'+xml,raise_if_not_found=False)
        if set(origins.mapped('res_id'))!={row.id} or (previous and previous!=row):
            raise ValidationError('Cambió la referencia histórica '+xml)
        aliases[xml]=dict(xml_id=OWNER+'.'+xml,record=row,noupdate=True)
    for cls in (models.Guide,models.ContainerOrder,models.Point,models.Check,models.Alert,models.Picking,models.Package):
        model=cls.__dict__.get('_name') or cls._inherit
        prefix=model.replace('.','_')
        names={field.name for field in cls._field_definitions}
        if cls not in (models.Picking,models.Package):
            add(env['ir.model']._get(model),'model_'+prefix)
            names.update({'id','display_name','create_uid','create_date','write_uid','write_date'})
            existing=set(env['ir.model.fields'].search([('model','=',model)]).mapped('name'))
            for base in cls.__dict__.get('_inherit',[]):
                names.update(set(env[base]._fields)&existing)
        for name in sorted(names):
            row=env['ir.model.fields'].search([('model','=',model),('name','=',name)])
            add(row,'field_'+prefix+'__'+name)
            if row.ttype=='selection':
                for option in env['ir.model.fields.selection'].search([('field_id','=',row.id)]):
                    add(option,'selection__'+prefix+'__'+name+'__'+option.value.lower())
    data._update_xmlids(list(aliases.values()))
