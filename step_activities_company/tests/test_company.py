from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestActivitiesCompany(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.first = cls.env.company
        cls.second = cls.env['res.company'].create({'name': 'QA Actividades'})
        cls.operator = new_test_user(
            cls.env, login='qa.activities.company', groups='base.group_user',
            company_id=cls.first.id, company_ids=[(6, 0, (cls.first | cls.second).ids)],
        )
        cls.partner = cls.env['res.partner'].create({'name': 'QA Contratista'})

    def _as_operator(self, model, companies):
        return self.env[model].with_user(self.operator).with_context(allowed_company_ids=companies.ids)

    def _documents(self, companies, kind):
        company = companies[:1]
        crew = self._as_operator('hr.salary.custom', companies).create({
            'name': 'QA Cuadrilla', 'group_type': kind, 'partner_id': self.partner.id,
        })
        field = 'salary_id' if kind == 'propio' else 'salary_id_contrac'
        tarja = self._as_operator('step.tarja', companies).create({
            field: crew.id, 'partner_id': self.partner.id, 'tarja_type': kind,
        })
        farm = self.env['step.fundo'].with_company(company).create({'name': 'QA Fundo'})
        cost = self._as_operator('step.tarja.cost', companies).create({
            'name': 'QA Costeo', 'fundo_id': farm.id, 'tarja_type': kind,
        })
        self.assertEqual(crew.company_id | tarja.company_id | cost.company_id, company)
        line_model = 'hr.salary.custom.line' if kind == 'propio' else 'hr.salary.contract.line'
        return [
            crew, tarja, cost,
            self._as_operator(line_model, companies).create({'salary_id': crew.id}),
            self._as_operator('step.tarja.registry', companies).create({'tarja_id': tarja.id}),
            self._as_operator('step.tarja.line', companies).create({'tarja_id': tarja.id}),
            self._as_operator('step.tarja.cost.line', companies).create({'tarja_cost_id': tarja.id}),
        ]

    def test_current_company_limits_documents_and_lines_in_both_flows(self):
        for kind in ('propio', 'contratista'):
            records_a = self._documents(self.first | self.second, kind)
            records_b = self._documents(self.second | self.first, kind)
            for companies, local, foreign in (
                (self.first | self.second, records_a, records_b),
                (self.second | self.first, records_b, records_a),
            ):
                for record, other in zip(local, foreign):
                    model = self._as_operator(record._name, companies)
                    domain = [('id', 'in', [record.id, other.id])]
                    self.assertEqual(model.search(domain).ids, record.ids)
                    self.assertEqual(model.search_count(domain), 1)
                    self.assertEqual(model.browse(record.id).read(['id']), [{'id': record.id}])
                    with self.assertRaises(AccessError):
                        model.browse(other.id).read(['id'])

    def test_foreign_company_and_parent_are_rejected_on_create(self):
        company_context = self.first | self.second
        crew, tarja, *_ = self._documents(self.second | self.first, 'propio')
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._as_operator('hr.salary.custom', company_context).create({
                'name': 'QA Otra empresa', 'company_id': self.second.id,
            })
        for model, parent, record in (
            ('hr.salary.custom.line', 'salary_id', crew),
            ('step.tarja.registry', 'tarja_id', tarja),
            ('step.tarja.cost.line', 'tarja_cost_id', tarja),
        ):
            with self.assertRaises(AccessError), self.cr.savepoint():
                self._as_operator(model, company_context).create({parent: record.id})
