"""Anchoring separates relocation risk from semantic/writer authorization."""
from copy import deepcopy
import unittest

import original_external_references_anchored as policy


def fixture():
    source = dict(database='MANAGEMENT_QA_CERRO_PAYROLL_API_ANCHORED_SYNTHETIC', backup_sha256='0' * 64,
        read_only=True, database_writes=False, import_authorized=False, id_reservation_authorized=False, two_snapshots_exact=True,
        scope={'hr.salary.rule': {'table': 'original_rule', 'ids': [1]}}, target_identities={'hr.salary.rule': {
            'physical_table': 'original_rule', 'expected_ids': [1], 'rows': [{'id': 1, 'row_sha256': '1' * 64}]}},
        endpoint_identities=[{'table': 'original_report', 'model': 'ir.actions.report', 'ids': [462],
            'rows': [{'id': 462, 'row_sha256': '2' * 64}], 'aliases': [{'id': 99, 'model': 'ir.actions.report', 'res_id': 462}]}],
        paths=[{'kind': 'serialized-configuration', 'table': 'ir_ui_view', 'field': 'arch_db',
            'rows': [{'owner_pk': {'id': 17, '_physical_table': 'ir_ui_view'}, 'content_sha256': '3' * 64}]}],
        blockers=[{'code': 'opaque-unresolved'}])
    for model, count in zip(policy.ORIGINAL_MODELS, (4, 5, 6, 71, 34)):
        table = 'original_' + model.replace('.', '_')
        source['scope'][model] = {'table': table, 'ids': list(range(1, count + 1))}
        source['target_identities'][model] = {'physical_table': table, 'expected_ids': list(range(1, count + 1)),
            'rows': [{'id': ident, 'row_sha256': '1' * 64} for ident in range(1, count + 1)]}
    source['scope']['ir.actions.report'] = {'table': 'original_report', 'ids': [462]}
    business = {'original_rule': {'rows': 71, 'md5': 'a' * 32}, 'ir_sequence_7': {'sequence': [8, True]}}
    identity = {'ir_model': [{'id': 600, 'model': 'hr.payslip'}], 'ir_model_fields': [{'id': 55, 'model': 'hr.payslip', 'name': 'state'}],
        'original_xmlids': [{'id': 90, 'module': 'hr_payroll', 'name': 'model_hr_payslip', 'model': 'ir.model', 'res_id': 600, 'noupdate': True}]}
    witness = dict(database=source['database'], lock_path='/run/lock/steps-environments.lock', lock_held_for_entire_rehearsal=True,
        fresh_restore_verified=True, complete_original_business_inventory_verified=True, original_ids_rekeyed=False,
        original_records_retargeted=False, backup_sha256='0' * 64, restore_receipt_sha256='4' * 64,
        lock_receipt_sha256='5' * 64, source_inventory_sha256='6' * 64)
    return source, business, identity, witness


class AnchoredPolicyCase(unittest.TestCase):
    def test_byte_preservation_classifies_risk_without_removing_guards_or_authorizing_writer(self):
        source, business, identity, witness = fixture()
        target, after, current = deepcopy(source), deepcopy(business), deepcopy(identity)
        after['new_real_engine_relation'] = {'rows': 71, 'md5': 'b' * 32}
        current['original_xmlids'].append(dict(identity['original_xmlids'][0], id=91, module='payroll'))
        result = policy.preserve(source, target, business, after, identity, current, witness)
        self.assertTrue(result['identity_relocation_risk_prevented_by_preservation'])
        for key in ('inherited_global_guards_removed', 'semantic_backend_compatibility_certified', 'adoption_writer_authorized', 'writer_authorized'):
            self.assertFalse(result[key])

    def test_any_opaque_endpoint_alias_original_identity_counter_or_lock_change_fails_closed(self):
        source, business, identity, witness = fixture()
        for change in ('opaque', 'opaque_owner', 'endpoint', 'alias', 'scope', 'identity', 'counter', 'missing_table',
                'lock', 'backup', 'rekey', 'retarget', 'fresh', 'inventory', 'writer'):
            target, after, current, proof = deepcopy(source), deepcopy(business), deepcopy(identity), deepcopy(witness)
            if change == 'opaque': target['paths'][0]['rows'][0]['content_sha256'] = '7' * 64
            elif change == 'opaque_owner': target['paths'][0]['rows'][0]['owner_pk']['id'] = 18
            elif change == 'endpoint': target['endpoint_identities'][0]['rows'][0]['row_sha256'] = '7' * 64
            elif change == 'alias': target['endpoint_identities'][0]['aliases'][0]['res_id'] = 463
            elif change == 'scope': target['scope']['hr.salary.rule']['ids'] = [2]
            elif change == 'identity': current['original_xmlids'][0]['res_id'] = 601
            elif change == 'counter': after['ir_sequence_7']['sequence'][0] += 1
            elif change == 'missing_table': after.pop('original_rule')
            elif change == 'lock': proof['lock_held_for_entire_rehearsal'] = False
            elif change == 'backup': proof['backup_sha256'] = '8' * 64
            elif change == 'rekey': proof['original_ids_rekeyed'] = True
            elif change == 'retarget': proof['original_records_retargeted'] = True
            elif change == 'fresh': proof['fresh_restore_verified'] = False
            elif change == 'inventory': proof['complete_original_business_inventory_verified'] = False
            elif change == 'writer': target['import_authorized'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                policy.preserve(source, target, business, after, identity, current, proof)


if __name__ == '__main__': unittest.main()
