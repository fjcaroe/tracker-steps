"""Reuse the original view record and its source XML ID on opt-in Cerro packages."""
from pathlib import Path

from lxml import etree

from odoo.exceptions import ValidationError


def structure(node):
    return node.tag, sorted(node.attrib.items()), (node.text or '').strip(), [
        structure(child) for child in node
    ]


def adopt(env, module, module_file, legacy_names):
    source = Path(module_file).parent / 'views' / 'customizations.xml'
    definitions = etree.parse(str(source), etree.XMLParser(resolve_entities=False))
    records = definitions.xpath('/odoo/record[@model="ir.ui.view"]')
    if {node.get('id') for node in records} != set(legacy_names) or len(records) != len(legacy_names):
        raise ValidationError('La lista de vistas de Cerro no coincide con el paquete.')
    aliases = []
    for node in records:
        name = node.get('id')
        legacy = 'studio_customization.' + legacy_names[name]
        current = env.ref(legacy, raise_if_not_found=False)
        owned = env.ref(module + '.' + name, raise_if_not_found=False)
        if owned and owned != current:
            raise ValidationError(f'El identificador de la vista {name} ya está ocupado.')
        if not current:
            continue
        fields = {field.get('name'): field for field in node.findall('field')}
        arch = fields['arch'][0]
        original_arch = etree.fromstring(current.with_context(lang='en_US').arch_db.encode(),
                                         etree.XMLParser(resolve_entities=False))
        if (current._name != 'ir.ui.view' or current.model != fields['model'].text
                or current.name != fields['name'].text or not current.active or current.mode != 'extension'
                or current.inherit_id != env.ref(fields['inherit_id'].get('ref')) or current.type != current.inherit_id.type
                or current.priority != int(fields['priority'].text) or current.groups_id
                or structure(original_arch) != structure(arch)):
            raise ValidationError(f'La vista original {legacy} cambió. Revise su definición antes de adoptar.')
        aliases.append({'xml_id': module + '.' + name, 'record': current, 'noupdate': False})
    if aliases and len(aliases) != len(records):
        raise ValidationError('Faltan vistas originales del conjunto de Cerro.')
    if aliases:
        env['ir.model.data']._update_xmlids(aliases)
