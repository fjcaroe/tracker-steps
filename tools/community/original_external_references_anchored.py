"""Separate, fail-closed policy for PRESERVING opaque references without edits.

It prevents ID-relocation damage when original bytes/PKs/endpoints stay exact.
It does not parse opaque code, prove backend compatibility, remove the global
reference guards or authorize adoption/writes. Root supplies lock/restore and
complete source snapshot evidence from the same private anchored rehearsal.
"""
import json
import re

ORIGINAL_MODELS = ('hr.payroll.structure', 'hr.payroll.structure.type', 'hr.payslip.input.type',
    'hr.salary.rule', 'hr.salary.rule.category')


def require(value, message):
    if not value:
        raise ValueError(message)


def opaque_inventory(report):
    rows = {}
    for path in report['paths']:
        if path['kind'] not in ('serialized-configuration', 'untyped-json-without-reference-schema'):
            continue
        for row in path['rows']:
            require(row['owner_pk'] is not None and re.fullmatch('[0-9a-f]{64}', row['content_sha256']), 'opaque-owner-or-byte-hash-not-proven')
            key = (path['table'], path['field'], json.dumps(row['owner_pk'], sort_keys=True, separators=(',', ':')))
            require(key not in rows, 'duplicate-opaque-owner-binding')
            rows[key] = row['content_sha256']
    return rows


def preserve(source, target, business_before, business_after, identity_before, identity_after, witness):
    """Return risk separation only; every inherited admission guard remains."""
    for report in (source, target):
        require(report['read_only'] is True and report['database_writes'] is False
            and report['import_authorized'] is False and report['id_reservation_authorized'] is False
            and report['two_snapshots_exact'] is True, 'readonly-complete-anchored-references-required')
    require(source['database'] == target['database'] and re.fullmatch(
        r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', source['database']), 'same-private-anchored-database-required')
    require(witness['database'] == source['database'] and witness['lock_path'] == '/run/lock/steps-environments.lock'
        and witness['lock_held_for_entire_rehearsal'] is True and witness['fresh_restore_verified'] is True
        and witness['complete_original_business_inventory_verified'] is True
        and witness['original_ids_rekeyed'] is False and witness['original_records_retargeted'] is False,
        'anchored-lock-restore-no-rekey-witness-required')
    for key in ('backup_sha256', 'restore_receipt_sha256', 'lock_receipt_sha256', 'source_inventory_sha256'):
        require(isinstance(witness[key], str) and re.fullmatch('[0-9a-f]{64}', witness[key]), 'sealed-anchored-witness-required:' + key)
    require(source['backup_sha256'] == target['backup_sha256'] == witness['backup_sha256'], 'anchored-original-backup-differs')
    require(isinstance(business_before, dict) and business_before and all(
        name in business_after and business_after[name] == row for name, row in business_before.items()),
        'original-business-or-counter-bytes-changed')
    for name in ('ir_model', 'ir_model_fields', 'original_xmlids'):
        before, after = identity_before[name], identity_after[name]
        require(before and isinstance(before, list) and isinstance(after, list), 'complete-original-identity-list-required:' + name)
        current = {row['id']: row for row in after}
        require(len(current) == len(after) and len({row['id'] for row in before}) == len(before), 'duplicate-original-identity-pk')
        require(all(current.get(row['id']) == row for row in before), 'original-identity-or-alias-retargeted:' + name)
    require(source['scope'] == target['scope'], 'original-reference-ids-or-physical-model-tables-changed')
    require(all(model in source['scope'] and model in source['target_identities'] for model in ORIGINAL_MODELS)
        and sum(len(source['scope'][model]['ids']) for model in ORIGINAL_MODELS) == 120
        and len(source['scope']['hr.salary.rule']['ids']) == 71
        and source['scope'].get('ir.actions.report', {}).get('ids') == [462]
        and source['endpoint_identities'], 'complete-original-120-71-and-report462-inventory-required')
    for model, before in source['target_identities'].items():
        after = target['target_identities'].get(model)
        require(after and before['physical_table'] == after['physical_table'] and before['expected_ids'] == after['expected_ids']
            and before['rows'] == after['rows'], 'original-scoped-endpoint-bytes-or-ids-changed:' + model)
    for before in source['endpoint_identities']:
        candidates = [row for row in target['endpoint_identities'] if (row['table'], row['model']) == (before['table'], before['model'])]
        require(len(candidates) == 1 and set(before['ids']) <= set(candidates[0]['ids']), 'original-external-endpoint-binding-lost')
        after = candidates[0]
        require([row for row in after['rows'] if row['id'] in before['ids']] == before['rows'], 'original-external-endpoint-bytes-changed')
        aliases = {row['id']: row for row in after['aliases']}
        require(len(aliases) == len(after['aliases']) and all(aliases.get(row['id']) == row for row in before['aliases']), 'original-external-endpoint-alias-retargeted')
    original, current = opaque_inventory(source), opaque_inventory(target)
    require(original and all(current.get(key) == value for key, value in original.items()), 'original-opaque-owner-or-content-bytes-changed')
    return {'schema': 1, 'policy': 'anchored-opaque-preservation-without-edits', 'opaque_original_cells_preserved': len(original),
        'original_business_snapshot_entries_exact': len(business_before),
        'original_identity_rows_exact': {key: len(identity_before[key]) for key in ('ir_model', 'ir_model_fields', 'original_xmlids')},
        'source_unresolved_guards': len(source['blockers']), 'target_unresolved_guards': len(target['blockers']),
        'inherited_global_guards_removed': False, 'opaque_contents_evaluated': False,
        'identity_relocation_risk_prevented_by_preservation': True, 'root_witness_requires_external_verification': True,
        'semantic_backend_compatibility_certified': False, 'permissions_compatibility_certified': False,
        'other_product_conversion_certified': False, 'adoption_writer_authorized': False, 'writer_authorized': False}
