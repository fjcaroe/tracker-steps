"""Synthetic graph contracts, never a native source visibility oracle."""
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import probe_original_master_visibility as source
import original_handover_visibility_contract as contract
from test_original_handover_visibility_contract import fixture, DATABASE


def graph_fixture():
    modules = [{'name': 'module_%03d' % index, 'version': None if index == 381 else '18.0.1.0.0',
        'license': 'OEEL-1' if index < 140 else 'LGPL-3', 'state': 'installed'} for index in range(382)]
    inventory = {'read_only': True, 'orm_loaded': False, 'business_data_exported': False,
        'source_bodies_exported': False, 'enterprise_sources_copied': False,
        'products': {'cerro': {'installed': 382, 'enterprise': 140,
            'modules': [{key: value for key, value in row.items() if key != 'state'} for row in modules]}}}
    return modules, json.dumps(inventory, sort_keys=True).encode()


def pinned_fixture(modules, raw):
    stack = ExitStack()
    stack.enter_context(patch.object(source, 'SOURCE_INVENTORY_SHA256', source.sha(raw)))
    stack.enter_context(patch.object(source, 'SOURCE_GRAPH_PROJECTION_SHA256', source.sha(source.encode(modules))))
    return stack


class SourceGraphVisibilityCase(unittest.TestCase):
    def test_entire_sorted_name_version_license_installed_projection_is_bound_to_both_seals(self):
        modules, raw = graph_fixture()
        with pinned_fixture(modules, raw):
            self.assertEqual(source.source_inventory_graph(raw), modules)
            admission = source.admit_source_graph(modules, raw)
            self.assertEqual(admission['installed'], 382)
            self.assertEqual(admission['enterprise'], 140)
            self.assertIsNone(admission['installed_modules'][-1]['version'])
            self.assertEqual(admission['observed_projection_sha256'], source.sha(source.encode(modules)))
            self.assertFalse(admission['database_writes'])
            for change in ('name', 'version', 'license', 'state', 'extra', 'missing', 'reorder', 'duplicate', 'invent_null'):
                observed = deepcopy(modules)
                if change == 'name': observed[1]['name'] = 'another_module'
                if change == 'version': observed[1]['version'] = '18.0.2.0.0'
                if change == 'license': observed[1]['license'] = 'LGPL-3'
                if change == 'state': observed[1]['state'] = 'to upgrade'
                if change == 'extra': observed.append(dict(observed[-1], name='extra_module'))
                if change == 'missing': observed.pop()
                if change == 'reorder': observed.reverse()
                if change == 'duplicate': observed[-1] = dict(observed[-2])
                if change == 'invent_null': observed[-1]['version'] = '18.0.1.0.0'
                with self.subTest(change=change), self.assertRaises(ValueError): source.admit_source_graph(observed, raw)

    def test_wrong_inventory_bytes_product_or_metadata_safety_rejects_without_database(self):
        modules, raw = graph_fixture()
        with self.assertRaisesRegex(ValueError, 'inventory9358'): source.source_inventory_graph(raw)
        with pinned_fixture(modules, raw):
            with self.assertRaises(ValueError): source.source_inventory_graph(raw + b' ')
        for change in ('rw', 'orm', 'body', 'count', 'license', 'projection'):
            data = json.loads(raw)
            if change == 'rw': data['read_only'] = False
            if change == 'orm': data['orm_loaded'] = True
            if change == 'body': data['enterprise_sources_copied'] = True
            if change == 'count': data['products']['cerro']['installed'] = 381
            if change == 'license': data['products']['cerro']['modules'][0]['license'] = 'LGPL-3'
            if change == 'projection': data['products']['cerro']['modules'][0]['version'] = None
            altered = json.dumps(data, sort_keys=True).encode()
            with pinned_fixture(modules, altered), self.subTest(change=change), self.assertRaises(ValueError):
                source.source_inventory_graph(altered)

    def test_graph382_requires_admission_new_observer_full_projection_and_original_identities(self):
        capsule, proof = fixture(); modules, raw = graph_fixture()
        with pinned_fixture(modules, raw):
            proof['engine'].update(installed=382, payslip_model_id=600, report_rows=[[462, 'hr.payslip']],
                module_metadata_sha256=source.sha(source.encode(modules)))
            proof['probe_sha256'] = next(iter(contract.GRAPH_SOURCE_OBSERVER_HASHES))
            proof['source_graph_admission'] = source.admit_source_graph(modules, raw)
            call = lambda value: contract.validate_source(value, capsule, target_database=DATABASE,
                original_model_id=600, original_report_ids={462})
            call(proof)
            for change in ('missing', 'old_observer', 'profile', 'inventory_sha', 'projection', 'count', 'engine_hash',
                    'module_version', 'module_state', 'readonly', 'model', 'report', 'extra_key'):
                value = deepcopy(proof); graph = value['source_graph_admission']
                if change == 'missing': value.pop('source_graph_admission')
                if change == 'old_observer': value['probe_sha256'] = next(iter(contract.LEGACY_SOURCE_OBSERVER_HASHES))
                if change == 'profile': graph['profile'] = 'source-graph-unreviewed'
                if change == 'inventory_sha': graph['inventory_sha256'] = '0' * 64
                if change == 'projection': graph['observed_projection_sha256'] = '0' * 64
                if change == 'count': graph['installed'] = 381
                if change == 'engine_hash': value['engine']['module_metadata_sha256'] = '0' * 64
                if change == 'module_version': graph['installed_modules'][1]['version'] = 'other'
                if change == 'module_state': graph['installed_modules'][1]['state'] = 'to remove'
                if change == 'readonly': value['transaction']['read_only'] = False
                if change == 'model': value['engine']['payslip_model_id'] = 602
                if change == 'report': value['engine']['report_rows'] = [[777, 'hr.payslip']]
                if change == 'extra_key': graph['allow_missing_modules'] = True
                with self.subTest(change=change), self.assertRaises(ValueError): call(value)

    def test_legacy381_receipt_remains_valid_and_382_never_implicitly_opts_in(self):
        capsule, proof = fixture()
        contract.validate_source(proof, capsule, target_database=DATABASE, original_model_id=602, original_report_ids={777})
        proof['engine']['installed'] = 382
        with self.assertRaisesRegex(ValueError, 'legacy-s7-source381'):
            contract.validate_source(proof, capsule, target_database=DATABASE, original_model_id=602, original_report_ids={777})
        self.assertIn(source.sha(Path(source.__file__).read_bytes()), contract.GRAPH_SOURCE_OBSERVER_HASHES)


if __name__ == '__main__':
    unittest.main()
