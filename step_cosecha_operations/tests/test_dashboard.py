from datetime import date
from unittest.mock import patch

from odoo import fields, Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class HarvestDashboardCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'Private T234 harvest',
            'gratifica': 0, 'step_seguro': 0, 'step_feriado': 0, 'step_ias': 0,
            'sema_corrida_legal': False})
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=self.company.ids, tz='America/Santiago'))
        self.registry = self.env['step.cosecha.registry']
        self.kg = self.env.ref('uom.product_uom_kgm')
        self.farm = self.env['step.fundo'].create({'name': 'Private T234 farm', 'company_id': self.company.id})
        self.species = self.env['step.especie'].create({'name': 'Private T234 fruit',
            'type_especie': 'frutal', 'group_especie': 'baya', 'company_id': self.company.id})
        self.tariff = self.env['product.pricelist'].create({'name': 'Private T234 rate',
            'currency_id': self.company.currency_id.id, 'company_id': self.company.id,
            'cosecha': True, 'group_type': 'propio', 'especie_id': self.species.id})

    def harvest(self, **values):
        return self.registry.create({'name': 'Private T234 order', 'company_id': self.company.id,
            'type_tarea': 'propio', 'product_uom_id': self.kg.id, 'date': '2026-11-24 12:00:00',
            'fundo_id': self.farm.id, 'pricelist_id': self.tariff.id, **values})

    def dashboard(self, **values):
        with patch.object(fields.Date, 'context_today', return_value=date(2026, 11, 24)):
            return self.registry.get_dashboard_data(**values)

    def test_today_and_yesterday_are_bounded_local_calendar_days(self):
        yesterday = self.harvest(date='2026-11-24 02:59:59')
        today = self.harvest(date='2026-11-24 03:00:00')
        self.harvest(date='2026-11-25 03:00:00')
        self.assertEqual([r['id'] for r in self.dashboard()['recent']], today.ids)
        self.assertEqual(self.dashboard()['recent'][0]['date_label'], '24-11-2026')
        self.assertEqual([r['id'] for r in self.dashboard(period='yesterday')['recent']], yesterday.ids)
        self.assertEqual(self.dashboard(period='all')['kpis']['records'], 3)
        with self.assertRaises(ValidationError):
            self.dashboard(period='invalid')

    def test_filters_combine_native_species_and_farm_in_the_active_company(self):
        wanted = self.harvest(tarja_kg=12)
        other_farm = self.farm.copy({'name': 'Private other farm'})
        self.harvest(fundo_id=other_farm.id, tarja_kg=99)
        foreign = self.env['res.company'].create({'name': 'Private foreign T234'})
        self.harvest(company_id=foreign.id, tarja_kg=999)
        data = self.dashboard(species_id=self.species.id, farm_id=self.farm.id)
        self.assertEqual([row['id'] for row in data['recent']], wanted.ids)
        self.assertEqual(data['kpis']['kilos'], 12)
        self.assertEqual(sum(data['states'].values()), 1)
        foreign_farm = self.env['step.fundo'].create({'name': 'Private foreign farm', 'company_id': foreign.id})
        with self.assertRaises(ValidationError):
            self.dashboard(farm_id=foreign_farm.id)

    def test_workers_hours_and_native_costs_do_not_rewrite_original_lines(self):
        employee = self.env['hr.employee'].create({'name': 'Private T234 worker', 'company_id': self.company.id})
        order = self.harvest(state='costo', tarja_kg=120, registry_line=[
            Command.create({'employee_id': employee.id, 'hrs': 4, 'sueldo_base': 1000}),
            Command.create({'employee_id': employee.id, 'hrs': 2, 'sueldo_base': 500}),
        ])
        self.env.flush_all()
        self.env.cr.execute('SELECT id, hrs, tarifa, sueldo_base FROM step_cosecha_registry_line WHERE registry_id=%s ORDER BY id', [order.id])
        before = self.env.cr.fetchall()
        row = self.dashboard()['recent'][0]
        self.assertEqual(row['workers'], 1)
        self.assertEqual(row['hours'], 6)
        self.assertAlmostEqual(row['average_kg'], 160)
        self.assertEqual(row['total_cost'], 1500)
        self.assertAlmostEqual(row['cost_per_kg'], 12.5)
        self.env.flush_all()
        self.env.cr.execute('SELECT id, hrs, tarifa, sueldo_base FROM step_cosecha_registry_line WHERE registry_id=%s ORDER BY id', [order.id])
        self.assertEqual(self.env.cr.fetchall(), before)

    def test_harvest_without_a_tariff_uses_its_native_variety_species(self):
        group = self.env['step.grupo.variedad'].create({'name': 'Private T234 group',
            'especie_id': self.species.id, 'company_id': self.company.id})
        variety = self.env['step.variedad'].create({'name': 'Private T234 variety',
            'cod_variedad': 'T234-P', 'especie_id': self.species.id,
            'grupo_variedad_id': group.id, 'company_id': self.company.id})
        order = self.harvest(pricelist_id=False, variedad_id=variety.id)
        self.assertFalse(order.especie_id)
        row = self.dashboard(species_id=self.species.id)['recent'][0]
        self.assertEqual(row['id'], order.id)
        self.assertEqual(row['species'], self.species.display_name)

    def test_contractor_uses_native_tarjas_hours_and_costs(self):
        workers = self.env['hr.employee'].create([{'name': 'Private T234 contractor '+str(i),
            'company_id': self.company.id} for i in range(2)])
        order = self.harvest(type_tarea='contratista', pricelist_id=False, state='costo',
            registry_tarja_line=[Command.create({'employee_id': worker.id, 'quantity': 100,
                'tarifa': 10, 'hrs': 8}) for worker in workers])
        row = order._dashboard_metrics()
        self.assertEqual(row['workers'], 2)
        self.assertEqual(row['hours'], 16)
        self.assertEqual(row['average_kg'], 100)
        self.assertEqual(row['total_cost'], 2000)
        self.assertEqual(row['cost_per_kg'], 10)

    def test_zero_bases_and_uncosted_orders_do_not_invent_ratios(self):
        order = self.harvest()
        row = order._dashboard_metrics()
        self.assertIsNone(row['average_kg'])
        self.assertIsNone(row['total_cost'])
        self.assertIsNone(row['cost_per_kg'])
        order.state = 'costo'
        self.assertEqual(order._dashboard_metrics()['total_cost'], 0)
        self.assertIsNone(order._dashboard_metrics()['cost_per_kg'])

    def test_daily_hours_are_configurable_per_company_and_validated(self):
        self.assertEqual(self.company.harvest_hours_per_day, 8)
        settings = self.env['res.config.settings'].create({'company_id': self.company.id})
        settings.harvest_hours_per_day = 7.5
        self.assertEqual(self.company.harvest_hours_per_day, 7.5)
        for hours in (0, -1, 25):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.company.harvest_hours_per_day = hours

    def test_table_pages_beyond_the_old_eight_rows_and_counts_all_matches(self):
        for i in range(51):
            self.harvest(name='Private order '+str(i))
        first = self.dashboard()
        second = self.dashboard(offset=50)
        self.assertEqual(first['kpis']['records'], 51)
        self.assertEqual(len(first['recent']), 50)
        self.assertEqual(len(second['recent']), 1)
        self.assertFalse({r['id'] for r in first['recent']} & {r['id'] for r in second['recent']})

    def test_portal_cannot_query_the_harvest_dashboard(self):
        portal = new_test_user(self.env, login='private_t234_portal', groups='base.group_portal')
        with self.assertRaises(AccessError):
            self.registry.with_user(portal).get_dashboard_data()
