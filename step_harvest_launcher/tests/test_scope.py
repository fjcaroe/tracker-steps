import json
from urllib.parse import urlsplit

from odoo import Command, fields
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.addons.step_harvest_launcher.controllers.scope import scope_token


@tagged('post_install', '-at_install')
class HarvestScopeTokenCase(TransactionCase):
    def test_database_user_company_and_restored_database_are_distinct(self):
        values = ['private_db', 'private_uuid', 10, 20]
        token = scope_token(*values)
        self.assertEqual(len(token), 64)
        self.assertEqual(token, scope_token(*values))
        for index, other in enumerate(['other_db', 'other_uuid', 11, 21]):
            changed = values.copy()
            changed[index] = other
            self.assertNotEqual(token, scope_token(*changed))


@tagged('post_install', '-at_install')
class HarvestNativeScopeCase(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.companies = cls.env['res.company'].create([
            {'name': 'Private Harvest scope A'}, {'name': 'Private Harvest scope B'}])
        cls.users = cls.env['res.users']
        cls.workers = cls.env['hr.employee']
        for index, company in enumerate(cls.companies):
            for code in ('step_cosecha_pro_seq', 'step_cosecha_contra_seq'):
                cls.env['ir.sequence'].create({'name': 'Private T232 sequence', 'code': code,
                    'company_id': company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE'})
            user = new_test_user(cls.env, login='private_harvest_scope_%s' % index,
                password='private-fixture', company_id=company.id,
                company_ids=[Command.set(cls.companies.ids if index == 0 else company.ids)],
                groups='base.group_user,hr.group_hr_user,analytic.group_analytic_accounting')
            cls.users |= user
            cls.workers |= cls.env['hr.employee'].with_company(company).create({
                'name': 'Private Harvest worker %s' % index, 'company_id': company.id, 'pin': str(9823100 + index)})
        cls.orders = cls.env['step.cosecha.registry']
        for index, company in enumerate(cls.companies):
            reference = 'PRIVATE-T232-%s' % index
            cls.orders |= cls.env['step.cosecha.registry'].with_company(company).create({
                'name': reference, 'folio': reference, 'mobile_work_order': reference,
                'type_tarea': 'propio', 'product_uom_id': cls.env.ref('uom.product_uom_kgm').id,
                'date': fields.Datetime.now(), 'company_id': company.id,
                'responsable_id': cls.users[index].id})

    def get_payload(self, path):
        # A fresh destination copy can initialize a large native registry on
        # its first HTTP request. Keep identity and permission assertions intact
        # while allowing that bounded cold start to finish.
        response = self.url_open(path, timeout=90)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_anonymous_session_has_no_business_identity(self):
        data = self.get_payload('/api/harvest/session')
        self.assertFalse(data['connected'])
        self.assertFalse(data['scope'])
        self.assertFalse(data['company'])

    def test_harvest_job_catalog_uses_native_reference_route(self):
        self.authenticate(self.users[0].login, 'private-fixture')
        result = self.get_payload('/api/harvest/ref/jobs')
        self.assertTrue(result['ok'])
        self.assertIsInstance(result['items'], list)

    def clear_company_cookie(self):
        for cookie in list(self.opener.cookies):
            if cookie.name == 'cids':
                self.opener.cookies.clear(cookie.domain, cookie.path, cookie.name)

    def test_company_selection_uses_the_native_cookie_before_reads_and_uploads(self):
        self.authenticate(self.users[0].login, 'private-fixture')
        original = self.get_payload('/api/harvest/bootstrap')['scope']
        try:
            for separator in ('-', ','):
                self.clear_company_cookie()
                self.opener.cookies.set('cids', separator.join(map(str, reversed(self.companies.ids))))
                session = self.get_payload('/api/harvest/session')
                self.assertEqual(self.get_payload('/api/harvest/health')['scope'], session['scope'])
                data = self.get_payload('/api/harvest/bootstrap')
                self.assertEqual(data['company']['id'], self.companies[1].id)
                self.assertEqual(data['scope'], session['scope'])
                self.assertNotEqual(data['scope'], original)
                self.assertEqual([row['odoo_id'] for row in data['orders']], self.orders[1].ids)
                self.assertNotIn(self.workers[0].id, [row['id'] for row in data['workers']])
                response = self.url_open('/api/harvest/sync', data=json.dumps({'scope': original,
                    'records': [{'client_uuid': 'private_old_company_cookie'}]}),
                    headers={'Content-Type': 'application/json'})
                self.assertEqual(response.status_code, 409)
        finally:
            self.clear_company_cookie()

    def test_foreign_or_malformed_company_cookie_is_rejected(self):
        self.authenticate(self.users[1].login, 'private-fixture')
        try:
            for value in (str(self.companies[0].id), str(self.companies[1].id)+'-invalid'):
                self.clear_company_cookie()
                self.opener.cookies.set('cids', value)
                for route in ('session', 'bootstrap'):
                    response = self.url_open('/api/harvest/'+route)
                    self.assertEqual(response.status_code, 403)
                    self.assertFalse(response.json()['ok'])
        finally:
            self.clear_company_cookie()

    def test_private_launcher_never_redirects_the_review_to_production(self):
        response = self.url_open('/harvest/open', allow_redirects=False)
        self.assertEqual(response.status_code, 302)
        target = urlsplit(response.headers['Location'])
        self.assertEqual(target.path, '/cosecha/')
        self.assertIn(target.hostname, (None, '127.0.0.1', 'localhost'))

    def test_native_reads_follow_the_authenticated_company(self):
        scopes = []
        for index, user in enumerate(self.users):
            self.authenticate(user.login, 'private-fixture')
            session = self.get_payload('/api/harvest/session')
            data = self.get_payload('/api/harvest/bootstrap')
            self.assertEqual(session['scope'], data['scope'])
            self.assertEqual(data['company']['id'], self.companies[index].id)
            ids = [worker['id'] for worker in data['workers']]
            self.assertIn(self.workers[index].id, ids)
            self.assertNotIn(self.workers[1-index].id, ids)
            self.assertEqual([row['odoo_id'] for row in data['orders']], self.orders[index].ids)
            scopes.append(data['scope'])
        self.assertNotEqual(*scopes)

    def test_old_or_foreign_scope_cannot_upload_into_current_company(self):
        self.authenticate(self.users[0].login, 'private-fixture')
        original = self.get_payload('/api/harvest/bootstrap')['scope']
        self.authenticate(self.users[1].login, 'private-fixture')
        current = self.get_payload('/api/harvest/bootstrap')['scope']
        self.assertNotEqual(original, current)
        before = self.env['step.cosecha.registry'].search_count([])
        for token in (original, None):
            response = self.url_open('/api/harvest/sync', data=json.dumps({
                'scope': token, 'records': [{'client_uuid': 'private_foreign_attempt'}]}),
                headers={'Content-Type': 'application/json'})
            self.assertEqual(response.status_code, 409)
            self.assertFalse(response.json()['ok'])
        self.assertEqual(self.env['step.cosecha.registry'].search_count([]), before)
        # A valid identity reaches the native input validation, which still
        # rejects an empty upload without creating a harvest operation.
        response = self.url_open('/api/harvest/sync', data=json.dumps({'scope': current, 'records': []}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422)

    def test_native_order_upload_is_idempotent_and_rejects_foreign_relations(self):
        self.authenticate(self.users[0].login, 'private-fixture')
        data = self.get_payload('/api/harvest/bootstrap')
        record = {'client_uuid': 'private_t232_native_upload', 'worker_id': self.workers[0].id,
            'tarja': 'PRIVATE-T232', 'row': 'Private row', 'boxes': 1, 'kilos': 4,
            'event_datetime': '2026-11-23T12:00:00Z', 'work_order': data['orders'][0]}
        payload = {'scope': data['scope'], 'records': [record]}
        first = self.url_open('/api/harvest/sync', data=json.dumps(payload), headers={'Content-Type': 'application/json'}).json()
        self.assertTrue(first['ok'], first)
        second = self.url_open('/api/harvest/sync', data=json.dumps(payload), headers={'Content-Type': 'application/json'}).json()
        self.assertTrue(second['ok'], second)
        self.assertEqual(first['results'][0]['id'], second['results'][0]['id'])
        line = self.env['step.cosecha.tarja.registry.line'].browse(first['results'][0]['id'])
        self.assertEqual(line.registry_id, self.orders[0])
        self.assertEqual(line.employee_id, self.workers[0])
        for key, value in [('worker_id', self.workers[1].id), ('work_order', {'odoo_id': self.orders[1].id})]:
            changed = dict(record, client_uuid='private_t232_foreign_' + key)
            changed[key] = value
            result = self.url_open('/api/harvest/sync', data=json.dumps({'scope': data['scope'], 'records': [changed]}),
                headers={'Content-Type': 'application/json'}).json()
            self.assertFalse(result['ok'])
            self.assertFalse(self.env['step.cosecha.tarja.registry.line'].search([
                ('mobile_uid', '=', changed['client_uuid'])]))

    def test_order_without_tarja_rejects_folio_and_retains_worker_and_quantity(self):
        order = self.orders[0]
        order.mobile_without_tarja = True
        self.authenticate(self.users[0].login, 'private-fixture')
        data = self.get_payload('/api/harvest/bootstrap')
        self.assertTrue(data['allows_without_tarja'])
        native = next(row for row in data['orders'] if row['odoo_id'] == order.id)
        self.assertTrue(native['without_tarja'])
        record = {'client_uuid': 'private_t243_delivery', 'worker_id': self.workers[0].id,
                  'tarja': '', 'boxes': 2, 'kilos': 4.27, 'work_order': native}
        headers = {'Content-Type': 'application/json'}
        rejected = self.url_open('/api/harvest/sync', data=json.dumps({'scope': data['scope'],
            'records': [dict(record, client_uuid='private_t243_unexpected_folio', tarja='UNEXPECTED')]}), headers=headers).json()
        self.assertFalse(rejected['ok'])
        payload = json.dumps({'scope': data['scope'], 'records': [record]})
        result = self.url_open('/api/harvest/sync', data=payload, headers=headers).json()
        self.assertTrue(result['ok'], result)
        line = self.env['step.cosecha.tarja.registry.line'].browse(result['results'][0]['id'])
        self.assertFalse(line.num_tarja)
        self.assertEqual(line.employee_id, self.workers[0])
        self.assertEqual((line.qty_caja, line.qty_kg), (2, 4.27))
        repeat = self.url_open('/api/harvest/sync', data=payload, headers=headers).json()
        self.assertEqual(repeat['results'][0]['id'], line.id)
        closed = self.url_open('/api/harvest/orders/transition', data=json.dumps({'scope': data['scope'],
            'work_order': native, 'action': 'close', 'delivery_uuids': [record['client_uuid']]}), headers=headers).json()
        self.assertTrue(closed['ok'], closed)
        self.assertEqual(closed['order']['status'], 'Cerrada')

    def test_plot_catalog_tracks_center_and_upload_saves_native_relation(self):
        company, foreign_company = self.companies
        env = self.env(context=dict(self.env.context, allowed_company_ids=self.companies.ids))
        plan = (company.management_actual_center_plan_id
                if 'management_actual_center_plan_id' in company._fields else False)
        if not plan:
            plan = env['account.analytic.plan'].create({'name': 'Centro Costos'})
        first, other, foreign = env['account.analytic.account'].create([
            {'name': 'Private T233 A', 'company_id': company.id, 'plan_id': plan.id},
            {'name': 'Private T233 B', 'company_id': company.id, 'plan_id': plan.id},
            {'name': 'Private T233 foreign', 'company_id': foreign_company.id, 'plan_id': plan.id},
        ])
        plots = env['step.cuartel.line'].create([
            {'name': 'Private plot', 'centro_id': center.id} for center in (first, other, foreign)
        ])
        farm = env['step.fundo'].create({'name': 'Private T233 farm', 'company_id': company.id})
        species = env['step.especie'].create({
            'name': 'Private T233 species', 'type_especie': 'frutal',
            'group_especie': 'baya', 'company_id': company.id})
        group = env['step.grupo.variedad'].create({
            'name': 'Private T233 group', 'especie_id': species.id, 'company_id': company.id})
        variety = env['step.variedad'].create({
            'name': 'Private T233 variety', 'cod_variedad': 'T233-PRIVATE',
            'especie_id': species.id, 'grupo_variedad_id': group.id, 'company_id': company.id})
        crew = env['hr.salary.custom'].create({
            'name': 'Private T233 crew', 'group_type': 'propio', 'company_id': company.id})
        contractor = env['res.partner'].create({'name': 'Private Harvest contractor', 'is_company': True})
        contractor_crew = env['hr.salary.custom'].create({
            'name': 'Private Harvest contractor crew', 'group_type': 'contratista',
            'company_id': company.id, 'partner_id': contractor.id})

        self.authenticate(self.users[0].login, 'private-fixture')
        data = self.get_payload('/api/harvest/bootstrap')
        self.assertEqual(data['company']['id'], company.id)
        crews = {row['id']: row for row in data['crews']}
        self.assertEqual(crews[crew.id]['type'], 'propio')
        self.assertFalse(crews[crew.id]['contractor'])
        self.assertEqual(crews[contractor_crew.id]['type'], 'contratista')
        self.assertEqual(crews[contractor_crew.id]['contractor']['id'], contractor.id)
        choices = {center['id']: center['cuarteles'] for center in data['cost_centers']}
        self.assertIn(first.id, choices)
        self.assertIn(other.id, choices)
        self.assertEqual([plot['id'] for plot in choices[first.id]], plots[0].ids)
        self.assertEqual([plot['id'] for plot in choices[other.id]], plots[1].ids)
        self.assertNotIn(foreign.id, choices)
        order = {'id': 'PRIVATE-T233', 'farm_id': farm.id, 'variety_id': variety.id,
                 'cost_id': first.id, 'crew_id': crew.id, 'approver_id': self.users[0].id}

        def upload(suffix, **order_changes):
            record = {'client_uuid': 'private_t233_' + suffix, 'worker_id': self.workers[0].id,
                      'tarja': 'PRIVATE-T233', 'boxes': 1, 'kilos': 4,
                      'work_order': dict(order, **order_changes)}
            response = self.url_open('/api/harvest/sync', data=json.dumps({
                'scope': data['scope'], 'records': [record]}), headers={'Content-Type': 'application/json'})
            return response.json()['results'][0]

        for plot in plots[1:]:
            self.assertFalse(upload(str(plot.id), cuartel_id=plot.id)['ok'])
        self.assertIn(self.users[0].id, [user['id'] for user in data['approvers']])
        self.assertNotIn(self.users[1].id, [user['id'] for user in data['approvers']])
        self.assertFalse(upload('foreign_approver', id='PRIVATE-FOREIGN-APPROVER',
                                approver_id=self.users[1].id)['ok'])
        self.assertFalse(env['step.cosecha.registry'].search([('mobile_work_order', '=', 'PRIVATE-FOREIGN-APPROVER')]))
        result = upload('valid', cuartel_id=plots[0].id)
        self.assertTrue(result['ok'], result)
        saved = env['step.cosecha.registry'].browse(result['work_order_id'])
        self.assertEqual(saved.cuartel_id, plots[0])
        self.assertEqual(saved.mobile_approver_id, self.users[0])
        self.assertEqual(upload('valid', cuartel_id=plots[0].id)['id'], result['id'])
        self.assertFalse(upload('conflict', cuartel_id=plots[1].id)['ok'])
        published = next(item for item in self.get_payload('/api/harvest/bootstrap')['orders']
                         if item['odoo_id'] == saved.id)
        self.assertEqual(published['cuartel_id'], plots[0].id)
        self.assertEqual(published['cuartel'], plots[0].display_name)
        self.assertEqual(published['crew_id'], crew.id)
        self.assertEqual(published['crew_type'], 'propio')
        contractor_result = upload('contractor', id='PRIVATE-T237-CONTRACTOR', crew_id=contractor_crew.id)
        self.assertTrue(contractor_result['ok'], contractor_result)
        contractor_order = env['step.cosecha.registry'].browse(contractor_result['work_order_id'])
        self.assertEqual(contractor_order.type_tarea, 'contratista')
        self.assertEqual(contractor_order.partner_id, contractor)
        self.assertEqual(contractor_order.salary_id_contrac, contractor_crew)
        order.pop('approver_id')
        legacy = upload('old_draft', id='PRIVATE-T233-LEGACY')
        self.assertTrue(legacy['ok'], legacy)
        legacy_order = env['step.cosecha.registry'].browse(legacy['work_order_id'])
        self.assertFalse(legacy_order.cuartel_id)
        self.assertEqual(legacy_order.mobile_approver_id, self.users[0])
