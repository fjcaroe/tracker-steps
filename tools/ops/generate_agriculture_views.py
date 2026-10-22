"""Generate static native forms, lists and ACLs for the reviewed legacy schema."""
import argparse
import csv
import io
import json
from pathlib import Path
import pprint
import runpy
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    addon = root / 'step_agriculture_records'
    schema = runpy.run_path(str(addon / 'schema.py'))
    mappings = runpy.run_path(str(addon / 'field_names.py'))['FIELDS']
    data = json.loads(args.inventory.read_text(encoding='utf-8'))
    models = schema['MODELS']
    excluded = {'id', 'display_name', 'create_date', 'create_uid', 'write_date', 'write_uid',
                'has_message', 'my_activity_date_deadline', 'rating_ids', 'website_message_ids',
                'consumption_line_ids', 'inventory_picking_id'}
    document = ET.Element('odoo')
    adoptions = {'access': {}, 'rules': {}}
    permission_rows = [['id','name','model_id:id','group_id:id','perm_read','perm_write','perm_create','perm_unlink']]
    for old_model, meta in data['models'].items():
        model = models[old_model]
        suffix = model.removeprefix('step.agriculture.')
        key = suffix.replace('.', '_')
        label = schema['LABELS'][suffix]
        fields = [f for f in meta['fields'] if f['name'] not in excluded
                  and not f['name'].startswith(('message_', 'activity_'))
                  and f['runtime_available']]
        names = {f['name']: mappings[old_model].get(f['name'], f['name']) for f in fields}
        fields.sort(key=lambda f: (names[f['name']] != 'name', names[f['name']]))
        by_name = {names[f['name']]: f for f in fields}
        if suffix == 'harvest.tag':
            by_name['tag_state_id'] = {'name': 'tag_state_id', 'ttype': 'many2one',
                'relation': 'step.packing.tag.state', 'field_description': 'Estado de tarja',
                'readonly': False, 'runtime_available': True}
        archive = suffix.startswith('archive.')

        def view(kind, arch):
            record = ET.SubElement(document, 'record', id='view_' + key + '_' + kind, model='ir.ui.view')
            ET.SubElement(record, 'field', name='name').text = model + '.' + kind
            ET.SubElement(record, 'field', name='model').text = model
            ET.SubElement(record, 'field', name='priority').text = '1'
            ET.SubElement(record, 'field', name='arch', type='xml').append(arch)

        tree = ET.Element('list', string=label)
        if archive:
            tree.attrib.update(create='0', edit='0', delete='0')
        visible = ['name', 'date', 'cost_center_id', 'fundo_id', 'state', 'company_id']
        for name, field in by_name.items():
            if field['ttype'] in ('one2many', 'many2many', 'html', 'text', 'binary'):
                continue
            ET.SubElement(tree, 'field', name=name, optional='show' if name in visible else 'hide')
        view('list', tree)
        form = ET.Element('form', string=label)
        if archive:
            form.attrib.update(create='0', edit='0', delete='0')
        header = ET.SubElement(form, 'header')
        if 'state' in by_name:
            ET.SubElement(header, 'field', name='state', widget='statusbar', options="{'clickable': True}")
        sheet = ET.SubElement(form, 'sheet')
        intro = ET.SubElement(sheet, 'div', {'class': 'o_step_bpa_record_intro'})
        ET.SubElement(intro, 'strong').text = label
        title = ET.SubElement(sheet, 'div', {'class': 'oe_title'})
        ET.SubElement(ET.SubElement(title, 'h1'), 'field', name='name')
        group = ET.SubElement(sheet, 'group')
        columns = [ET.SubElement(group, 'group'), ET.SubElement(group, 'group')]
        pages = []
        counter = 0
        for name, field in by_name.items():
            if name in ('name', 'state'):
                continue
            if field['ttype'] == 'one2many':
                pages.append((name, field))
            elif field['ttype'] in ('html', 'text'):
                pages.append((name, field))
            else:
                attrs = {'name': name}
                if field['ttype'] == 'many2many':
                    attrs['widget'] = 'many2many_tags'
                if name == 'legacy_tag_state_id':
                    attrs.update(readonly='1', string='Estado histórico de tarja', options="{'no_create': True}")
                ET.SubElement(columns[counter % 2], 'field', attrs)
                counter += 1
        if pages:
            book = ET.SubElement(sheet, 'notebook')
            for name, field in pages:
                relation = field['relation']
                page_label = (schema['LABELS'][models[relation].removeprefix('step.agriculture.')]
                              if relation in models else schema['FIELD_LABELS'].get(name, field['field_description']))
                page = ET.SubElement(book, 'page', name='page_' + name, string=page_label)
                entry = ET.SubElement(page, 'field', name=name, nolabel='1')
                if field['ttype'] == 'one2many' and relation in models and not field['readonly']:
                    rows = ET.SubElement(entry, 'list', editable='bottom')
                    if relation == 'x_registro_cosecha_line_7dde6':
                        ET.SubElement(rows, 'field', name='tag_state_id')
                    for child in data['models'][relation]['fields']:
                        child_name = mappings[relation].get(child['name'], child['name'])
                        if child['name'] in excluded or child['name'] == field['relation_field']:
                            continue
                        if child['name'].startswith(('message_', 'activity_')) or not child['runtime_available']:
                            continue
                        if child['ttype'] in ('one2many', 'many2many', 'html', 'text', 'binary'):
                            continue
                        attrs = {'name': child_name}
                        if child_name in ('legacy_tag_state_id', 'sequence') or child['readonly']:
                            attrs['optional'] = 'hide'
                        if child_name == 'legacy_tag_state_id':
                            attrs['readonly'] = '1'
                        ET.SubElement(rows, 'field', attrs)
        if meta['mail_thread']:
            ET.SubElement(form, 'chatter')
        view('form', form)
        search = ET.Element('search', string=label)
        for name in ('name', 'cost_center_id', 'fundo_id', 'company_id', 'state'):
            if name in by_name:
                ET.SubElement(search, 'field', name=name)
        for name in ('cost_center_id', 'fundo_id', 'state'):
            if name in by_name:
                ET.SubElement(search, 'filter', name='group_' + name, string=schema['FIELD_LABELS'].get(name, by_name[name]['field_description']),
                              context="{'group_by': '" + name + "'}")
        view('search', search)
        graph = ET.Element('graph', string=label)
        pivot = ET.Element('pivot', string=label)
        group_field = next((n for n in ('cost_center_id', 'fundo_id', 'state') if n in by_name), None)
        if group_field:
            ET.SubElement(graph, 'field', name=group_field)
            ET.SubElement(pivot, 'field', name=group_field, type='row')
        view('graph', graph)
        view('pivot', pivot)
        for index, access in enumerate(meta['access']):
            xmlid = 'access_' + key + '_' + str(index)
            assert access['xmlid'], (old_model, access['id'])
            adoptions['access'][access['xmlid']] = xmlid
            group = data['group_refs'].get(str(access['group_id'][0])) if access['group_id'] else ''
            assert group is not None, (old_model, access['group_id'])
            flags = [int(access[p]) for p in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink')]
            if archive:
                flags = [flags[0], 0, 0, 0]
            permission_rows.append([xmlid, label, 'model_' + model.replace('.', '_'), group, *flags])
        for index, rule in enumerate(meta['rules']):
            xmlid = 'rule_' + key + '_' + str(index)
            assert rule['xmlid']
            adoptions['rules'][rule['xmlid']] = xmlid
            # Domains are translated from explicit model fields, never guessed names.
            record = ET.SubElement(document, 'record', id=xmlid, model='ir.rule')
            ET.SubElement(record, 'field', name='name').text = rule['name']
            ET.SubElement(record, 'field', name='model_id', ref='model_' + model.replace('.', '_'))
            ET.SubElement(record, 'field', name='domain_force').text = schema['replace_tokens'](rule['domain_force'], mappings[old_model])
            groups = [data['group_refs'][str(ident)] for ident in rule['groups']]
            ET.SubElement(record, 'field', name='groups', eval='[(6, 0, [' +
                          ', '.join('ref(' + repr(group) + ')' for group in groups) + '])]')
            for perm in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink', 'active'):
                ET.SubElement(record, 'field', name=perm, eval=repr(rule[perm]))
    record = ET.SubElement(document, 'record', id='view_cost_center_activities', model='ir.ui.view')
    ET.SubElement(record, 'field', name='name').text = 'account.analytic.account.agricultural.activities'
    ET.SubElement(record, 'field', name='model').text = 'account.analytic.account'
    ET.SubElement(record, 'field', name='inherit_id', ref='step_hr.step_view_account_analytic_account_form')
    ET.SubElement(record, 'field', name='priority').text = '90'
    arch = ET.SubElement(record, 'field', name='arch', type='xml')
    xpath = ET.SubElement(arch, 'xpath', expr='//form/sheet/div[not(@name)][1]', position='before')
    box = ET.SubElement(xpath, 'div', name='button_box', **{'class': 'oe_button_box'})
    buttons = [('cost','Costos','gears'), ('forecast','Pronóstico cosecha','feed'),
               ('machinery','Maquinaria','group'), ('movement','Movilización','eject'),
               ('harvest','Cosecha','diamond'), ('irrigation','Riego','tint'),
               ('contractor','Contratistas','diamond'), ('own','Tarja propia','diamond'),
               ('foliar','Aplicación foliar','pause'), ('monitoring','Monitoreo','retweet'),
               ('monitoring','Plaga','diamond'), ('advisory','Asesoría','etsy'),
               ('inspection','Inspecciones','low-vision')]
    for key in dict.fromkeys(b[0] for b in buttons):
        ET.SubElement(box, 'field', name='agriculture_can_' + key, invisible='1')
    for key, label, icon in buttons:
        context = {'agriculture_activity': key}
        if label == 'Plaga':
            context['agriculture_pest_view'] = True
        button = ET.SubElement(box, 'button', name='action_agriculture_activity', type='object',
                               icon='fa-' + icon, context=repr(context),
                               invisible='not agriculture_can_' + key, **{'class': 'oe_stat_button'})
        ET.SubElement(button, 'field', name='agriculture_' + key + '_count', widget='statinfo', string=label)
    ET.indent(document)
    (addon / 'views').mkdir(exist_ok=True)
    ET.ElementTree(document).write(addon / 'views/documents.xml', encoding='utf-8', xml_declaration=True)
    (addon / 'security').mkdir(exist_ok=True)
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator='\n').writerows(permission_rows)
    (addon / 'security/ir.model.access.csv').write_text(stream.getvalue(), encoding='utf-8')
    (addon / 'adoption.py').write_text('"""Original external IDs adopted without replacing security records."""\nADOPTIONS = '
                                     + pprint.pformat(adoptions, sort_dicts=True, width=110) + '\n', encoding='utf-8')
    print('Generated complete native document views and preserved security')


if __name__ == '__main__':
    main()
