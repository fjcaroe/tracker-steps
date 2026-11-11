from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class DispatchTypeCompaniesCase(TransactionCase):
    def test_native_dispatch_type_can_be_used_by_selected_companies(self):
        company = self.env.company
        other = self.env['res.company'].create({'name': 'QA T204 sucursal'})
        other.dispatch_dte_provider = 'third_party'
        contact = self.env['res.partner'].create({'name': 'QA T204 cliente', 'step_carga': True})
        dispatch_type = self.env['step.freight.dispatch.type'].create({'name': 'QA T204 tipo compartido'})
        vals = {'company_id': other.id, 'dispatch_type_id': dispatch_type.id, 'external_folio': '204099',
                'partner_id': contact.id, 'carrier_id': contact.id, 'origin_address': 'Origen QA',
                'destination_address': 'Destino QA', 'truck_plate': 'ABCD12'}
        Guide = self.env['step.dispatch.guide'].with_company(other)
        with self.assertRaisesRegex(ValidationError, 'habilitado'), self.cr.savepoint():
            Guide.create(vals)
        dispatch_type.company_ids = [Command.set((company | other).ids)]
        self.assertEqual(Guide.create(vals).dispatch_type_id, dispatch_type)
        with self.assertRaisesRegex(ValidationError, 'Conserve'), self.cr.savepoint():
            dispatch_type.company_ids = [Command.set(company.ids)]
