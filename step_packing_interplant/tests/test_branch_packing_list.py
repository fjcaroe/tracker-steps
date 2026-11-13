from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class BranchPackingListCase(TransactionCase):
    def test_matrix_packing_list_from_only_active_branch(self):
        matrix = self.env.company
        branch = self.env['res.company'].create({'name': 'QA213 branch', 'parent_id': matrix.id})
        other = self.env['res.company'].create({'name': 'QA213 other', 'parent_id': matrix.id})
        operator = new_test_user(self.env, login='qa213-branch', groups='stock.group_stock_user',
            company_id=branch.id, company_ids=[Command.set((branch | matrix).ids)])
        scoped = self.env(user=operator, su=False, context=dict(self.env.context, allowed_company_ids=branch.ids))
        parent_scope = self.env(user=operator, su=False,
            context=dict(self.env.context, allowed_company_ids=[matrix.id, branch.id]))
        partner = self.env['res.partner'].create({'name': 'QA213 export contact', 'step_export': True})
        kind = self.env['step.freight.dispatch.type'].with_company(branch).create({
            'name': 'QA213 shipment', 'company_ids': [Command.set((branch | other).ids)],
            'step_recipient_kind': 'shipment',
        })
        shipment = self.env['step.export.export'].create({
            'name': 'QA213 shipment', 'shipment_number': 'QA213', 'state': 'validated',
        })
        guide_model = self.env['step.dispatch.guide']
        values = {'dispatch_type_id': kind.id, 'partner_id': partner.id, 'carrier_id': partner.id,
                  'origin_address': 'QA source', 'destination_address': 'QA port', 'truck_plate': 'QA2130'}
        guide = guide_model.with_company(branch).create(dict(values, external_folio='QA213-6666'))
        draft = guide_model.with_company(branch).create(dict(values, external_folio='QA213-DRAFT'))
        foreign = guide_model.with_company(other).create(dict(values, external_folio='QA213-OTHER'))
        shipment.with_context(allowed_company_ids=[matrix.id, branch.id, other.id]).write({
            'dispatch_guide_ids': [Command.set((guide | draft | foreign).ids)]})
        tag = self.env['stock.quant.package'].with_company(branch).create({
            'name': 'QA213 tag', 'is_fruit_tag': True, 'step_tag_kind': 'E', 'company_id': branch.id,
        })
        # Establish the same post-dispatch state as an existing confirmed guide.
        # T212's native confirmation with stock is exercised by its own suite.
        self.cr.execute('INSERT INTO step_dispatch_guide_load_tag_rel VALUES (%s, %s)', (guide.id, tag.id))
        self.cr.execute("UPDATE step_dispatch_guide SET state='confirmed' WHERE id IN %s", [tuple((guide | foreign).ids)])
        guide_model.invalidate_model(['state', 'load_tag_ids'])
        model = scoped['step.export.packing.list']
        probe = model.new({'shipment_id': shipment.id})
        self.assertEqual(probe.available_guide_ids.ids, guide.ids)
        self.assertEqual(scoped[guide._name].name_search('6666', args=[('id', 'in', guide.ids)])[0][0], guide.id)
        with Form(model) as form:
            form.shipment_id = shipment.with_env(parent_scope)
            form.guide_id = guide.with_env(scoped)
            self.assertEqual(len(form.tag_ids), 1)
        packing = form.record
        self.assertEqual(packing.sudo().company_id, matrix)
        self.assertEqual(packing.sudo().tag_ids, tag)
        self.assertTrue(packing.sudo().name.startswith('PL/'))
        self.assertIn(packing.with_env(parent_scope), shipment.with_env(parent_scope).packing_list_ids)
        self.assertFalse(shipment.tag_ids)
        with self.assertRaises(AccessError), self.cr.savepoint():
            model.create({'shipment_id': shipment.id, 'guide_id': foreign.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            model.create({'shipment_id': shipment.id, 'guide_id': draft.id})
        self.assertEqual(scoped.companies, branch)
