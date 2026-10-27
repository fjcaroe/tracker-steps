"""An identical reset is a no-op; a different graph must never be hidden."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ops'))
from preserve_action_view_ids import identical_reset


class ActionViewPreservationCase(unittest.TestCase):
    def test_identical_graph(self):
        self.assertTrue(identical_reset([(5, 0, 0), (0, 0, {'view_mode': 'list', 'view_id': 12})], [('list', 12, 0)]))

    def test_changed_graph_or_order(self):
        commands = [(5, 0, 0), (0, 0, {'view_mode': 'list', 'view_id': 12})]
        for existing in ([('list', 13, 0)], [('form', 12, 0)], [('list', 12, 1)], []):
            self.assertFalse(identical_reset(commands, existing))

    def test_other_commands_and_extra_values(self):
        self.assertFalse(identical_reset([(6, 0, [12])], [('list', 12, 0)]))
        self.assertFalse(identical_reset([(5, 0, 0), (0, 0, {'view_mode': 'list', 'view_id': 12, 'other': True})], [('list', 12, 0)]))


if __name__ == '__main__':
    unittest.main()
