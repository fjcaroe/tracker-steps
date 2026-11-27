from odoo.exceptions import ValidationError
from .bindings import BASE_MODELS, FIELDS, SOURCES

OWNER = 'step_cerro_receipt_flow'
SYSTEM = {'id', 'display_name', 'create_uid', 'create_date', 'write_uid', 'write_date'}


def adopt_originals(env):
    data = env['ir.model.data']
    if env['ir.module.module'].search_count([('name','in',list(SOURCES)),('state','in',['installed','to install','to upgrade'])]):
        raise ValidationError('Hay otro proveedor activo de la recepción agrícola.')
    aliases = {}

    def add(record, name):
        originals = data.search([('name','=',name),('model','=',record._name),
                                 ('module','in',list(SOURCES) + ['mail','base'])])
        old = env.ref(OWNER+'.'+name, raise_if_not_found=False)
        if len(record) != 1 or not originals or set(originals.mapped('res_id')) != {record.id} or (old and old != record):
            raise ValidationError('Cambió la identidad de recepción '+name)
        aliases[name] = dict(xml_id=OWNER+'.'+name,record=record,noupdate=True)

    fields_by_model = {name:set(fields) for name, fields in FIELDS.items()}
    for model, mixins in BASE_MODELS.items():
        add(env['ir.model']._get(model),'model_'+model.replace('.','_'))
        names = fields_by_model.setdefault(model,set())
        names.update(SYSTEM)
        for mixin in mixins:
            original = env['ir.model.fields'].search([('model','=',model)]).mapped('name')
            names.update(set(original).intersection(env[mixin]._fields))

    for model,names in fields_by_model.items():
        prefix = model.replace('.','_')
        for name in sorted(names):
            record=env['ir.model.fields'].search([('model','=',model),('name','=',name)])
            add(record,'field_'+prefix+'__'+name)
            if record.ttype=='selection':
                for choice in env['ir.model.fields.selection'].search([('field_id','=',record.id)]):
                    add(choice,'selection__'+prefix+'__'+name+'__'+choice.value.lower())
    data._update_xmlids(list(aliases.values()))
