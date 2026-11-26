"""Offline checks for private-plan boundaries; all records below are synthetic."""
import copy
import sys
import types
import unittest
from unittest.mock import patch

with patch.dict(sys.modules, {'fcntl': types.ModuleType('fcntl')}):
    from correct_reception_weights import validate_plan


def fixture():
    return {'ticket': 240, 'database': 'CERRO_EL_PLOMO', 'company_id': 98,
            'user_id': 8, 'expected_before_total': 700, 'expected_after_total': 770,
            'update_advance_drafts': True, 'draft_proformas': [{'id': 91}, {'id': 92}],
            'tags': [dict(name='SYNTHETIC'+str(n), package_id=n, detail_id=n,
                          receipt_line_id=n, picking_id=n, lot_id=n, product_id=n,
                          owner_id=n, location_id=n, boxes=10, old_kg=100, new_kg=110)
                     for n in range(1, 8)]}


class PlanBoundaryTests(unittest.TestCase):
    def test_complete_private_plan(self):
        validate_plan(fixture())

    def test_destination_and_ticket_cannot_drift(self):
        for key, value in [('database', 'LAB_TAREAS'), ('ticket', 239), ('user_id', 1)]:
            plan = fixture(); plan[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_duplicates_missing_rows_and_unapproved_totals(self):
        for change in ('duplicate', 'missing', 'total', 'negative', 'identity'):
            plan = copy.deepcopy(fixture())
            if change == 'duplicate':
                plan['tags'][1]['package_id'] = 1
            elif change == 'missing':
                plan['tags'].pop()
            elif change == 'total':
                plan['tags'][0]['new_kg'] += 1
            elif change == 'negative':
                plan['tags'][0]['new_kg'] = -1
            else:
                plan['tags'][0]['lot_id'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(plan)


if __name__ == '__main__':
    unittest.main()
