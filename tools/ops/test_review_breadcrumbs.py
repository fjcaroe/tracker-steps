"""Keep read-only native review navigation bounded to verified actions."""
import json
import unittest
from review_management_panel import is_action_breadcrumb_read, is_read_request


class BreadcrumbReadCase(unittest.TestCase):
    def allowed(self, actions):
        return is_action_breadcrumb_read(json.dumps({'params': {'actions': actions}}),
            [10, 11], ['step.cosecha.registry'])

    def test_verified_client_and_window_navigation(self):
        self.assertTrue(self.allowed([{'action': 10}, {'action': '11', 'resId': 'new'}]))
        self.assertTrue(self.allowed([{'model': 'step.cosecha.registry', 'resId': 3}]))

    def test_unknown_actions_and_models_are_denied(self):
        self.assertFalse(self.allowed([{'action': 999}]))
        self.assertFalse(self.allowed([{'action': 'mail.action_send'}]))
        self.assertFalse(self.allowed([{'model': 'ir.actions.server', 'resId': 3}]))
        self.assertFalse(is_read_request('/web/action/load_breadcrumbs', b'{}'))

    def test_malformed_and_mutation_requests_stay_denied(self):
        for actions in ([], [None], [{'action': True}], [{'action': 10, 'resId': -1}], [{'action': 10}]*17):
            self.assertFalse(self.allowed(actions))
        self.assertFalse(is_action_breadcrumb_read(b'bad', [10]))
        self.assertFalse(is_read_request('/web/dataset/call_button',
            json.dumps({'params': {'model': 'step.cosecha.registry', 'method': 'action_costeo'}})))


if __name__ == '__main__':
    unittest.main()
