from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestHarvestContainerControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'dispatch_dte_provider': 'third_party', 'step_fruit_inventory_enabled': True})
        cls.warehouse = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.producer = cls.env['res.partner'].create({'name': 'Productor envases QA219', 'is_productor': True})
        cls.driver = cls.env['res.partner'].create({'name': 'Chofer QA219', 'step_chofer': True})
        cls.fruit = cls.env['product.product'].create({'name': 'Fruta QA219', 'is_storable': True})
        cls.packaging = cls.env['product.packaging'].create({
            'name': 'Embalaje QA219', 'step_packaging_group': 'harvest', 'product_id': cls.fruit.id, 'qty': 1,
        })
        cls.container = cls.env['product.product'].create({
            'name': 'Caja retornable QA219', 'is_storable': True, 'tracking': 'lot',
            'step_is_harvest_container': True, 'step_harvest_packaging_id': cls.packaging.id,
        })
        cls.lots = cls.env['stock.lot'].create([
            {'name': 'Envases QA219-' + number, 'product_id': cls.container.id, 'company_id': cls.company.id}
            for number in ('1', '2')
        ])
        cls.root = cls.warehouse.lot_stock_id
        cls.quant = cls.env['stock.quant']
        for lot in cls.lots:
            cls.quant._update_available_quantity(cls.container, cls.root, 10, lot_id=lot)

    def _guide(self, with_fruit=False, quantity=4):
        lines = [Command.create({
            'product_id': self.container.id, 'description': self.container.name, 'lot_id': self.lots[1].id,
            'product_uom_id': self.container.uom_id.id, 'quantity': quantity, 'price_unit': 999,
        })]
        if with_fruit:
            lines += [Command.create({
                'product_id': self.fruit.id, 'description': self.fruit.name, 'quantity': 2, 'price_unit': 120,
                'product_uom_id': self.fruit.uom_id.id,
            })]
        return self.env['step.dispatch.guide'].create({
            'external_folio': 'T219-%s' % quantity, 'partner_id': self.producer.id,
            'carrier_id': self.driver.id, 'driver_partner_id': self.driver.id,
            'transfer_reason_id': self.env.ref('step_dispatch_guide.transfer_reason_1').id,
            'step_source_warehouse_id': self.warehouse.id, 'origin_address': 'Bodega QA',
            'destination_address': 'Predio QA', 'truck_plate': 'ABC123', 'line_ids': lines,
        })

    def test_native_mapping_and_return_with_fruit(self):
        form = Form(self.container.product_tmpl_id)
        self.assertEqual(form.step_harvest_packaging_id, self.packaging)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.packaging.step_packaging_group = 'export'
        guide = self._guide()
        guide.action_confirm()
        fundo = self.env['step.fundo'].create({
            'name': 'Predio QA219', 'partner_id': self.producer.id, 'company_id': self.company.id,
        })
        species = self.env['step.especie'].create({'name': 'Especie QA219', 'type_especie': 'frutal', 'group_especie': 'baya'})
        group = self.env['step.grupo.variedad'].create({'name': 'Grupo QA219', 'especie_id': species.id})
        variety = self.env['step.variedad'].create({
            'name': 'Variedad QA219', 'cod_variedad': 'T219-TEST', 'grupo_variedad_id': group.id,
        })
        package = self.env['stock.quant.package'].create({
            'name': 'QA219-C-1', 'is_fruit_tag': True, 'step_tag_kind': 'C', 'company_id': self.company.id,
        })
        receipt = self.env['stock.picking'].create({
            'partner_id': self.producer.id, 'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.warehouse.in_type_id.default_location_src_id.id,
            'location_dest_id': self.root.id, 'step_fruit_reception_kind': 'process',
            'fruit_fundo_id': fundo.id, 'fruit_species_id': species.id, 'fruit_variety_id': variety.id,
            'step_fruit_gross_kg': 55.0,
            'fruit_tag_line_ids': [Command.create({
                'tag_number': package.name, 'package_id': package.id, 'product_id': self.fruit.id,
                'packaging_id': self.packaging.id, 'quantity': 55, 'box_count': 3, 'kilos': 55,
                'variety_id': variety.id,
            })],
        })
        receipt.action_prepare_fruit_stock()
        receipt.button_validate()
        self.assertEqual(receipt.state, 'done')
        transfer = receipt.step_container_transfer_ids
        self.assertEqual(transfer.state, 'draft')
        self.assertEqual(transfer.line_ids.product_id, self.container)
        self.assertEqual(transfer.line_ids.quantity, 3)
        self.assertEqual(receipt.action_step_container_return()['res_id'], transfer.id)
        transfer.line_ids.write({'lot_id': self.lots[1].id, 'conservation': 'good', 'operating': 'dirty'})
        transfer.action_validate()
        self.assertEqual(transfer.picking_id.move_line_ids.lot_id, self.lots[1])
        self.assertEqual(transfer.picking_id.move_line_ids.step_container_operating, 'dirty')
        account = self.producer._step_container_location(self.company)
        self.assertEqual(self.quant._get_available_quantity(self.container, account), 1)

    def test_invoice_and_stock_are_independent_and_confirmation_is_idempotent(self):
        guide = self._guide(with_fruit=True)
        self.assertEqual(guide.amount_total, 240)
        guide.action_confirm()
        guide.action_confirm()
        transfer = guide.step_container_transfer_ids
        self.assertEqual(len(transfer), 1)
        self.assertEqual(transfer.state, 'done')
        self.assertEqual(transfer.picking_id.move_line_ids.lot_id, self.lots[1])
        self.assertEqual(guide.invoice_status, 'to_invoice')
        self.assertEqual([vals['product_id'] for _, _, vals in guide._prepare_invoice_line_vals()], self.fruit.ids)
        self.assertEqual(self.quant._get_available_quantity(self.container, self.root, lot_id=self.lots[0], strict=True), 10)
        with self.assertRaises(UserError), self.cr.savepoint():
            guide.action_cancel()

    def test_only_containers_no_invoice_and_insufficient_lot_rolls_back(self):
        guide = self._guide()
        guide.action_confirm()
        self.assertEqual(guide.invoice_status, 'no')
        self.assertFalse(guide._prepare_invoice_line_vals())
        other = self._guide(quantity=9)
        with self.assertRaises(UserError), self.cr.savepoint():
            other.action_confirm()
        self.assertEqual(other.state, 'draft')
        self.assertFalse(other.step_container_transfer_ids)

    def test_work_order_moves_only_confirmed_lot_and_accumulates_posted_expenses(self):
        plans = self.env['account.analytic.plan'].create(
            [{'name': 'QA219 ' + dimension} for dimension in ('temporada', 'centro', 'actividad', 'OT')])
        accounts = self.env['account.analytic.account'].create([
            {'name': plan.name, 'plan_id': plan.id, 'company_id': self.company.id}
            for plan in plans[:3]
        ])
        order = self.env['step.harvest.container.work.order'].create({
            'warehouse_id': self.warehouse.id, 'product_id': self.container.id, 'lot_id': self.lots[0].id,
            'quantity': 4, 'operation': 'wash', 'season_account_id': accounts[0].id,
            'center_account_id': accounts[1].id, 'activity_account_id': accounts[2].id,
            'work_plan_id': plans[3].id, 'assigned_conservation': 'good', 'assigned_operating': 'dirty',
        })
        order.action_complete()
        moved = order.picking_id.move_line_ids
        self.assertEqual(moved.lot_id, self.lots[0])
        self.assertEqual(moved.quantity, 4)
        self.assertEqual(moved.step_container_operating, 'clean')
        self.assertEqual(self.quant._get_available_quantity(self.container, self.root, lot_id=self.lots[0], strict=True), 6)
        journal = self.env['account.journal'].create({
            'name': 'Gastos QA219', 'code': 'Q219C', 'type': 'general', 'company_id': self.company.id,
        })
        debit = self.env['account.account'].create({
            'name': 'Gasto QA219', 'code': 'T219001', 'account_type': 'expense', 'company_ids': [Command.set(self.company.ids)],
        })
        credit = self.env['account.account'].create({
            'name': 'Contrapartida QA219', 'code': 'T219002', 'account_type': 'liability_current',
            'company_ids': [Command.set(self.company.ids)],
        })
        entry = self.env['account.move'].create({
            'journal_id': journal.id, 'step_container_work_order_id': order.id,
            'line_ids': [Command.create({'name': 'Lavado', 'account_id': debit.id, 'debit': 200}),
                         Command.create({'name': 'Contrapartida', 'account_id': credit.id, 'credit': 200})],
        })
        self.assertFalse(order._step_cost_lines())
        entry.action_post()
        self.assertEqual(order._step_cost_lines().move_line_id.account_id, debit)
        order.invalidate_recordset(['inventory_cost', 'financial_cost', 'total_cost', 'unit_cost'])
        self.assertEqual(order.total_cost, 200)
        self.assertEqual(order.unit_cost, 50)
