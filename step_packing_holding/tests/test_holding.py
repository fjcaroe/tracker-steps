from datetime import date
from lxml import etree
from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged, new_test_user, Form


@tagged('post_install', '-at_install')
class HoldingCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True,
            mail_create_nosubscribe=True, no_reset_password=True))
        cls.parent = cls.env['res.company'].create({'name': 'Private Holding root'})
        cls.branch = cls.env['res.company'].create({'name': 'Private Holding branch', 'parent_id': cls.parent.id})
        cls.sibling = cls.env['res.company'].create({'name': 'Private Holding sibling', 'parent_id': cls.parent.id})
        cls.foreign = cls.env['res.company'].create({'name': 'Private unrelated company'})
        cls.user = new_test_user(cls.env, login='private-holding-147',
            groups='stock.group_stock_manager,account.group_account_manager', company_id=cls.parent.id,
            company_ids=[Command.set((cls.parent | cls.branch | cls.sibling | cls.foreign).ids)])
        cls.scope = cls.env(user=cls.user, su=False,
            context=dict(cls.env.context, allowed_company_ids=(cls.parent | cls.branch | cls.sibling).ids))
        cls.season = cls.env['step.temporada'].create({'name': 'Private Holding season'})
        cls.species = cls.env['step.especie'].create({'name': 'Private Holding cherries', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
        group = cls.env['step.grupo.variedad'].create({'name': 'Private Holding group', 'especie_id': cls.species.id})
        cls.variety = cls.env['step.variedad'].create({'name': 'Private Holding variety', 'cod_variedad': 'PRIV147',
            'especie_id': cls.species.id, 'grupo_variedad_id': group.id})
        cls.product = cls.env['product.product'].create({'name': 'Private Holding fruit', 'grupo_labor': 'pack', 'is_storable': True, 'weight': 1})
        cls.partner = cls.env['res.partner'].create({'name': 'Private Holding producer', 'is_productor': True})

    def order(self, company=None):
        return self.scope['step.packing.order'].create({'branch_company_id': (company or self.branch).id,
            'week_start': '2026-11-02', 'week_end': '2026-11-08'})

    def shipment(self, company=None, **values):
        return self.env['step.export.export'].with_company(company or self.parent).create(dict({
            'name': 'Private Holding shipment', 'shipment_number': 'PRIVATE-%s-%s' % (self.id(), company.id if company else 0),
            'company_id': (company or self.parent).id}, **values))

    def guide(self, company=None, shipment=None):
        company = company or self.branch
        return self.scope['step.dispatch.guide'].with_company(company).create({
            'external_folio': 'PRIVATE-%s' % self.id(), 'company_id': company.id,
            'partner_id': self.partner.id, 'origin_address': 'Private origin', 'destination_address': 'Private destination',
            'carrier_id': self.partner.id, 'truck_plate': 'QA0147', 'step_export_shipment_id': shipment.id if shipment else False})

    def tag(self, kind, kilos, result=False):
        return self.env['stock.quant.package'].create({'name': 'PRIVATE-%s-%s' % (kind, self.id()),
            'is_fruit_tag': True, 'step_tag_kind': kind, 'step_packing_result': result,
            'step_producer_id': self.partner.id, 'especie_id': self.species.id, 'variedad_id': self.variety.id,
            'step_tag_line_ids': [Command.create({'producer_id': self.partner.id, 'product_id': self.product.id,
                'quantity': kilos, 'boxes': kilos, 'kilos': kilos})]})

    def test_147_branch_ownership_and_production(self):
        order = self.order()
        line = self.scope['step.packing.order.line'].create({'order_id': order.id, 'product_id': self.product.id,
            'species_id': self.species.id, 'variety_id': self.variety.id, 'boxes': 10, 'kilos': 10})
        order.action_validate()
        action = line.action_create_production()
        production = self.scope['step.packing.production'].browse(action['res_id'])
        self.assertEqual((order.company_id, production.company_id), (self.branch, self.branch))
        self.assertEqual(production.step_packing_order_id, order)
        visible = self.scope(context=dict(self.scope.context, allowed_company_ids=self.branch.ids))['step.packing.order'].search([('id', '=', order.id)])
        self.assertEqual(visible, order)
        with self.cr.savepoint(), self.assertRaises(UserError):
            order.write({'branch_company_id': self.sibling.id})

    def test_147_unrelated_or_unauthorized_branch_rejected(self):
        with self.cr.savepoint(), self.assertRaises(AccessError):
            self.order(self.foreign)
        self.user.company_ids = [Command.set(self.parent.ids)]
        with self.cr.savepoint(), self.assertRaises(AccessError):
            self.order(self.branch)

    def test_147_branch_change_before_lines(self):
        order = self.order()
        order.branch_company_id = self.sibling
        self.assertEqual(order.company_id, self.sibling)

    def test_149_guide_and_instruction_link_parent_shipment(self):
        shipment = self.shipment()
        guide = self.guide(shipment=shipment)
        self.assertEqual(guide.step_export_shipment_id, shipment)
        self.assertEqual(guide.company_id, self.branch)
        self.assertIn(guide, shipment.dispatch_guide_ids)
        instruction = self.scope['step.export.dispatch.order'].create({'name': 'Private branch instruction',
            'company_id': self.branch.id, 'shipment_id': shipment.id})
        self.assertEqual(instruction.company_id, self.branch)
        self.assertEqual(instruction.shipment_id, shipment)
        self.assertFalse(guide.picking_id)

    def test_149_selector_and_server_reject_sibling_and_foreign(self):
        guide = self.guide()
        self.assertEqual(set(guide.holding_shipment_company_ids.ids), set((self.parent | self.branch).ids))
        for company in (self.sibling, self.foreign):
            shipment = self.shipment(company)
            wide = guide.with_context(allowed_company_ids=(self.parent | self.branch | self.sibling | self.foreign).ids)
            with self.cr.savepoint(), self.assertRaises(ValidationError):
                wide.step_export_shipment_id = shipment
            with self.cr.savepoint(), self.assertRaises(ValidationError):
                self.scope['step.export.dispatch.order'].create({'name': 'Private invalid instruction',
                    'company_id': self.branch.id, 'shipment_id': shipment.id})

    def test_148_default_and_explicit_company_scope(self):
        model = self.scope['step.packing.order']
        result = model.operational_comparison('producers', {'species_id': self.species.id})
        self.assertEqual(set(result['selected_company_ids']), set((self.parent | self.branch | self.sibling).ids))
        self.assertNotIn(self.foreign.id, [c['id'] for c in result['companies']])
        for selected in ([self.parent.id], self.branch.ids, (self.branch | self.sibling).ids):
            result = model.operational_comparison('producers', {'company_ids': selected, 'species_id': self.species.id})
            self.assertEqual(result['selected_company_ids'], selected)
        with self.cr.savepoint(), self.assertRaises(AccessError):
            model.operational_comparison('producers', {'company_ids': self.foreign.ids})
        with self.cr.savepoint(), self.assertRaises(ValidationError):
            model.operational_comparison('producers', {'company_ids': []})

    def test_148_sum_estimates_from_selected_branches(self):
        for company, kilos in [(self.parent, 100), (self.branch, 200), (self.sibling, 300), (self.foreign, 9000)]:
            estimate = self.env['step.export.estimate'].with_company(company).create({'name': 'Private estimate',
                'company_id': company.id, 'season_id': self.season.id, 'producer_id': self.partner.id})
            estimate.write({'estimate_line_ids': [Command.create({'species_id': self.species.id,
                'variety_id': self.variety.id, 'product_id': self.product.id, 'delivery_kind': 'packed',
                'export_kg': kilos, 'kg_per_box': 1, 'boxes_per_package': 10,
                'week_line_ids': [Command.create({'week_start': '2026-11-02', 'export_kg': kilos})]})]})
            estimate.state = 'current'
        model = self.scope['step.packing.order']
        total = model.operational_comparison('producers', {'season_id': self.season.id})['tables'][0]['total']
        self.assertEqual(total['estimated'], 600)
        total = model.operational_comparison('producers', {'season_id': self.season.id, 'company_ids': self.branch.ids})['tables'][0]['total']
        self.assertEqual(total['estimated'], 200)
        self.assertEqual(model.producer_holding_counts(self.branch.ids)['estimates'], 1)

    def test_150_profiles_and_generic_validation(self):
        market = self.env['step.fruit.market'].create({'name': 'Private market', 'code': 'PRIV150'})
        notify = self.env['res.partner'].create({'name': 'Private notify', 'step_export_notify': True})
        consignee = self.env['res.partner'].create({'name': 'Private consignee', 'step_export_consignee': True})
        receiver = self.env['res.partner'].create({'name': 'Private receiver', 'step_export_receiver': True,
            'step_export_market_id': market.id, 'step_export_default_notify_id': notify.id,
            'step_export_default_consignee_id': consignee.id})
        generic = self.env['res.partner'].create({'name': 'Private generic', 'step_export_receiver': True,
            'step_export_generic_receiver': True, 'step_export_market_id': market.id})
        pallet = self.env['stock.package.type'].create({'name': 'Private pallet'})
        program = self.env['step.export.sales.program'].with_company(self.parent).create({
            'name': 'Private generic program', 'partner_id': generic.id, 'season_id': self.season.id,
            'species_id': self.species.id, 'product_id': self.product.id, 'package_type_id': pallet.id,
            'date_start': date(2026, 11, 2), 'date_end': date(2026, 11, 30), 'rate_to_usd': 1,
            'currency_id': self.env.ref('base.USD').id, 'boxes_per_pallet': 10, 'kg_per_box': 1,
            'pallets_per_container': 1, 'line_ids': [Command.create({'week_start': date(2026, 11, 2), 'container_qty': 1, 'price_per_kg': 1})]})
        program.action_validate(); program.action_activate()
        shipment = self.shipment(sales_program_id=program.id, receiver_id=receiver.id,
            line_ids=[Command.create({'product_id': self.product.id, 'pallet_qty': 1, 'boxes_per_pallet': 10, 'kg_per_box': 1})])
        self.assertEqual((shipment.notify_id, shipment.consignee_id), (notify, consignee))
        self.assertIn(receiver, shipment.eligible_receiver_ids)
        shipment.action_validate_shipment()
        self.assertEqual((shipment.state, shipment.receiver_id), ('validated', receiver))
        self.assertEqual(program.partner_id, generic)
        other = self.env['res.partner'].create({'name': 'Private wrong market', 'step_export_receiver': True})
        with self.cr.savepoint(), self.assertRaises(ValidationError):
            self.shipment(sales_program_id=program.id, receiver_id=other.id)

    def test_150_role_checks_and_market_required(self):
        with self.cr.savepoint(), self.assertRaises(ValidationError):
            self.env['res.partner'].create({'name': 'Private invalid generic', 'step_export_generic_receiver': True})
        for field in ('step_export_default_notify_id', 'step_export_default_consignee_id'):
            with self.cr.savepoint(), self.assertRaises(ValidationError):
                self.partner.write({field: self.partner.id})

    def test_151_positive_negative_percentages_and_standard_unchanged(self):
        incoming = self.tag('C', 100)
        export = self.tag('E', 80, 'export')
        production = self.env['step.packing.production'].create({
            'step_packing_input_tag_ids': [Command.set(incoming.ids)],
            'step_packing_output_tag_ids': [Command.set(export.ids)], 'step_packing_overweight_kg': 5})
        self.assertEqual(production.step_packing_loss_kg, 15)
        self.assertEqual((production.step_packing_export_percent, production.step_packing_overweight_percent,
                          production.step_packing_loss_percent), (80, 5, 15))
        production.step_packing_overweight_kg = -5
        self.assertEqual((production.step_packing_loss_kg, production.step_packing_overweight_percent), (25, -5))
        self.assertEqual(export.step_actual_kg, 80)
        self.assertEqual(self.product.weight, 1)
        self.assertAlmostEqual(sum(production['step_packing_%s_percent' % concept] for concept in
            ('export', 'overweight', 'commercial', 'precaliber', 'waste', 'loss')), 100)

    def test_151_zero_and_validated_lock(self):
        production = self.env['step.packing.production'].create({})
        self.assertEqual(production.step_packing_overweight_percent, 0)
        production.state = 'validated'
        with self.cr.savepoint(), self.assertRaises(UserError):
            production.step_packing_overweight_kg = 1

    def test_effective_forms_and_menu_actions(self):
        for model, field in [('step.packing.order', 'branch_company_id'), ('step.dispatch.guide', 'holding_shipment_company_ids'),
                             ('step.export.dispatch.order', 'holding_shipment_company_ids'), ('res.partner', 'step_export_market_id'),
                             ('step.export.export', 'eligible_receiver_ids'), ('step.packing.production', 'step_packing_overweight_kg')]:
            tree = etree.fromstring(self.scope[model].get_view(view_type='form')['arch'].encode())
            self.assertTrue(tree.xpath("//field[@name='%s']" % field), model)
        for xmlid in ('step_packing_operations.action_packing_order', 'step_packing_dispatch.instructions_action'):
            action = self.scope['ir.actions.act_window']._for_xml_id(xmlid)
            self.assertEqual(set(action['context']['allowed_company_ids']), set((self.parent | self.branch | self.sibling).ids))
