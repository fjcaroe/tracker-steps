"""Generate reviewable static declarations from a private audited schema.

This tool runs only during development. The addon never reads Studio metadata
to construct models, fields or forms at runtime.
"""
import argparse
import ast
import json
from pathlib import Path
import pprint
import re
import runpy
import unicodedata


def clean(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return re.sub('[^a-z0-9_]', '_', value.lower()).strip('_')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    addon = root / 'step_agriculture_records'
    schema = runpy.run_path(str(addon / 'schema.py'))
    models, common = schema['MODELS'], schema['COMMON_FIELDS']
    data = json.loads(args.inventory.read_text(encoding='utf-8'))
    assert set(models) == set(data['models']), 'Review newly discovered dependencies first'
    base_path = addon / 'models/bpa.py'
    original = (base_path if base_path.exists() else root / 'step_bpa_irrigation/models/bpa_native.py').read_text(encoding='utf-8')
    previous = runpy.run_path(str(addon / 'field_names.py'))['FIELDS'] if (addon / 'field_names.py').exists() else {}
    tree = ast.parse(original)
    base_fields = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            assignments = {a.targets[0].id: a.value for a in node.body
                           if isinstance(a, ast.Assign) and isinstance(a.targets[0], ast.Name)}
            name = ast.literal_eval(assignments['_name'])
            name = next((old for old, new in models.items() if new == name), name)
            inverse = {value: key for key, value in previous.get(name, {}).items()}
            base_fields[name] = {inverse.get(key, key) for key in assignments if not key.startswith('_')}
    mappings = {}
    for name, meta in data['models'].items():
        available = {f['name'] for f in meta['fields'] if not f['name'].startswith('x_')}
        mapping = {}
        for field in meta['fields']:
            old = field['name']
            if not old.startswith('x_'):
                continue
            new = common.get(old)
            if not new:
                assert not re.search(r'_(field|related_field)_', old), ('Name this field explicitly', name, old)
                new = clean(old.removeprefix('x_studio_').removeprefix('x_'))
                if field['ttype'] == 'many2one' and not new.endswith('_id'):
                    new += '_id'
                if field['ttype'] in ('one2many', 'many2many') and not new.endswith('_ids'):
                    new += '_ids'
            if new in available:
                new = 'legacy_' + new
            assert new not in available, (name, old, new)
            available.add(new)
            mapping[old] = new
        mappings[name] = mapping
    (addon / 'field_names.py').write_text(
        '"""Reviewed field renames; original IDs and columns are migrated in place."""\n'
        + 'FIELDS = ' + pprint.pformat(mappings, sort_dicts=True, width=110) + '\n', encoding='utf-8')
    global_fields = dict(common)
    for mapping in mappings.values():
        for old, new in mapping.items():
            global_fields.setdefault(old, new)
    replace = schema['replace_tokens']
    base_source = replace(replace(original, models), global_fields)
    # Existing masters also retain their Studio chatter/activity history.
    base_source = base_source.replace('_order = "name"', '_order = "name"')
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not any(isinstance(a, ast.Assign) and
                isinstance(a.targets[0], ast.Name) and a.targets[0].id == '_inherit' for a in node.body):
            base_source = base_source.replace('class ' + node.name + '(models.Model):',
                'class ' + node.name + '(models.Model):\n    _inherit = ["mail.thread", "mail.activity.mixin"]')
    (addon / 'models').mkdir(exist_ok=True)
    (addon / 'models/bpa.py').write_text(base_source, encoding='utf-8')
    lines = ['"""Static agricultural fields, preserving the audited types and relations."""',
             'from odoo import api, fields, models', '']
    for old_model, meta in data['models'].items():
        new_model = models[old_model]
        mapping = mappings[old_model]
        classname = ''.join(part.title() for part in new_model.split('.'))
        is_base = old_model in base_fields
        lines += ['', 'class ' + classname + '(models.Model):']
        if is_base:
            lines += ['    _inherit = ' + repr(new_model)]
        else:
            lines += ['    _name = ' + repr(new_model), '    _description = ' + repr(schema['LABELS'][new_model.removeprefix('step.agriculture.')]),
                      '    _rec_name = "name"', '    _order = ' + repr(replace(meta['order'], mapping))]
            inherit = []
            if meta['mail_thread']:
                inherit.append('mail.thread')
            if meta['mail_activity']:
                inherit.append('mail.activity.mixin')
            if inherit:
                lines += ['    _inherit = ' + repr(inherit)]
        if old_model in schema['SEQUENCES']:
            lines += ['    _folio_sequence = ' + repr(schema['SEQUENCES'][old_model])]
            if is_base:
                lines += ['    name = fields.Char(default="Nuevo", readonly=True, copy=False)']
        computes = []
        for field in meta['fields']:
            old = field['name']
            if not old.startswith('x_') or old in base_fields.get(old_model, set()):
                continue
            new = mapping[old]
            kind = field['ttype']
            kwargs = {'string': schema['FIELD_LABELS'].get(new, field['field_description']),
                      'required': field.get('runtime_required', field['required']),
                      'readonly': field.get('runtime_readonly', field['readonly']),
                      'copy': field['copied'], 'store': field.get('runtime_store', field['store'])}
            if field['help']:
                kwargs['help'] = field['help']
            if field.get('runtime_groups'):
                kwargs['groups'] = field['runtime_groups']
            if field.get('runtime_translate'):
                kwargs['translate'] = True
            if field['index']:
                kwargs['index'] = True
            if kind == 'many2one':
                kwargs['comodel_name'] = models.get(field['relation'], field['relation'])
                kwargs['ondelete'] = field['on_delete'] or 'set null'
            if kind in ('one2many', 'many2many'):
                kwargs['comodel_name'] = models.get(field['relation'], field['relation'])
            if kind == 'one2many' and not field['related']:
                inverse = field['relation_field']
                kwargs['inverse_name'] = mappings.get(field['relation'], {}).get(inverse, inverse)
            if kind == 'many2many' and not field['related']:
                kwargs.update(relation=field['relation_table'], column1=field['column1'], column2=field['column2'])
            if kind == 'selection':
                kwargs['selection'] = field['selection']
                if new == 'state' and field['selection']:
                    kwargs['default'] = field['selection'][0][0]
            if kind == 'monetary':
                kwargs['currency_field'] = mapping.get(field.get('currency_field'), field.get('currency_field', 'currency_id'))
            if field['domain'] and field['domain'] != '[]':
                kwargs['domain'] = replace(field['domain'], global_fields)
            if field['related'] and field['runtime_available']:
                kwargs['related'] = replace(field['related'], global_fields)
            elif field['compute']:
                method = '_compute_' + new
                kwargs['compute'] = method
                deps = [d.strip() for d in (field['depends'] or '').split(',') if d.strip()]
                code = replace(field['compute'].replace('\r\n', '\n'), global_fields)
                computes.append((method, [replace(d, global_fields) for d in deps], code))
            elif not field['runtime_available']:
                kwargs.update(compute='_compute_' + new, readonly=True, store=False, required=False)
                computes.append(('_compute_' + new, [], 'for record in self:\n    record[' + repr(new) + '] = False'))
            if new == 'name':
                kwargs['default'] = '__NEW_NAME__'
                if old_model in schema['SEQUENCES']:
                    kwargs.update(readonly=True, copy=False)
            if new == 'active':
                kwargs['default'] = True
            if new == 'legacy_tag_state_id':
                kwargs.update(readonly=True, copy=False, string='Estado histórico de tarja')
            if new == 'legacy_workflow_state':
                kwargs.update(readonly=True, copy=False, string='Estado anterior')
            constructor = {'many2one': 'Many2one', 'one2many': 'One2many',
                           'many2many': 'Many2many'}.get(kind, kind.title())
            rendered = ', '.join(k + '=' + ('"Nuevo"' if v == '__NEW_NAME__' else repr(v)) for k, v in kwargs.items())
            lines += ['    ' + new + ' = fields.' + constructor + '(' + rendered + ')']
        if old_model in schema['SEQUENCES']:
            lines += ['', '    @api.model_create_multi', '    def create(self, values_list):',
                      '        for values in values_list:',
                      '            values["name"] = self.env["ir.sequence"].next_by_code(self._folio_sequence) or "/"',
                      '        return super().create(values_list)']
        for method, deps, code in computes:
            lines += ['', '    @api.depends(' + ', '.join(repr(d) for d in deps) + ')', '    def ' + method + '(self):']
            # Normalize inconsistent Studio indentation into a real Python method.
            normalized = ast.unparse(ast.parse(code))
            if method == '_compute_maquinadas':
                normalized = normalized.replace('/ record.capacidad_lts_aplicadora',
                    '/ record.capacidad_lts_aplicadora if record.capacidad_lts_aplicadora else 0.0')
            lines += ['        ' + line for line in normalized.splitlines()]
        lines += ['']
    (addon / 'models/documents.py').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Generated static native declarations for', len(models), 'models; review before commit')


if __name__ == '__main__':
    main()
