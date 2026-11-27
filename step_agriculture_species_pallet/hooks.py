"""Adopt the original species fields and the same nonnegative PostgreSQL constraint."""
from odoo.exceptions import ValidationError

LEGACY = 'step_producer_fruit_reports'
CURRENT = 'step_agriculture_species_pallet'
CONSTRAINT = 'step_especie_base_boxes_per_pallet_nonnegative'


def pre_init_hook(env):
    data = env['ir.model.data']
    names = ('field_step_especie__sag_code', 'field_step_especie__base_boxes_per_pallet',
             'constraint_' + CONSTRAINT)
    old = data.search([('module', '=', LEGACY), ('name', 'in', names)])
    if not old:
        return
    if len(old) != len(names):
        raise ValidationError('El catálogo de especies tiene una adopción de origen incompleta.')
    target = env['ir.module.module'].search([('name', '=', CURRENT)])
    for alias in old:
        if alias.name.startswith('field_'):
            name = alias.name.split('__', 1)[1]
            record = env['ir.model.fields'].browse(alias.res_id).exists()
            if (alias.model != 'ir.model.fields' or record.model != 'step.especie' or record.name != name
                    or record.ttype != {'sag_code': 'char', 'base_boxes_per_pallet': 'float'}[name]):
                raise ValidationError('Campo de especie de origen incompatible: ' + name)
        else:
            record = env['ir.model.constraint'].browse(alias.res_id).exists()
            if (alias.model != 'ir.model.constraint' or record.name != CONSTRAINT or record.type != 'u'
                    or record.model.model != 'step.especie' or record.module.name not in (LEGACY, CURRENT)
                    or record.definition.lower() != 'check(base_boxes_per_pallet >= 0)'):
                raise ValidationError('La restricción original de cajas por pallet cambió.')
            # Odoo reflects constraints by (name,module). Move ownership before
            # reflection so the existing registry row and its SQL check survive.
            if record.module != target:
                record.module = target
        collision = env.ref(CURRENT + '.' + alias.name, raise_if_not_found=False)
        if collision and collision != record:
            raise ValidationError('El identificador de destino de la especie está ocupado.')
        data._update_xmlids([{'xml_id': CURRENT + '.' + alias.name, 'record': record, 'noupdate': True}])
