"""COPY is inert metadata; no restore/SQL/ORM or private fixtures."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import original_external_references_dump as audit


BODY = ('-- Data only, do not execute\n'
    'COPY public.ir_model_data (id, module, name, model, res_id, noupdate, create_uid) FROM stdin;\n'
    '1\thr_contract\tstructure_type_employee\thr.payroll.structure.type\t1\tt\t1\n'
    '2\tsynthetic\taccent_Ñandú\\tkey\tir.actions.report\t462\tf\t1\n'
    '\\.\nSELECT pg_catalog.setval(\'source_sequence\', 900, true);\n')


class OriginalReferenceDumpCase(unittest.TestCase):
    def test_entire_original_identity_is_bound_to_dump_without_executing_its_commands(self):
        rows = audit.xmlids_from_copy(BODY)
        self.assertEqual(rows[1]['name'], 'accent_Ñandú\tkey')
        with patch.object(audit.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=BODY)) as run:
            result = audit.prove_original_identity('/private/source.dump', {'original_xmlids': list(reversed(rows))})
            self.assertEqual(result['original_xmlids'], 2)
            self.assertFalse(result['dump_ddl_dml_or_copy_executed'])
            command = run.call_args.args[0]
            self.assertEqual(command[:5], ['pg_restore', '--data-only', '--schema=public', '--table=ir_model_data', '--file=-'])
            self.assertNotIn('--dbname', command)
            self.assertNotIn('-d', command)
            changed = deepcopy(rows); changed[1]['noupdate'] = True
            with self.assertRaisesRegex(ValueError, 'differs-from-own-backup'):
                audit.prove_original_identity('/private/source.dump', {'original_xmlids': changed})

    def test_extra_copy_missing_terminator_duplicate_id_or_malformed_boolean_is_rejected(self):
        variants = [BODY + BODY, BODY.replace('\\.\n', ''),
            BODY.replace('2\tsynthetic', '1\tsynthetic'), BODY.replace('\tf\t1\n', '\tunknown\t1\n'),
            BODY.replace('COPY public.ir_model_data', 'COPY public.hr_salary_rule')]
        for body in variants:
            with self.subTest(length=len(body)), self.assertRaises(ValueError):
                audit.xmlids_from_copy(body)


if __name__ == '__main__':
    unittest.main()
