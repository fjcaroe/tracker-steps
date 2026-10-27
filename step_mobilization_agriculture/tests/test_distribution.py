from psycopg2.errors import ForeignKeyViolation
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.addons.step_mobilization.tests.common import MobilizationCommon


@tagged('post_install', '-at_install')
class AgriculturalDistributionCase(MobilizationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.farm=cls.env['step.fundo'].create({'name':'Mobilization fixture farm','company_id':cls.company.id})
        cls.other_farm=cls.env['step.fundo'].create({'name':'Different fixture farm','company_id':cls.company.id})
        center_plan=cls.env['account.analytic.plan'].create({'name':'Mobilization fixture center'})
        activity_plan=cls.env['account.analytic.plan'].create({'name':'Mobilization fixture activity'})
        cls.center=cls.env['account.analytic.account'].create({'name':'Mobilization fixture center',
            'plan_id':center_plan.id,'company_id':cls.company.id})
        cls.activity=cls.env['account.analytic.account'].create({'name':'Mobilization fixture activity',
            'plan_id':activity_plan.id,'company_id':cls.company.id})
        cls.labor=cls.env['product.template'].create({'name':'Mobilization fixture labor',
            'is_labor':True,'actividad_id':cls.activity.id})

    def seed_tarja(self):
        crew=self.env['hr.salary.custom'].create({'name':'Distribution fixture crew','company_id':self.company.id})
        return self.env['step.tarja'].create({'name':'Distribution fixture tarja','salary_id':crew.id,
            'date':'2026-10-27','fundo_id':self.farm.id,'company_id':self.company.id,
            'tarja_line':[(0,0,{'employee_id':self.employee_1.id,'cost_id':self.center.id,'labor_id':self.labor.id})]})

    def test_real_tarja_cost_distribution_and_balanced_accounting(self):
        tarja=self.seed_tarja()
        trip=self._make_trip(date=tarja.date,fundo_id=self.farm.id)
        trip.action_open()
        self.env['step.movi.registry.line'].create({'movi_id':trip.id,'employee_id':self.employee_1.id,'operacion':'in'})
        trip.action_close();trip.action_validate();trip.action_costeo()
        self.assertEqual(trip.movi_cost_line.cost_id,self.center)
        self.assertEqual(trip.movi_cost_line.labor_id,self.labor)
        self.assertEqual(trip.movi_cost_line.cost_total,1000)
        distribution=trip.movi_cost_line._get_analytic_distribution()
        self.assertEqual(distribution,{str(self.center.id)+','+str(self.activity.id):100})
        trip.action_conta()
        self.assertTrue(trip.invoice_id)
        self.assertAlmostEqual(sum(trip.invoice_id.line_ids.mapped('debit')),
                               sum(trip.invoice_id.line_ids.mapped('credit')))
        self.assertEqual(tarja.tarja_line.cost_id,self.center)

    def test_lookup_uses_current_farm_date_company_and_employee(self):
        self.seed_tarja()
        trip=self._make_trip(date='2026-10-27',fundo_id=self.farm.id)
        self.assertEqual(trip._get_cost_distribution_hook(self.employee_1),
                         {'cost_id':self.center.id,'labor_id':self.labor.id})
        self.assertFalse(trip._get_cost_distribution_hook(self.employee_2))
        trip.fundo_id=self.other_farm
        self.assertFalse(trip._get_cost_distribution_hook(self.employee_1))
        trip.fundo_id=self.farm;trip.date='2026-10-28'
        self.assertFalse(trip._get_cost_distribution_hook(self.employee_1))
        trip.date='2026-10-27'
        other=self.env['res.company'].create({'name':'Other distribution fixture company'})
        other_trip=self.env['step.movi.registry'].new({'company_id':other.id,
            'fundo_id':self.farm.id,'date':'2026-10-27'})
        self.assertFalse(other_trip._get_cost_distribution_hook(self.employee_1))

    def test_recost_reads_updated_original_tarja_relation(self):
        tarja=self.seed_tarja()
        trip=self._make_trip(date=tarja.date,fundo_id=self.farm.id)
        self.assertTrue(trip._get_cost_distribution_hook(self.employee_1)['cost_id'])
        tarja.tarja_line.cost_id=False
        self.assertFalse(trip._get_cost_distribution_hook(self.employee_1)['cost_id'])

    def test_farm_with_trip_cannot_delete_its_operational_history(self):
        trip=self._make_trip(fundo_id=self.farm.id)
        with self.assertRaises(ForeignKeyViolation),mute_logger('odoo.sql_db'),self.cr.savepoint():
            self.farm.unlink()
        self.assertTrue(trip.exists())
