# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'step_sawmill')
class TestSawmill(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env['product.product'].create({'name': 'Tabla 1x4 (test aserradero)'})
        cls.log = cls.env['product.product'].create({'name': 'Troza (test aserradero)'})
        cls.op = cls.env['step.sawmill.production.order'].create({'name': 'OP de prueba'})

    # -- secuencias y OP/OT ---------------------------------------------------
    def test_sequences_and_default_stage(self):
        self.assertTrue(self.op.number.startswith('OP-'))
        self.assertEqual(self.op.stage_id.name, 'Nuevo')
        ot = self.env['step.sawmill.work.order'].create({
            'name': 'OT de prueba', 'production_order_id': self.op.id})
        self.assertTrue(ot.number.startswith('OT-'))
        self.assertEqual(self.op.work_order_count, 1)
        action = self.op.action_view_work_orders()
        self.assertEqual(action['domain'], [('production_order_id', '=', self.op.id)])

    # -- cuadrilla ------------------------------------------------------------
    def test_crew_headcount_and_hours(self):
        emp1 = self.env['hr.employee'].create({'name': 'Operario 1'})
        emp2 = self.env['hr.employee'].create({'name': 'Operario 2'})
        crew = self.env['step.sawmill.crew'].create({
            'name': 'Cuadrilla A',
            'member_ids': [
                Command.create({'employee_id': emp1.id,
                                'time_in': datetime(2026, 1, 5, 8, 0),
                                'time_out': datetime(2026, 1, 5, 16, 30)}),
                Command.create({'employee_id': emp2.id}),
            ],
        })
        self.assertEqual(crew.headcount, 2)
        self.assertAlmostEqual(crew.member_ids[0].hours, 8.5)
        self.assertEqual(crew.member_ids[1].hours, 0.0)

    # -- aserrío --------------------------------------------------------------
    def _sawing(self, **extra):
        vals = {
            'raw_product_id': self.log.id,
            'date_start': datetime(2026, 1, 5, 8, 0),
            'date_stop': datetime(2026, 1, 5, 12, 30),
            'output_ids': [Command.create({'product_id': self.product.id, 'pieces': 10,
                                           'quantity': 1.5, 'quantity_m3': 0.4})],
        }
        vals.update(extra)
        return self.env['step.sawmill.sawing'].create(vals)

    def test_sawing_flow_and_totals(self):
        saw = self._sawing()
        self.assertTrue(saw.name.startswith('ASE-'))
        self.assertEqual(saw.state, 'draft')
        self.assertAlmostEqual(saw.total_hours, 4.5)
        saw.write({'cost_ids': [Command.create({
            'product_id': self.product.id, 'quantity': 2.0, 'pieces': 10,
            'cost_raw': 100.0, 'cost_own_labor': 40.0, 'cost_contract_labor': 10.0,
            'cost_supplies': 5.0, 'cost_expenses': 3.0, 'cost_machines': 2.0})]})
        line = saw.cost_ids
        self.assertAlmostEqual(line.cost_total, 160.0)
        self.assertAlmostEqual(line.unit_cost_uom, 80.0)
        self.assertAlmostEqual(line.unit_cost_piece, 16.0)
        self.assertAlmostEqual(saw.cost_total, 160.0)
        saw.action_authorize()
        saw.action_value()
        self.assertEqual(saw.state, 'valued')

    def test_cost_line_without_quantity_does_not_divide_by_zero(self):
        saw = self._sawing(cost_ids=[Command.create({'product_id': self.product.id, 'cost_raw': 10.0})])
        self.assertEqual(saw.cost_ids.unit_cost_uom, 0.0)
        self.assertEqual(saw.cost_ids.unit_cost_piece, 0.0)

    def test_state_guards(self):
        saw = self._sawing()
        with self.assertRaises(UserError):
            saw.action_value()          # no se salta la autorización
        saw.action_authorize()
        with self.assertRaises(UserError):
            saw.action_authorize()      # no se autoriza dos veces
        with self.assertRaises(UserError):
            saw.unlink()                # solo se borra en Ingresada
        saw.action_reset()
        saw.unlink()

    def test_reopen_valued_requires_manager(self):
        saw = self._sawing()
        saw.action_authorize()
        saw.action_value()
        user = self.env['res.users'].create({
            'name': 'Usuario aserradero', 'login': 'sawmill_user_test',
            'groups_id': [Command.set([self.env.ref('step_sawmill.group_sawmill_user').id])],
        })
        with self.assertRaises(UserError):
            saw.with_user(user).action_reset()
        saw.action_reset()  # el superusuario/administrador sí puede
        self.assertEqual(saw.state, 'draft')

    def test_input_line_total_cost(self):
        saw = self._sawing(input_ids=[Command.create({
            'product_id': self.log.id, 'quantity': 3.0, 'unit_cost': 12.5})])
        self.assertAlmostEqual(saw.input_ids.total_cost, 37.5)

    def test_headcount_follows_crew(self):
        emp = self.env['hr.employee'].create({'name': 'Operario 3'})
        crew = self.env['step.sawmill.crew'].create({
            'name': 'Cuadrilla B', 'member_ids': [Command.create({'employee_id': emp.id})]})
        saw = self._sawing(crew_id=crew.id)
        self.assertEqual(saw.headcount, 1)

    # -- elaboración: líneas con el padre correcto ----------------------------
    def test_elaboration_lines_and_single_parent(self):
        ela = self.env['step.sawmill.elaboration'].create({
            'output_ids': [Command.create({'product_id': self.product.id, 'pieces': 5})]})
        self.assertTrue(ela.name.startswith('ELA-'))
        self.assertEqual(ela.output_ids.elaboration_id, ela)
        saw = self._sawing()
        with self.assertRaises(ValidationError):
            self.env['step.sawmill.output.line'].create({
                'product_id': self.product.id,
                'sawing_id': saw.id, 'elaboration_id': ela.id})
        with self.assertRaises(ValidationError):
            self.env['step.sawmill.output.line'].create({'product_id': self.product.id})

    # -- secado / impregnado / certificación ----------------------------------
    def test_drying(self):
        dry = self.env['step.sawmill.drying'].create({
            'name': 'Secado de prueba',
            'date_start': datetime(2026, 1, 5, 8, 0),
            'date_stop': datetime(2026, 1, 6, 8, 0),
        })
        self.assertAlmostEqual(dry.real_hours, 24.0)
        dry.action_done()
        self.assertEqual(dry.state, 'done')
        with self.assertRaises(UserError):
            dry.action_done()

    def test_impregnation_and_certification(self):
        imp = self.env['step.sawmill.impregnation'].create({
            'name': 'HC-001',
            'date_start': datetime(2026, 1, 5, 8, 0),
            'date_stop': datetime(2026, 1, 5, 14, 15),
        })
        self.assertAlmostEqual(imp.total_time, 6.25)
        with self.assertRaises(UserError):
            imp.action_certify()        # antes hay que aprobar
        imp.action_approve()
        imp.action_certify()
        self.assertEqual(imp.state, 'certified')
        cert = self.env['step.sawmill.certification'].create({
            'name': 'Cert HC-001', 'impregnation_id': imp.id})
        self.assertEqual(cert.state, 'sent')
        cert.action_certify()
        self.assertEqual(cert.state, 'certified')
        self.assertTrue(cert.certification_date)

    # -- catálogos ------------------------------------------------------------
    def test_catalog_unique_name(self):
        self.env['step.sawmill.grade'].create({'name': 'Grado de prueba'})
        with self.assertRaises(ValidationError):
            self.env['step.sawmill.grade'].create({'name': 'grado de prueba'})

    def test_working_days_not_negative(self):
        with self.assertRaises(ValidationError):
            self.env['step.sawmill.working.days'].create({
                'name': 'Ene 26', 'month': '2026-01-01', 'working_days': -1})
