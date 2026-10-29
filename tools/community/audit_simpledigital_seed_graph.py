"""Static XML/CSV seed references only; never export values or evaluate code."""
import argparse
import ast
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re

from lxml import etree


SALARY_MODELS = {'hr.salary.rule', 'hr.salary.rule.category', 'hr.payroll.structure',
                 'hr.payroll.structure.type', 'hr.payslip.input.type'}
IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_.-]*\Z')
PLACEHOLDER = re.compile(r'%\(([A-Za-z_][A-Za-z0-9_.-]*)\)[ds]')


def canonical(value, module):
    assert isinstance(value, str) and IDENT.fullmatch(value), 'Non-static XML identifier'
    return value if '.' in value else module + '.' + value


def relative(value):
    p = PurePosixPath(value)
    assert not p.is_absolute() and '..' not in p.parts and str(p) == value and '\\' not in value
    return value


def location(node, filename, module):
    owners = [item for item in (node, *node.iterancestors()) if item.get('id')
        and etree.QName(item).localname in ('record', 'template', 'menuitem', 'act_window', 'report')]
    fields = [item for item in (node, *node.iterancestors()) if etree.QName(item).localname == 'field']
    return {'file': filename, 'line': node.sourceline,
        'owner': canonical(owners[0].get('id'), module) if owners else None,
        'field': fields[0].get('name') if fields else None}


def expression_refs(value, module):
    """Read literal ref() arguments from AST, including QWeb, without eval."""
    try:
        tree = ast.parse(value, mode='eval')
    except (SyntaxError, ValueError):
        return [], bool(re.search(r'\bref\s*\(', value))
    refs, dynamic = [], False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_ref = isinstance(node.func, ast.Name) and node.func.id == 'ref'
        is_ref |= isinstance(node.func, ast.Attribute) and node.func.attr == 'ref'
        if not is_ref:
            continue
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            refs.append(canonical(node.args[0].value, module))
        else:
            dynamic = True
    return refs, dynamic


def scan_xml(content, filename, module):
    assert b'\x00' not in content and not re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', content, re.I), 'DTD/entity XML refused'
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True, remove_comments=True, huge_tree=False)
    try:
        root = etree.fromstring(content, parser=parser)
    except etree.XMLSyntaxError:
        raise ValueError('Invalid provider XML; body withheld') from None
    definitions, refs, dynamic, functions = [], [], [], []
    models = {'record': None, 'template': 'ir.ui.view', 'menuitem': 'ir.ui.menu',
              'act_window': 'ir.actions.act_window', 'report': 'ir.actions.report'}
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        tag = etree.QName(node).localname
        place = location(node, filename, module)
        if tag in models and node.get('id'):
            ident = canonical(node.get('id'), module)
            definitions.append(dict(place, xmlid=ident, model=node.get('model') or models[tag],
                external_target=not ident.startswith(module + '.'), forcecreate=node.get('forcecreate', 'true')))
        if tag in ('function', 'delete'):
            functions.append(dict(place, kind=tag, model=node.get('model'), method=node.get('name'),
                has_search_domain=node.get('search') is not None))
        for attribute, value in node.attrib.items():
            targets, kind = [], 'loader'
            if attribute == 'ref':
                targets = [canonical(value, module)]
            elif attribute == 'groups':
                targets = [canonical(item.strip().lstrip('!'), module) for item in value.split(',') if item.strip()]
            elif attribute in ('parent', 'action', 'inherit_id'):
                if IDENT.fullmatch(value): targets = [canonical(value, module)]
            elif attribute == 't-call':
                kind = 'runtime-template'
                if IDENT.fullmatch(value): targets = [canonical(value, module)]
                else: dynamic.append(dict(place, attribute=attribute, kind=kind))
            elif attribute == 'eval' or attribute.startswith('t-'):
                kind = 'loader-eval' if attribute == 'eval' else 'runtime-expression'
                targets, unknown = expression_refs(value, module)
                if unknown: dynamic.append(dict(place, attribute=attribute, kind=kind))
            for target in targets + [canonical(item, module) for item in PLACEHOLDER.findall(value)]:
                refs.append(dict(place, attribute=attribute, kind=kind, target=target))
    return {'definitions': definitions, 'refs': refs, 'dynamic_refs': dynamic, 'side_effect_nodes': functions}


def scan_csv(content, filename, module):
    definitions, refs = [], []
    for line, row in enumerate(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))), 2):
        owner = canonical(row['id'], module) if row.get('id') else None
        if owner: definitions.append({'file': filename, 'line': line, 'owner': owner, 'field': None,
            'xmlid': owner, 'model': filename.split('/')[-1].split('.csv')[0], 'external_target': not owner.startswith(module + '.'), 'forcecreate': 'true'})
        for field, value in row.items():
            if field and field.endswith(':id') and value:
                refs.append({'file': filename, 'line': line, 'owner': owner, 'field': field,
                    'attribute': field, 'kind': 'loader-csv', 'target': canonical(value, module)})
    return {'definitions': definitions, 'refs': refs, 'dynamic_refs': [], 'side_effect_nodes': []}


def analyze_addon(addon, *, omit=(), allowed_files=None, approved_external=()):
    addon = Path(addon)
    module = addon.name
    manifest = ast.literal_eval((addon / '__manifest__.py').read_text(encoding='utf-8-sig'))
    assert manifest.get('license') in ('AGPL-3', 'LGPL-3', 'GPL-3'), 'Free provider required; no Enterprise source inspection'
    loaded = [relative(name) for name in manifest.get('data', [])]
    omitted = {relative(name) for name in omit}
    assert len(loaded) == len(set(loaded)), 'Duplicate manifest data file'
    files = {}
    for name in dict.fromkeys([*loaded, *sorted(omitted)]):
        assert allowed_files is None or name in allowed_files, 'Non-runtime file refused'
        path = addon / name
        assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(addon.resolve())
        content = path.read_bytes()
        if name.endswith('.xml'): data = scan_xml(content, name, module)
        elif name.endswith('.csv'): data = scan_csv(content, name, module)
        else: raise ValueError('Unsupported data loader file; no body exported')
        files[name] = dict(data, sha256=hashlib.sha256(content).hexdigest(), loaded=name in loaded and name not in omitted)
    all_definitions = {row['xmlid'] for data in files.values() for row in data['definitions']}
    retained = [name for name in loaded if name not in omitted]
    retained_definitions = {row['xmlid'] for name in retained for row in files[name]['definitions']}
    removed = all_definitions - retained_definitions
    available, references = set(approved_external), []
    for name in retained:
        for row in files[name]['refs']:
            target = row['target']
            if target in available: status = 'available-before-file'
            elif target in removed: status = 'removed-seed-reference'
            elif target in retained_definitions: status = 'same-or-later-file-definition'
            elif target.startswith(module + '.model_'): status = 'implicit-model-id-requires-registry'
            elif target.startswith(module + '.'): status = 'missing-provider-definition'
            else: status = 'external-requires-real-bootstrap'
            references.append(dict(row, resolution=status))
        available.update(row['xmlid'] for row in files[name]['definitions'])
    salary = [row for name in retained for row in files[name]['definitions'] if row['model'] in SALARY_MODELS]
    return {'schema': 1, 'read_only_files_only': True, 'orm_loaded': False, 'database_queried': False,
        'formula_bodies_exported': False, 'values_exported': False, 'module': module, 'license': manifest['license'],
        'manifest_sha256': hashlib.sha256((addon / '__manifest__.py').read_bytes()).hexdigest(),
        'data_order': loaded, 'omitted_files': sorted(omitted), 'demo_files_not_loaded': manifest.get('demo', []),
        'files': files, 'references': references, 'removed_xmlids': sorted(removed),
        'removed_seed_blockers': [row for row in references if row['resolution'] == 'removed-seed-reference'],
        'remaining_salary_master_records': salary, 'external_requirements': sorted({row['target'] for row in references if row['resolution'] in ('external-requires-real-bootstrap', 'implicit-model-id-requires-registry')}),
        'runtime_or_loader_dynamic_refs': [row for name in retained for row in files[name]['dynamic_refs']],
        'side_effect_nodes': [row for name in retained for row in files[name]['side_effect_nodes']],
        'bootstrap_certified': False, 'identity_adopted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--pin', type=Path, required=True)
    parser.add_argument('--verify-source-pin', action='store_true')
    parser.add_argument('--omit', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pin = json.loads(args.pin.read_text())
    assert pin['license'] == 'AGPL-3' and len(pin['files']) == 52
    if args.verify_source_pin:
        assert all(hashlib.sha256((args.addon / relative(name)).read_bytes()).hexdigest() == value for name, value in pin['files'].items()), 'Original runtime pin mismatch'
    output = args.output.resolve()
    assert Path('/opt/steps-validation') in output.parents and not output.exists()
    report = analyze_addon(args.addon, omit=args.omit, allowed_files=set(pin['files']))
    report.update(tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), source_pin_sha256=hashlib.sha256(args.pin.read_bytes()).hexdigest(), original_pin_verified=args.verify_source_pin)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'removed_seed_blockers': len(report['removed_seed_blockers']),
        'remaining_salary_master_records': len(report['remaining_salary_master_records']), 'external_requirements': len(report['external_requirements']), 'bootstrap_certified': False}))


if __name__ == '__main__':
    main()
