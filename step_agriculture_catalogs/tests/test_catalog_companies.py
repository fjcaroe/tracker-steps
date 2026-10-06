from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCatalogCompanies(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.a = cls.env.company
        cls.b = cls.env['res.company'].create({'name': 'QA empresas catálogo B'})
        cls.c = cls.env['res.company'].create({'name': 'QA empresas catálogo C'})
        cls.user = cls.env['res.users'].create({
            'name': 'QA catálogo usuario', 'login': 'qa_catalog_user',
            'company_id': cls.a.id, 'company_ids': [Command.set((cls.a | cls.b | cls.c).ids)],
            'groups_id': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def test_multiple_selected_companies_and_blank_shared(self):
        restricted = self.env['step.temporada'].create({'name': 'QA temporada AB', 'company_ids': [Command.set((self.a | self.b).ids)]})
        shared = self.env['step.temporada'].create({'name': 'QA temporada compartida', 'company_ids': [Command.clear()]})
        for company in (self.a, self.b, self.c):
            visible = self.env['step.temporada'].with_user(self.user).with_context(allowed_company_ids=company.ids).search([('id', 'in', (restricted | shared).ids)])
            self.assertIn(shared, visible)
            self.assertEqual(restricted.id in visible.ids, company != self.c)
        restricted.write({'company_ids': [Command.clear()]})
        self.assertFalse(restricted.company_id)
        self.assertFalse(restricted.company_ids)

    def test_legacy_single_company_writes_are_preserved(self):
        season = self.env['step.temporada'].create({'name': 'QA compatible', 'company_id': self.a.id})
        self.assertEqual(season.company_ids, self.a)
        season.company_id = self.b
        self.assertEqual(season.company_ids, self.b)
        self.assertEqual(season.company_id, self.b)

    def test_shared_species_requires_shared_parent_and_matching_group(self):
        species = self.env['step.especie'].create({'name': 'QA especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h', 'company_ids': [Command.clear()]})
        group = self.env['step.grupo.variedad'].create({'name': 'QA grupo', 'especie_id': species.id, 'company_ids': [Command.clear()]})
        variety = self.env['step.variedad'].create({'name': 'QA variedad', 'cod_variedad': 'QACAT', 'especie_id': species.id, 'grupo_variedad_id': group.id, 'company_ids': [Command.clear()]})
        self.assertFalse(variety.company_ids)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            species.write({'company_ids': [Command.set(self.a.ids)]})
        restricted = self.env['step.especie'].create({'name': 'QA especie A', 'type_especie': 'frutal', 'group_especie': 'fruta_h', 'company_id': self.a.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['step.grupo.variedad'].create({'name': 'QA incorrecto', 'especie_id': restricted.id, 'company_ids': [Command.clear()]})

    def test_native_company_check_uses_selected_companies(self):
        species = self.env['step.especie'].create({'name': 'QA check A', 'type_especie': 'frutal', 'group_especie': 'fruta_h', 'company_ids': [Command.set((self.a | self.b).ids)]})
        domain = species._check_company_domain(self.c)
        self.assertFalse(species.filtered_domain(domain))
        self.assertEqual(species.filtered_domain(species._check_company_domain(self.b)), species)
