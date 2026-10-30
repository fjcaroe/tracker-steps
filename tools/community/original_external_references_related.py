"""Prove a stored discriminator's exact relation to the ir.model namespace.

Metadata only. No Odoo, records, source bodies, compute/selection execution,
SQL execution or model-name-to-table guesses. Runtime rows must independently
prove equality to this physical relation; metadata alone is not admission.
"""
from collections import Counter
import json


EXPECTED = ('calendar.event', 'mail.activity', 'rating.rating')


def resolve(catalog, models, owner_model, reference_field):
    """Return one narrowly typed chain, or an explicit unresolved reason."""
    def reject(reason):
        return {'proven': False, 'reason': reason}

    owner = models.get(owner_model)
    proof = reference_field.get('discriminator_field')
    if not owner or not proof or proof.get('name') != reference_field.get('model_field'):
        return reject('discriminator-metadata-missing')
    if (proof.get('type') != 'char' or proof.get('store') is not True or proof.get('compute') is not True
            or proof.get('company_dependent') is not False):
        return reject('stored-related-char-required')
    related = proof.get('related')
    if not isinstance(related, list) or len(related) != 2 or related[1] != 'model':
        return reject('exact-two-step-ir-model-related-chain-required')
    first, leaf = related
    link = next((field for field in owner['fields'] if field['name'] == first), None)
    namespace = models.get('ir.model')
    if (not link or link.get('type') != 'many2one' or link.get('comodel') != 'ir.model'
            or link.get('store') is not True or link.get('company_dependent') is not False or link.get('related')
            or not namespace or namespace['abstract'] or not namespace['auto'] or namespace['transient']):
        return reject('physical-stored-many2one-to-registry-ir-model-required')
    tables = {row['name']: row for row in catalog['tables']}
    owner_table, model_table = owner['table'], namespace['table']
    if any(table not in tables or tables[table]['schema'] != 'public' or tables[table]['kind'] not in ('r', 'p')
            for table in (owner_table, model_table)):
        return reject('related-chain-not-in-public-physical-storage')
    columns = {(row['table_name'], row['name']): row for row in catalog['columns']}
    stored = columns.get((owner_table, proof['name']))
    source = columns.get((owner_table, first))
    target = columns.get((model_table, leaf))
    if (not stored or stored['sql_type'] not in ('text', 'character varying') or not source
            or source['sql_type'] not in ('smallint', 'integer', 'bigint') or not target
            or target['sql_type'] not in ('text', 'character varying') or target['not_null'] is not True):
        return reject('stored-discriminator-link-or-namespace-column-not-proven')
    declared = [row for row in catalog['fields'] if row['model'] == owner_model and row['name'] == first]
    if (len(declared) != 1 or declared[0]['ttype'] != 'many2one' or declared[0]['relation'] != 'ir.model'
            or declared[0]['store'] is not True or declared[0]['company_dependent'] or declared[0].get('related')):
        return reject('sql-and-registry-link-metadata-differ')
    fks = [row for row in catalog['foreign_keys'] if row['source_schema'] == row['target_schema'] == 'public'
        and row['source_table'] == owner_table and row['source_columns'] == [first]
        and row['target_table'] == model_table and row['target_columns'] == ['id'] and row['validated'] is True]
    keys = [row for row in catalog['keys'] if row['table_name'] == model_table and row['columns'] == [leaf]]
    if len(fks) != 1 or not keys:
        return reject('validated-namespace-foreign-key-and-global-unique-name-required')
    return {'proven': True, 'kind': 'stored-related-ir-model-namespace', 'owner_model': owner_model,
        'owner_table': owner_table, 'reference_field': reference_field['name'],
        'stored_discriminator_field': proof['name'], 'related': related,
        'namespace_model': 'ir.model', 'namespace_table': model_table, 'namespace_field': leaf,
        'link_field': first, 'foreign_key': fks[0], 'namespace_unique_keys': keys, 'namespace_read_only_parent': True,
        'runtime_equality_observation_required': True, 'computes_executed': False,
        'source_bodies_read': False, 'adoption_authorized': False}


def compare(baseline, current):
    """Offline contrast: close exactly three guards and preserve old bindings."""
    def require(value, message):
        if not value:
            raise ValueError(message)
    for report in (baseline, current):
        require(report['read_only'] is True and report['database_writes'] is False
            and report['import_authorized'] is False and report['id_reservation_authorized'] is False
            and report['two_snapshots_exact'] is True, 'readonly-complete-reference-reports-required')
    for key in ('database', 'capsule_sha256', 'backup_sha256', 'acceptance_sha256', 'registry_proof_sha256',
            'source_packet_sha256', 'installation_postflight_sha256', 'scope', 'target_identities',
            'alias_identity_plan', 'original_master_value_hashes', 'original_xmlids_backup_proof', 'registry_runtime_proof'):
        require(baseline[key] == current[key], 'related-contrast-source-or-identity-differs:' + key)
    catalogs = {'transaction', 'database', 'modules', 'pending', 'tables', 'columns', 'keys', 'foreign_keys',
        'fields', 'alias_occupants', 'action_462', 'action_family'}
    catalogs |= {key for key in baseline['observations'] if key.startswith(('target-occupants:', 'target-aliases:', 'original-master-hash:'))}
    require(all(baseline['observations'][key] == current['observations'][key] for key in catalogs), 'related-contrast-catalog-drift')

    def paths(report):
        result = Counter()
        for path in report['paths']:
            value = dict(path)
            value.pop('observation')
            if 'invalid_observation' in value:
                value['invalid_observation'] = report['observations'][value['invalid_observation']]
            result[json.dumps(value, sort_keys=True, separators=(',', ':'))] += 1
        return result
    old_paths, new_paths = paths(baseline), paths(current)
    require(all(new_paths[key] >= count for key, count in old_paths.items()), 'related-contrast-lost-or-changed-original-path')

    def blocker(row):
        value = dict(row); value.pop('related_binding_reason', None)
        return json.dumps(value, sort_keys=True, separators=(',', ':'))
    old_blocks, new_blocks = (Counter(blocker(row) for row in report['blockers']) for report in (baseline, current))
    closed = [blocker({'code': 'polymorphic-discriminator-binding-not-proven', 'model': model, 'field': 'res_id'}) for model in EXPECTED]
    require(all(old_blocks[key] == 1 and new_blocks[key] == 0 for key in closed), 'exact-three-original-related-guards-not-closed')
    for key in closed:
        old_blocks.subtract({key: 1})
        del old_blocks[key]
    require(old_blocks == new_blocks, 'related-contrast-other-guards-changed-or-new-data-mismatch')
    lineage = {}
    for model in EXPECTED:
        mismatches = [path for path in current['paths'] if path['kind'] == 'stored-related-discriminator-mismatch'
            and path['discriminator_binding']['owner_model'] == model]
        links = [path for path in current['paths'] if path['kind'] == 'registry-related-discriminator-link' and path['owner_model'] == model]
        require(len(mismatches) == len(links) == 1 and not mismatches[0]['rows']
            and links[0]['runtime_equality_observation'] == mismatches[0]['observation']
            and links[0]['discriminator_binding']['runtime_equality_observation_required'] is True,
            'related-runtime-lineage-and-empty-mismatch-witness-required')
        lineage[model] = {'active_namespace_link_observations': len(links[0]['rows']), 'mismatches': 0,
            'physical_namespace_table': links[0]['discriminator_binding']['namespace_table']}
    return {'schema': 1, 'closed_guards': [{'model': model, 'field': 'res_id'} for model in EXPECTED],
        'blockers_before': len(baseline['blockers']), 'blockers_after': len(current['blockers']),
        'only_three_proven_related_guards_closed': True, 'all_original_paths_and_observations_preserved': True,
        'catalog_and_original_master_hashes_unchanged': True, 'runtime_lineage': lineage,
        'database_writes': False, 'computes_executed': False, 'adoption_authorized': False, 'id_reservation_authorized': False}
