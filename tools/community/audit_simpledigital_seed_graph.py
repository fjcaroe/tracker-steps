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
MODULE = 'l10n_cl_simpledigital_payroll'
SALARY_SEED_FILES = ('data/hr_salary_rule.xml', 'data/hr_salary_structure.xml')
MOVEMENT_SEED_FILE = 'data/hr_employee_movement.xml'
BOOTSTRAP_SEED_FILES = (*SALARY_SEED_FILES, MOVEMENT_SEED_FILE)
DEFER_FILE = 'data/hr_work_entry_type.xml'
DEFER_OWNER = MODULE + '.work_entry_type_unpaid_cl'
DEFER_TARGET = MODULE + '.structure_chile'


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


def verify_bootstrap_profile(normal_addon, profile_addon, *, allowed_files):
    """Prove three omitted seeds and one deferred assignment, never waive a ref.

    This is an independent XML/CSV audit. The builder additionally proves
    mandatory dependency/Python reference closure; actual registry installation
    and the original configuration remain separate acceptance gates.
    """
    normal_addon, profile_addon = Path(normal_addon), Path(profile_addon)
    assert normal_addon.name == profile_addon.name == MODULE, 'Provider identity drift'
    # License metadata is admitted before reading any runtime body from either
    # root, including a mistaken Enterprise directory supplied by the caller.
    for folder in (normal_addon, profile_addon):
        path = folder / '__manifest__.py'
        assert not path.is_symlink(), 'Symlink provider manifest'
        declaration = ast.literal_eval(path.read_text(encoding='utf-8-sig'))
        assert declaration.get('license') == 'AGPL-3', 'Free provider required'

    def snapshot(folder):
        files = {}
        for path in folder.rglob('*'):
            assert not path.is_symlink(), 'Symlink in provider snapshot'
            if not path.is_file():
                continue
            name = relative(path.relative_to(folder).as_posix())
            assert name in allowed_files, 'Unexpected provider runtime file'
            files[name] = path.read_bytes()
        return files

    normal, profile = snapshot(normal_addon), snapshot(profile_addon)
    assert set(normal) == set(allowed_files), 'Incomplete normal runtime snapshot'
    assert set(profile) == set(normal) - set(BOOTSTRAP_SEED_FILES), 'Only the three approved seed files may disappear'
    normal_manifest = ast.literal_eval(normal['__manifest__.py'].decode('utf-8-sig'))
    profile_manifest = ast.literal_eval(profile['__manifest__.py'].decode('utf-8-sig'))
    assert normal_manifest.get('license') == 'AGPL-3', 'Free provider required'
    assert normal_manifest.get('depends') == ['step_simpledigital_oca_base'], 'Normal provider dependency drift'
    assert not normal_manifest.get('demo'), 'Provider demo is not authorized'
    assert all(normal_manifest.get('data', []).count(name) == 1 for name in BOOTSTRAP_SEED_FILES), 'Approved seed list drift'
    expected_manifest = dict(normal_manifest,
        data=[name for name in normal_manifest['data'] if name not in BOOTSTRAP_SEED_FILES])
    assert profile_manifest == expected_manifest, 'Unexpected profile manifest change'
    assert normal_manifest['data'].count(DEFER_FILE) == 1, 'Deferred type loader drift'

    baseline = analyze_addon(normal_addon, omit=BOOTSTRAP_SEED_FILES, allowed_files=allowed_files)
    expected_edge = {'file': DEFER_FILE, 'owner': DEFER_OWNER, 'field': 'unpaid_structure_ids',
        'attribute': 'eval', 'kind': 'loader-eval', 'target': DEFER_TARGET, 'resolution': 'removed-seed-reference'}
    assert len(baseline['removed_seed_blockers']) == 1, 'Unexpected omitted seed reference'
    edge = baseline['removed_seed_blockers'][0]
    assert all(edge[key] == value for key, value in expected_edge.items()), 'Deferred reference identity drift'
    # Safe parser already admitted this exact source in analyze_addon. Inspect
    # only the approved field's attributes; never evaluate its expression.
    tree = etree.fromstring(normal[DEFER_FILE], parser=etree.XMLParser(
        resolve_entities=False, load_dtd=False, no_network=True, remove_comments=True))
    owners = [node for node in tree.iter('record') if node.get('id')
        and canonical(node.get('id'), MODULE) == DEFER_OWNER]
    assert len(owners) == 1 and owners[0].get('model') == 'hr.work.entry.type', 'Deferred field owner drift'
    fields = [node for node in owners[0].findall('field') if node.get('name') == 'unpaid_structure_ids']
    assert len(fields) == 1 and set(fields[0].attrib) == {'name', 'eval'}, 'Deferred assignment drift'
    expected_expression = ast.dump(ast.parse("[(4, ref(%r))]" % DEFER_TARGET, mode='eval'))
    assert ast.dump(ast.parse(fields[0].get('eval'), mode='eval')) == expected_expression, 'Deferred expression drift'
    spans = list(re.finditer(rb'<field\b[^>]*\bname=[\"\']unpaid_structure_ids[\"\'][^>]*/>', normal[DEFER_FILE]))
    assert len(spans) == 1, 'Ambiguous deferred field byte span'
    span = spans[0]
    assert profile[DEFER_FILE] == normal[DEFER_FILE][:span.start()] + normal[DEFER_FILE][span.end():], 'Deferred field bytes changed beyond one assignment'
    assert all(profile[name] == value for name, value in normal.items()
        if name not in (*BOOTSTRAP_SEED_FILES, DEFER_FILE, '__manifest__.py')), 'Unexpected provider runtime modification'

    graph = analyze_addon(profile_addon, allowed_files=allowed_files)
    assert not graph['remaining_salary_master_records'], 'Profile still creates salary masters'
    removed = set(baseline['removed_xmlids'])
    assert DEFER_TARGET in removed, 'Deferred target is not an omitted salary seed'
    orphans = [row for row in graph['references'] if row['target'] in removed
        or row['resolution'] in ('removed-seed-reference', 'missing-provider-definition')]
    assert not orphans, 'Profile has another unresolved provider reference'
    assert not graph['side_effect_nodes'], 'Unexpected loader side effects'
    movements = baseline['files'][MOVEMENT_SEED_FILE]['definitions']
    movement_models = {'hr.employee.movement.type', 'hr.employee.hr.event.type'}
    assert movements and all(row['model'] in movement_models for row in movements), 'Movement catalog identity drift'
    salary_xmlids = {row['xmlid'] for name in SALARY_SEED_FILES
        for row in baseline['files'][name]['definitions']}
    graph.update(schema=3, profile='original-bootstrap-without-salary-seeds',
        normal_manifest_sha256=hashlib.sha256(normal['__manifest__.py']).hexdigest(),
        omitted_seed_files=list(BOOTSTRAP_SEED_FILES), omitted_provider_xmlids=sorted(removed),
        omitted_salary_seed_files=list(SALARY_SEED_FILES), omitted_salary_xmlids=sorted(salary_xmlids),
        deferred_movement_catalog={
            'file': MOVEMENT_SEED_FILE,
            'original_file_sha256': hashlib.sha256(normal[MOVEMENT_SEED_FILE]).hexdigest(),
            'definitions': [{'xmlid': row['xmlid'], 'model': row['model']} for row in movements],
            'model_counts': {model: sum(row['model'] == model for row in movements) for model in sorted(movement_models)},
            'adopted': False, 'original_catalog_preserved_in_target': False,
            'generated_salary_rules_adopted': False, 'rule_generation_executed': False,
            'generated_salary_rule_count_certified': False,
            'must_adopt_before_original_movement_processing': True},
        deferred_original_unpaid_link={
            'file': DEFER_FILE, 'record_xmlid': DEFER_OWNER, 'field': 'unpaid_structure_ids',
            'structure_xmlid': DEFER_TARGET, 'relation': 'hr_payroll_structure_hr_work_entry_type_rel',
            'original_fragment_sha256': hashlib.sha256(span.group()).hexdigest(),
            'original_file_sha256': hashlib.sha256(normal[DEFER_FILE]).hexdigest(),
            'profile_file_sha256': hashlib.sha256(profile[DEFER_FILE]).hexdigest(),
            'assignment_absent_in_profile': True, 'adopted': False,
            'original_policy_preserved_in_target': False, 'must_adopt_before_chile_processing': True},
        other_local_orphans=[], static_xml_csv_profile_closed=True,
        python_and_dependency_closure_certified=False, operational_payroll_package=False)
    return graph


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--addon', type=Path, required=True)
    parser.add_argument('--pin', type=Path, required=True)
    parser.add_argument('--verify-source-pin', action='store_true')
    parser.add_argument('--omit', action='append', default=[])
    parser.add_argument('--baseline-addon', type=Path,
        help='Normal derived provider for strict three-seed/one-assignment profile comparison')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pin = json.loads(args.pin.read_text())
    assert pin['license'] == 'AGPL-3' and len(pin['files']) == 52
    declaration = ast.literal_eval((args.addon / '__manifest__.py').read_text(encoding='utf-8-sig'))
    assert declaration.get('license') == 'AGPL-3', 'Free provider required before source inspection'
    if args.verify_source_pin:
        assert all(hashlib.sha256((args.addon / relative(name)).read_bytes()).hexdigest() == value for name, value in pin['files'].items()), 'Original runtime pin mismatch'
    output = args.output.resolve()
    assert Path('/opt/steps-validation') in output.parents and not output.exists()
    if args.baseline_addon:
        assert not args.omit and not args.verify_source_pin, 'Profile comparison uses its normal derived baseline'
        report = verify_bootstrap_profile(args.baseline_addon, args.addon, allowed_files=set(pin['files']))
    else:
        report = analyze_addon(args.addon, omit=args.omit, allowed_files=set(pin['files']))
    report.update(tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), source_pin_sha256=hashlib.sha256(args.pin.read_bytes()).hexdigest(), original_pin_verified=args.verify_source_pin)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream: json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'removed_seed_blockers': len(report['removed_seed_blockers']),
        'remaining_salary_master_records': len(report['remaining_salary_master_records']), 'external_requirements': len(report['external_requirements']), 'bootstrap_certified': False}))


if __name__ == '__main__':
    main()
