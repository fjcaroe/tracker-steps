import json
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval


@tagged('post_install', '-at_install')
class HarvestLifecycleCase(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private Harvest lifecycle'})
        cls.user = new_test_user(cls.env, login='private_harvest_lifecycle', password='private-fixture',
            company_id=cls.company.id, company_ids=[Command.set(cls.company.ids)],
            groups='base.group_user,hr.group_hr_user,analytic.group_analytic_accounting')
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
            self.assertEqual(order.state, 'in' if action == 'close' else 'apro')
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
        for action in ('approve', 'review', 'send', 'unknown'):
            with self.assertRaises(ValidationError):
                self.order._harvest_transition(action, [])
        self.assertEqual(self.order.mobile_status, 'progress')
        self.assertEqual(self.order.state, 'in')
        self.assertFalse(self.order.mobile_approver_id)
        self.assertFalse(self.order.mobile_approved_by_id)

    def test_native_write_permissions_are_required(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.order.with_user(public)._harvest_transition('close', [])

    def test_standard_delivery_uses_box_count_and_snapshot_while_manual_keeps_kilos(self):
        packaging = self.env['product.packaging'].create({
            'name': 'Private harvest packaging', 'qty': 1,
            'product_id': self.env['product.product'].create({'name': 'Private harvest fruit'}).id,
            'step_packaging_group': 'harvest', 'step_export_kg_per_box': 3.455,
        })
        standard = self.order.copy({'mobile_work_order': 'PRIVATE-T242',
            'mobile_standard_weight': True, 'mobile_packaging_id': packaging.id,
            'mobile_kg_per_box': packaging.step_export_kg_per_box,
            'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            'tarja_registry_line': [Command.clear()]})
        packaging.step_export_kg_per_box = 4.0
        rows = self.env['step.cosecha.tarja.registry.line']
        values = {'employee_id': self.worker.id, 'qty_kg': 9.27, 'qty_caja': 3, 'quantity': 9.27}
        standard_line, manual_line = rows.create([
            dict(values, registry_id=standard.id, mobile_uid='private_t242_standard'),
            dict(values, registry_id=self.order.id, mobile_uid='private_t242_manual'),
        ])
        self.assertEqual((standard_line.qty_caja, standard_line.qty_kg, standard_line.quantity), (3, 10.37, 3))
        self.assertEqual((standard.total_boxes, standard.total_kilos), (3, 10.37))
        self.assertEqual((manual_line.qty_kg, manual_line.quantity), (9.27, 9.27))
        with self.assertRaises(ValidationError):
            rows.create(dict(values, registry_id=standard.id, mobile_uid='private_t242_fraction', qty_caja=1.5))

    def test_reopen_revokes_only_the_native_approval_created_by_harvest(self):
        order = self.order.with_user(self.user)
        for action in ('close', 'approve'):
            order._harvest_transition(action, [self.line.mobile_uid])
        self.assertEqual(order.state, 'apro')
        self.assertEqual(order.mobile_approved_by_id, self.user)
        self.assertEqual(order.mobile_approver_id, self.user)
        self.assertEqual(order.mobile_approved_delivery_count, 1)
        self.assertTrue(order.mobile_approved_manifest)
        order._harvest_transition('reopen', ['not-yet-transmitted'])
        self.assertEqual(order.state, 'in')
        self.assertEqual(order.mobile_status, 'progress')
        self.assertFalse(order.mobile_approved_by_id)
        self.assertFalse(order.mobile_approved_manifest)
        self.assertEqual(order.mobile_approver_id, self.user)
        order._harvest_transition('reopen', [])
        self.assertEqual(order.state, 'in')

    def test_historical_approval_and_costing_are_not_reversed_on_mobile_reopen(self):
        order = self.order.with_user(self.user)
        for state in ('apro', 'costo', 'cont'):
            self.order.write({'state': state, 'mobile_status': 'progress', 'mobile_native_approval': False,
                         'mobile_approved_by_id': False})
            order._harvest_transition('close', [self.line.mobile_uid])
            order._harvest_transition('approve', [self.line.mobile_uid])
            self.assertEqual(order.state, state)
            self.assertFalse(order.mobile_native_approval)
            order._harvest_transition('reopen', [])
            self.assertEqual(order.state, state)

    def test_selected_approver_must_be_the_actor_and_have_native_access(self):
        other = new_test_user(self.env, login='private_other_harvest_approver', company_id=self.company.id,
                             company_ids=[Command.set(self.company.ids)], groups='base.group_user')
        order = self.order.with_user(self.user)
        order.mobile_approver_id = other
        order._harvest_transition('close', [self.line.mobile_uid])
        with self.assertRaises(AccessError):
            order._harvest_transition('approve', [self.line.mobile_uid])
        self.assertEqual(order.state, 'in')
        order.with_user(other)._harvest_transition('approve', [self.line.mobile_uid])
        self.assertEqual(order.mobile_approved_by_id, other)
        with self.assertRaises(ValidationError):
            order.mobile_approver_id = self.user

    def test_native_generic_writes_cannot_forge_the_mobile_approval_audit(self):
        order = self.order.with_user(self.user)
        for values in ({'mobile_status': 'sent'}, {'mobile_approved_by_id': self.user.id},
                       {'mobile_approved_manifest': 'forged'}):
            with self.assertRaises(AccessError):
                order.write(values)
        with self.assertRaises(AccessError):
            order.create({'name': 'Private forged approval', 'company_id': self.company.id,
                          'type_tarea': 'propio', 'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
                          'mobile_status': 'sent', 'mobile_approved_by_id': self.user.id})
        self.assertEqual(order.mobile_status, 'progress')

    def test_foreign_and_portal_users_cannot_be_selected_as_approvers(self):
        foreign_company = self.env['res.company'].create({'name': 'Private approval foreign company'})
        foreign = new_test_user(self.env, login='private_foreign_approver', company_id=foreign_company.id,
                               company_ids=[Command.set(foreign_company.ids)], groups='base.group_user')
        for user in (foreign, self.env.ref('base.public_user')):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.order.mobile_approver_id = user

    def test_sent_order_cannot_reopen_and_approval_is_idempotent(self):
        order = self.order.with_user(self.user)
        for action in ('close', 'approve'):
            order._harvest_transition(action, [self.line.mobile_uid])
        approved_at = order.mobile_approved_at
        digest = order.mobile_approved_manifest
        order._harvest_transition('approve', [self.line.mobile_uid])
        self.assertEqual((order.mobile_approved_at, order.mobile_approved_manifest), (approved_at, digest))
        order._harvest_transition('send', [self.line.mobile_uid])
        with self.assertRaises(ValidationError):
            order._harvest_transition('reopen', [])
        self.assertEqual(order.mobile_status, 'sent')

    def test_http_total_send_recovers_missing_delivery_and_retries_without_duplicates(self):
        self.assertEqual(self.transition('close').status_code, 200)
        approved = self.transition('approve').json()
        self.assertEqual(approved['order']['erp_state'], 'apro')
        self.assertEqual(approved['order']['approved_by_id'], self.user.id)
        pending = {'client_uuid': 'private_t236_total_send', 'worker_id': self.worker.id,
                   'boxes': 2, 'kilos': 7, 'tarja': 'PRIVATE-PENDING', 'work_order': {'odoo_id': self.order.id}}
        manifest = [self.line.mobile_uid, pending['client_uuid']]
        response = self.transition('send', records=[pending], delivery_uuids=manifest)
        self.assertEqual(response.status_code, 200, response.text)
        first = response.json()
        self.assertEqual(first['order']['status'], 'Enviada')
        self.assertEqual(first['order']['erp_state'], 'apro')
        self.assertFalse(first['results'][0]['duplicate'])
        self.assertEqual(first['results'][0]['client_uuid'], pending['client_uuid'])
        repeated = self.transition('send', records=[pending], delivery_uuids=manifest).json()
        self.assertTrue(repeated['ok'], repeated)
        self.assertTrue(repeated['results'][0]['duplicate'])
        self.assertEqual(first['results'][0]['id'], repeated['results'][0]['id'])
        self.assertEqual(first['order']['state_changed_at'], repeated['order']['state_changed_at'])
        self.assertEqual(self.env['step.cosecha.tarja.registry.line'].search_count([
            ('mobile_uid', '=', pending['client_uuid'])]), 1)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.mobile_approved_delivery_count, 2)

    def test_incomplete_total_send_rolls_back_deliveries_and_native_approval_changes(self):
        self.transition('close')
        self.transition('approve')
        self.order.invalidate_recordset()
        snapshot = self.order.mobile_approved_manifest, self.order.mobile_approved_at
        pending = {'client_uuid': 'private_t236_rollback_send', 'worker_id': self.worker.id, 'boxes': 1, 'kilos': 3}
        response = self.transition('send', records=[pending],
            delivery_uuids=[self.line.mobile_uid, pending['client_uuid'], 'private_still_missing'])
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.env['step.cosecha.tarja.registry.line'].search([('mobile_uid', '=', pending['client_uuid'])]))
        self.order.invalidate_recordset()
        self.assertEqual((self.order.mobile_approved_manifest, self.order.mobile_approved_at), snapshot)
        self.assertEqual((self.order.state, self.order.mobile_status), ('apro', 'reviewed'))

    def test_total_send_cannot_append_to_costed_orders_or_cross_order_manifests(self):
        self.transition('close')
        self.transition('approve')
        pending = {'client_uuid': 'private_t236_costed_send', 'worker_id': self.worker.id, 'boxes': 1, 'kilos': 3}
        self.order.state = 'costo'
        response = self.transition('send', records=[pending], delivery_uuids=[self.line.mobile_uid, pending['client_uuid']])
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.env['step.cosecha.tarja.registry.line'].search([('mobile_uid', '=', pending['client_uuid'])]))
        self.order.invalidate_recordset()
        self.assertEqual((self.order.state, self.order.mobile_status), ('costo', 'reviewed'))
        foreign = dict(pending, work_order={'odoo_id': self.order.id + 1})
        self.assertEqual(self.transition('send', records=[foreign],
            delivery_uuids=[self.line.mobile_uid, pending['client_uuid']]).status_code, 422)

    def test_only_selected_approver_can_reapprove_deliveries_during_total_send(self):
        self.transition('close')
        self.transition('approve')
        other = new_test_user(self.env, login='private_harvest_sender', password='private-fixture',
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
            groups='base.group_user,hr.group_hr_user,analytic.group_analytic_accounting')
        self.authenticate(other.login, 'private-fixture')
        scope = self.url_open('/api/harvest/bootstrap', timeout=90).json()['scope']
        pending = {'client_uuid': 'private_t236_unauthorized_sender', 'worker_id': self.worker.id, 'boxes': 1, 'kilos': 2}
        response = self.url_open('/api/harvest/orders/transition', data=json.dumps({
            'scope': scope, 'action': 'send', 'work_order': {'odoo_id': self.order.id},
            'delivery_uuids': [self.line.mobile_uid, pending['client_uuid']], 'records': [pending]}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.env['step.cosecha.tarja.registry.line'].search([('mobile_uid', '=', pending['client_uuid'])]))

    def test_http_transition_confirms_native_relation_and_scope(self):
        response = self.transition('close')
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['order']['odoo_id'], self.order.id)
        self.assertEqual(payload['order']['status'], 'Cerrada')
        self.assertEqual(payload['confirmed_delivery_uuids'], [self.line.mobile_uid])
        self.assertTrue(payload['order']['can_transition'])
        action = self.env.ref('step_cosecha.action_step_cosecha_registry')
        self.assertEqual(payload['order']['erp_url'], '/odoo/action-%s/%s' % (action.id, self.order.id))

    def test_bootstrap_links_both_tareo_types_to_their_native_actions(self):
        contractor = self.env['step.cosecha.registry'].with_company(self.company).create({
            'name': 'Private lifecycle contractor order', 'type_tarea': 'contratista',
            'product_uom_id': self.env.ref('uom.product_uom_kgm').id,
            'company_id': self.company.id, 'date': fields.Datetime.now()})
        self.authenticate(self.user.login, 'private-fixture')
        response = self.url_open('/api/harvest/bootstrap', timeout=90)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['ok'], data)
        orders = {row['odoo_id']: row for row in data['orders']}
        for order, xmlid in ((self.order, 'step_cosecha.action_step_cosecha_registry'),
                             (contractor, 'step_cosecha.action_step_cosecha_registry_contra')):
            action = self.env.ref(xmlid)
            self.assertEqual(action.res_model, 'step.cosecha.registry')
            self.assertEqual(orders[order.id]['erp_url'], '/odoo/action-%s/%s' % (action.id, order.id))

    def test_changed_context_rejects_transition_without_changing_order(self):
        response = self.transition('close', scope='changed-context')
        self.assertEqual(response.status_code, 409)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.mobile_status, 'progress')

    def test_legacy_order_without_mobile_alias_shows_confirmed_lifecycle(self):
        order = self.order.with_user(self.user)
        order.mobile_work_order = False
        name, folio = order.name, order.folio
        view = order.get_view(view_id=self.env.ref('step_cosecha.view_step_cosecha_registry_form').id, view_type='form')
        arch = etree.fromstring(view['arch'])
        state_field, = arch.xpath(".//field[@name='mobile_status']")
        expression = state_field.get('invisible')
        self.assertTrue(safe_eval(expression, {'mobile_work_order': False, 'mobile_state_date': False}))
        order._harvest_transition('close', [self.line.mobile_uid])
        self.assertFalse(safe_eval(expression, {'mobile_work_order': order.mobile_work_order,
                                               'mobile_state_date': order.mobile_state_date}))
        self.assertEqual(order.mobile_status, 'closed')
        self.assertFalse(order.mobile_work_order)
        self.assertEqual((order.name, order.folio), (name, folio))

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
