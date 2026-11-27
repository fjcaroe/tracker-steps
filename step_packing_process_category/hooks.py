from odoo.exceptions import ValidationError


def pre_init_hook(env):
    data = env['ir.model.data']
    field_name = 'field_step_packing_process_type__step_category'
    selections = {f'selection__step_packing_process_type__step_category__{value}': value
                  for value in ('selection', 'packing', 'correction')}
    records = data.search([('module', '=', 'step_packing_operations'),
                           ('name', 'in', [field_name, *selections])])
    if not records:
        return
    if len(records) != 4:
        raise ValidationError('La selección de procesos de packing de origen está incompleta.')
    field = env.ref('step_packing_operations.' + field_name)
    if field._name != 'ir.model.fields' or (field.model, field.name, field.ttype) != (
            'step.packing.process.type', 'step_category', 'selection'):
        raise ValidationError('El campo original de categoría de proceso cambió.')
    for entry in records:
        record = env[entry.model].browse(entry.res_id).exists()
        if entry.name in selections and (entry.model != 'ir.model.fields.selection'
                or record.field_id != field or record.value != selections[entry.name]):
            raise ValidationError('La opción original de categoría de proceso cambió.')
        xml_id = 'step_packing_process_category.' + entry.name
        existing = env.ref(xml_id, raise_if_not_found=False)
        if existing and existing != record:
            raise ValidationError('El identificador de la categoría de proceso está ocupado.')
        data._update_xmlids([{'xml_id': xml_id, 'record': record, 'noupdate': True}])
        if not entry.noupdate:
            entry.noupdate = True
