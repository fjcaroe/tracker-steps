"""Adopt the native packing process catalogue while leaving existing access and menus in place."""
from pathlib import Path

from lxml import etree

from odoo import models
from odoo.exceptions import ValidationError

OWNER = 'step_packing_process_catalog'
LEGACY = 'step_packing'
CATALOGS = ('step_packing_process_type', 'step_packing_process_type_tag')


def identity(env, namespace, name, record):
    xml_id = namespace + '.' + name
    previous = env.ref(xml_id, raise_if_not_found=False)
    if previous and previous != record:
        raise ValidationError('El identificador del catálogo ya pertenece a otro registro: ' + xml_id)
    if not previous:
        env['ir.model.data']._update_xmlids([{'xml_id': xml_id, 'record': record, 'noupdate': True}])


def shape(node):
    return node.tag, sorted(node.attrib.items()), (node.text or '').strip(), [shape(item) for item in node]


def resource(env, item):
    name, model = item.get('id'), item.get('model')
    values = {f.get('name'): (f[0] if f.get('name') == 'arch' else f.text) for f in item.findall('field')}
    record = env.ref(LEGACY + '.' + name, raise_if_not_found=False)
    if record:
        if record._name != model:
            raise ValidationError('Cambió el modelo de la vista o acción del catálogo.')
        original = record.with_context(lang='en_US')
        for key, expected in values.items():
            if key == 'arch':
                if shape(etree.fromstring(original.arch_db.encode())) != shape(expected):
                    raise ValidationError('Cambió la arquitectura original del catálogo: ' + name)
            elif original[key] != expected:
                raise ValidationError('Cambió la definición original del catálogo: ' + name + '.' + key)
        if model == 'ir.ui.view' and (not record.active or record.inherit_id or record.groups_id):
            raise ValidationError('Cambió el alcance de una vista base del catálogo.')
    else:
        if 'arch' in values:
            values['arch'] = etree.tostring(values['arch'], encoding='unicode')
        record = env[model].create(values)
    identity(env, OWNER, name, record)
    identity(env, LEGACY, name, record)


def adopt_catalog(env):
    data = env['ir.model.data']
    group = env.ref('base.group_user')
    for catalog in CATALOGS:
        name = catalog.replace('_', '.')
        model = env['ir.model']._get(name)
        identity(env, LEGACY, 'model_' + catalog, model)
        identity(env, OWNER, 'model_' + catalog, model)
        fields = data.search([('module', '=', OWNER), ('model', '=', 'ir.model.fields'),
                              ('name', '=like', 'field_' + catalog + '__%')])
        for entry in fields:
            field = env['ir.model.fields'].browse(entry.res_id)
            if field.model == name:
                identity(env, LEGACY, entry.name, field)
        access_name = 'access_' + catalog + '_user'
        access = env.ref(LEGACY + '.' + access_name, raise_if_not_found=False)
        if access:
            if (access._name != 'ir.model.access' or access.model_id != model or access.group_id != group
                    or not access.active or not access.perm_read or not access.perm_write or not access.perm_create or access.perm_unlink):
                raise ValidationError('Los permisos del catálogo histórico de tipos de proceso cambiaron.')
        else:
            access = env['ir.model.access'].create({'name': name + '.user', 'model_id': model.id, 'group_id': group.id,
                'perm_read': True, 'perm_write': True, 'perm_create': True, 'perm_unlink': False})
        identity(env, OWNER, access_name, access)
        identity(env, LEGACY, access_name, access)
        source = Path(__file__).parent / 'views' / (catalog + '_views.xml')
        for item in etree.parse(str(source), etree.XMLParser(resolve_entities=False)).getroot():
            resource(env, item)


class CatalogIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        return [*super()._step_retained_aliases(), (LEGACY, OWNER, None)]
