import json

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class HarvestLifecycleCase(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private Harvest lifecycle'})
        cls.user = new_test_user(cls.env, login='private_harvest_lifecycle', password='private-fixture',
            company_id=cls.company.id, company_ids=[Command.set(cls.company.ids)], groups='base.group_user,hr.group_hr_user')
        cls.worker = cls.env['hr.employee'].with_company(cls.company).create({
            'name': 'Private lifecycle worker', 'company_id': cls.company.id, 'pin': '984236'})
        cls.order = cls.env['step.cosecha.registry'].with_company(cls.company).create({
            'name': 'Private lifecycle order', 'mobile_work_order': 'PRIVATE-T236',
            'type_tarea': 'propio', 'product_uom_id': cls.env.ref('uom.product_uom_kgm').id,
            'company_id': cls.company.id, 'date': fields.Datetime.now()})
        cls.line = cls.env['step.cosecha.tarja.registry.line'].create({
            'registry_id': cls.order.id, 'employee_id': cls.worker.id, 'qty_caja': 1, 'qty_kg': 4,
            'mobile_uid': 'private_t236_confirmed'})

    def transition(self, action, **changes):
        self.authenticate(self.user.login, 'private-fixture')
        scope = self.url_open('/api/harvest/bootstrap', timeout=90).json()['scope']
        payload = dict(scope=scope, action=action, work_order={'odoo_id': self.order.id},
                       delivery_uuids=[self.line.mobile_uid])
        payload.update(changes)
        return self.url_open('/api/harvest/orders/transition', data=json.dumps(payload),
                             headers={'Content-Type': 'application/json'})

    def test_native_lifecycle_preserves_erp_state_and_audits_actor(self):
        order = self.order.with_user(self.user)
        for action, expected in [('close', 'closed'), ('review', 'reviewed'), ('send', 'sent')]:
            order._harvest_transition(action, [self.line.mobile_uid])
            self.assertEqual(order.mobile_status, expected)
            self.assertEqual(order.state, 'in')
            self.assertEqual(order.mobile_state_user_id, self.user)
            self.assertTrue(order.mobile_state_date)
            timestamp = order.mobile_state_date
            order._harvest_transition(action, [self.line.mobile_uid])
            self.assertEqual(order.mobile_state_date, timestamp)

    def test_incomplete_or_invalid_manifest_cannot_close(self):
        for manifest in ([self.line.mobile_uid, 'missing'], ['missing'], 'invalid', [False],
                         [self.line.mobile_uid, self.line.mobile_uid]):
            with self.assertRaises(ValidationError):
                self.order._harvest_transition('close', manifest)
        self.assertEqual(self.order.mobile_status, 'progress')

    def test_out_of_order_transitions_are_rejected(self):
        for action in ('review', 'send', 'unknown'):
            with self.assertRaises(ValidationError):
                self.order._harvest_transition(action, [])
        self.assertEqual(self.order.mobile_status, 'progress')

    def test_native_write_permissions_are_required(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.order.with_user(public)._harvest_transition('close', [])

    def test_http_transition_confirms_native_relation_and_scope(self):
        response = self.transition('close')
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['order']['odoo_id'], self.order.id)
        self.assertEqual(payload['order']['status'], 'Cerrada')
        self.assertEqual(payload['confirmed_delivery_uuids'], [self.line.mobile_uid])
        self.assertTrue(payload['order']['can_transition'])

    def test_changed_context_rejects_transition_without_changing_order(self):
        response = self.transition('close', scope='changed-context')
        self.assertEqual(response.status_code, 409)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.mobile_status, 'progress')

    def test_closed_order_rejects_new_delivery_but_retries_keep_native_identity(self):
        self.order._harvest_transition('close', [self.line.mobile_uid])
        self.authenticate(self.user.login, 'private-fixture')
        scope = self.url_open('/api/harvest/bootstrap', timeout=90).json()['scope']
        def sync(uuid):
            return self.url_open('/api/harvest/sync', data=json.dumps({'scope': scope, 'records': [{
                'client_uuid': uuid, 'worker_id': self.worker.id, 'boxes': 1, 'kilos': 4,
                'work_order': {'odoo_id': self.order.id}}]}), headers={'Content-Type': 'application/json'}).json()
        retry = sync(self.line.mobile_uid)
        self.assertTrue(retry['ok'], retry)
        self.assertEqual(retry['results'][0]['work_order_id'], self.order.id)
        rejected = sync('private_t236_after_close')
        self.assertFalse(rejected['ok'], rejected)
        self.assertFalse(self.env['step.cosecha.tarja.registry.line'].search([
            ('mobile_uid', '=', 'private_t236_after_close')]))
