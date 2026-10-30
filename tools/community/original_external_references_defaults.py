"""Typed ir.default JSON references; read-only, never evaluates conditions.

Source contract: Odoo Community 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4,
odoo/addons/base/models/ir_default.py (LGPL-3): field_id and JSON-encoded
defaults. No convert_to_cache, ORM access, domain/code evaluation or writer.
Unknown scalar/custom semantics stay unresolved; planned identity deltas
never authorize overwriting an occupant.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re

import original_external_references as refs
import payroll_configuration_adoption_preflight as gate


SOURCE = 'https://github.com/odoo/odoo/blob/4b4efe68291d6def5bb7d2e1f2b829e0cda577d4/odoo/addons/base/models/ir_default.py'
RELATIONAL = ('many2one', 'many2many', 'reference')
SAFE_M2O = r'^[[:space:]]*(false|null|0|[1-9][0-9]{0,9})[[:space:]]*$'
SAFE_M2M = r'^[[:space:]]*(false|null|[][0-9,[:space:]-]+)[[:space:]]*$'
SAFE_REFERENCE = r'^[[:space:]]*(false|null|"[a-z_][a-z0-9_.]+,[1-9][0-9]{0,9}")[[:space:]]*$'


def need(value, message):
    if not value:
        raise ValueError(message)


def targets(kind, raw, comodel, models):
    """Parse references, never execute relational commands or use loose IDs."""
    def nonfinite(_):
        raise ValueError('nonfinite-json-refused')
    value = json.loads(raw, parse_constant=nonfinite)
    if value is None or value is False:
        return []
    positive = lambda number: type(number) is int and 0 < number < 2**31
    if kind == 'many2one':
        if type(value) is int and value == 0:
            return []
        need(positive(value), 'many2one-default-is-not-an-exact-record-id')
        return [(comodel, value)]
    if kind == 'reference':
        need(isinstance(value, str) and re.fullmatch(r'[a-z_][a-z0-9_.]+,[1-9][0-9]{0,9}', value), 'reference-default-is-not-model-comma-id')
        model, number = value.rsplit(',', 1)
        need(model in models and positive(int(number)), 'reference-default-model-or-id-not-proven')
        return [(model, int(number))]
    need(kind == 'many2many' and isinstance(value, list), 'unsupported-relational-default-type')
    if all(positive(number) for number in value):
        return [(comodel, number) for number in value]
    result = []
    for command in value:
        need(isinstance(command, list) and command and type(command[0]) is int, 'relational-default-command-not-typed')
        if command[0] == 4:
            need(len(command) in (2, 3) and positive(command[1])
                and (len(command) == 2 or type(command[2]) is int and command[2] == 0), 'invalid-link-default-command')
            result.append((comodel, command[1]))
        elif command[0] == 6:
            need(len(command) == 3 and type(command[1]) is int and command[1] == 0 and isinstance(command[2], list)
                and all(positive(number) for number in command[2]), 'invalid-set-default-command')
            result += [(comodel, number) for number in command[2]]
        else:
            raise ValueError('create-update-delete-clear-default-commands-not-admitted')
    return result


def contract(reference, registry):
    models = refs.registry_models(registry)
    observations = reference['observations']
    owner, metadata = models.get('ir.default'), models.get('ir.model.fields')
    need(owner and metadata and owner['auto'] and not owner['abstract'] and not owner['transient'], 'actual-default-model-storage-not-proven')
    table, fields_table = owner['table'], metadata['table']
    columns = {(row['table_name'], row['name']): row for row in observations['columns']}
    need(all((table, name) in columns for name in ('id', 'field_id', 'user_id', 'company_id', 'condition', 'json_value'))
        and columns[table, 'json_value']['sql_type'] in ('text', 'character varying'), 'default-json-physical-columns-not-proven')
    links = []
    for name, target in (('field_id', 'ir.model.fields'), ('user_id', 'res.users'), ('company_id', 'res.company')):
        relation = next((field for field in owner['fields'] if field['name'] == name), None)
        need(relation and relation['type'] == 'many2one' and relation['comodel'] == target and relation['store']
            and target in models, 'default-metadata-user-company-link-not-proven')
        fks = [fk for fk in observations['foreign_keys'] if fk['source_schema'] == fk['target_schema'] == 'public'
            and fk['source_table'] == table and fk['source_columns'] == [name] and fk['target_table'] == models[target]['table']
            and fk['target_columns'] == ['id'] and fk['validated']]
        need(len(fks) == 1, 'default-field-user-company-validated-fk-required')
        links.append(fks[0])
    need(refs._owner(table, observations), 'default-owner-key-required')
    return {'table': table, 'field_table': fields_table, 'foreign_keys': links, 'owner_key': refs._owner(table, observations)}


def queries(binding):
    owner = refs._owner_sql(binding['owner_key'])
    column, field = 'd.json_value', 'f.ttype'
    # Only reference-shaped numbers/model names leave SQL as payload. Unknown
    # strings/scalars (including possible secrets) leave solely as hashes.
    exposed = ('CASE WHEN (' + field + "='many2one' AND " + column + ' ~ ' + refs.literal(SAFE_M2O) + ') OR ('
        + field + "='many2many' AND " + column + ' ~ ' + refs.literal(SAFE_M2M) + ') OR ('
        + field + "='reference' AND " + column + ' ~ ' + refs.literal(SAFE_REFERENCE) + ') THEN ' + column + ' ELSE NULL END')
    sql = ('SELECT ' + owner.replace('t.', 'd.') + ' AS owner_pk,d.field_id,d.user_id,d.company_id,'
        + "encode(sha256(convert_to(d.condition::text,'UTF8')),'hex') AS condition_sha256,"
        + "encode(sha256(convert_to(to_jsonb(d)::text,'UTF8')),'hex') AS row_sha256,"
        + "encode(sha256(convert_to(d.json_value::text,'UTF8')),'hex') AS value_sha256,"
        + 'f.model,f.name AS field_name,f.ttype,f.relation,f.store,f.company_dependent,' + exposed + ' AS reference_json'
        + ' FROM public.' + refs.ident(binding['table']) + ' d LEFT JOIN ONLY public.' + refs.ident(binding['field_table'])
        + ' f ON f.id=d.field_id ORDER BY owner_pk')
    return {'transaction': "SELECT current_setting('transaction_read_only') AS mode", 'defaults': sql}


def classify(rows, reference, registry):
    models = refs.registry_models(registry)
    known_fields = {row['id']: row for row in reference['observations']['fields']}
    adoption = {model: set(value['ids']) for model, value in reference['scope'].items()
        if model in gate.TABLES.values() or model.startswith('ir.actions.')}
    classified = []
    need(len({json.dumps(row['owner_pk'], sort_keys=True) for row in rows}) == len(rows), 'duplicate-physical-default-owner')
    for row in rows:
        item = {key: row[key] for key in ('owner_pk', 'field_id', 'user_id', 'company_id', 'condition_sha256',
            'row_sha256', 'value_sha256', 'model', 'field_name', 'ttype', 'relation')}
        item.update(status='unresolved', targets=[], adoption_target_hits=[], writer_authorized=False)
        meta = known_fields.get(row['field_id'])
        owner = models.get(row['model'])
        loaded = next((field for field in owner['fields'] if field['name'] == row['field_name']), None) if owner else None
        if row['ttype'] not in RELATIONAL:
            item['reason'] = 'scalar-or-custom-default-not-certified-by-relational-registry-snapshot'
        elif (not meta or not loaded or any(meta[key] != row[key] for key in ('model', 'ttype', 'relation', 'store', 'company_dependent'))
                or meta['name'] != row['field_name'] or loaded['type'] != row['ttype'] or loaded['comodel'] != row['relation']
                or loaded['store'] != row['store'] or loaded['company_dependent'] != row['company_dependent']):
            item['reason'] = 'default-field-sql-and-loaded-registry-binding-not-proven'
        elif row['reference_json'] is None:
            item['reason'] = 'default-json-not-reference-shaped-payload-withheld'
        else:
            try:
                pairs = targets(row['ttype'], row['reference_json'], row['relation'], models)
                physical = {row['name'] for row in reference['observations']['tables'] if row['kind'] in ('r', 'p') and row['schema'] == 'public'}
                need(all(model in models and not models[model]['abstract'] and models[model]['table'] in physical for model, _ in pairs), 'default-target-model-not-physical')
            except (ValueError, TypeError):
                item['reason'] = 'relational-default-json-is-not-an-admitted-literal'
            else:
                item.update(status='typed', reason=None,
                    targets=[{'model': model, 'table': models[model]['table'], 'id': number} for model, number in pairs],
                    adoption_target_hits=[{'model': model, 'id': number} for model, number in pairs if number in adoption.get(model, set())])
        classified.append(item)
    return classified


def endpoint_plan(rows, classified, registry):
    models = refs.registry_models(registry)
    paths, observations = [], {}
    for source, item in zip(rows, classified):
        candidates = [(target['model'], target['id']) for target in item['targets']]
        candidates += [('ir.model.fields', source['field_id'])]
        candidates += [(model, source[key]) for model, key in (('res.users', 'user_id'), ('res.company', 'company_id')) if source[key] is not None]
        for model, number in candidates:
            need(model in models and not models[model]['abstract'], 'default-endpoint-model-not-registered')
            name = 'default-endpoint-source:' + str(len(paths))
            paths.append({'observation': name, 'target_model': model, 'target_table': models[model]['table']})
            observations[name] = [{'owner_pk': source['owner_pk'], 'target_id': number}]
    return refs.endpoint_queries(paths, observations, registry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference-report', 'registry-proof', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--expected-reference-sha256', required=True)
    args = parser.parse_args()
    need(refs.sha(args.reference_report) == args.expected_reference_sha256, 'reference-seal-differs')
    reference, registry = (json.loads(path.read_text()) for path in (args.reference_report, args.registry_proof))
    need(refs.sha(args.registry_proof) == reference['registry_proof_sha256'] and reference['read_only'] is True
        and reference['database_writes'] is False and reference['import_authorized'] is False, 'sealed-readonly-reference-required')
    binding = contract(reference, registry); statements = queries(binding)
    discovery = refs.run_snapshot(reference['database'], statements)
    rows = classify(discovery['defaults'], reference, registry)
    endpoints, endpoint_contracts = endpoint_plan(discovery['defaults'], rows, registry)
    first = refs.run_snapshot(reference['database'], dict(statements, **endpoints))
    second = refs.run_snapshot(reference['database'], dict(statements, **endpoints))
    need(first == second and all(first[key] == value for key, value in discovery.items()), 'defaults-or-field-metadata-changed-between-snapshots')
    identities = []
    for endpoint in endpoint_contracts:
        found = first[endpoint['observation']]
        need(set(endpoint['ids']) == {row['id'] for row in found} and len(found) == len(endpoint['ids']), 'typed-default-endpoint-missing-or-ambiguous')
        identities.append(dict(endpoint, rows=found, aliases=first.get(endpoint.get('alias_observation'), [])))
    # The inherited global guard is deliberately not removed by a partial
    # classification or by separating planned alias/target deltas.
    report = {'schema': 1, 'database': reference['database'], 'read_only': True, 'database_writes': False,
        'orm_loaded': False, 'conditions_or_code_evaluated': False, 'writer_authorized': False,
        'inherited_guard_count': len(reference['blockers']), 'inherited_guards_unchanged': True,
        'source_contract': SOURCE, 'source_reference_sha256': refs.sha(args.reference_report),
        'registry_sha256': refs.sha(args.registry_proof), 'tool_sha256': refs.sha(__file__),
        'physical_contract': binding, 'queries': dict(statements, **endpoints), 'two_snapshots_exact': True,
        'observations': first, 'classified_defaults': rows, 'endpoint_identities': identities,
        'summary': {'defaults': len(rows), 'states': dict(Counter(row['status'] for row in rows)),
            'typed_targets': sum(len(row['targets']) for row in rows),
            'adoption_target_hits': sum(len(row['adoption_target_hits']) for row in rows),
            'all_defaults_classified': all(row['status'] == 'typed' for row in rows),
            'typed_endpoint_records_and_aliases_captured': sum(len(row['rows']) for row in identities),
            'writer_authorized': False}}
    output = args.output.resolve()
    need(output.is_relative_to(Path('/opt/steps-validation')) and not output.exists() and output.parent.is_dir(), 'new-private-output-required')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'output': str(output), 'sha256': refs.sha(output), **report['summary']}))


if __name__ == '__main__':
    main()
