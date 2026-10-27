from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExportNavigation(TransactionCase):
    def test_client_menu_contract_and_instruction_form(self):
        root = self.env.ref('step_export.menu_step_export_root')
        menus = self.env['ir.ui.menu'].with_context(lang='es_CL').search(
            [('parent_id', '=', root.id)], order='sequence,id')
        # Optional apps add their own roots (for example Control). Keep the
        # base navigation contract without rejecting those installed consumers.
        owned_ids=self.env['ir.model.data'].search([('module','=','step_export'),
            ('model','=','ir.ui.menu'),('res_id','in',menus.ids)]).mapped('res_id')
        self.assertEqual(menus.filtered(lambda menu:menu.id in owned_ids).mapped('name'), [
            'Inicio', 'Planificación', 'Embarque', 'Recibidor',
            'Gastos exportación', 'Maestros', 'Configuraciones'])
        instruction = self.env.ref('step_export.action_export_shipping_instructions')
        self.assertEqual(instruction.res_model, 'step.export.export')
        # The saved customer hierarchy puts sales notes before instructions.
        # Preserve that order and verify the actual parent/action contract.
        menu=self.env.ref('step_export.menu_step_export_shipping_instruction')
        self.assertEqual(menu.parent_id,self.env.ref('step_export.menu_step_export_shipments'))
        self.assertEqual(menu.action,instruction)
        arch = self.env[instruction.res_model].get_view(view_type='form')['arch']
        self.assertIn('action_validate_shipment', arch)
        self.assertIn('name="line_ids"', arch)
        legacy = self.env.ref('step_export.menu_step_export_legacy_instructions')
        self.assertIn(self.env.ref('base.group_no_one'), legacy.groups_id)
        for menu in self.env['ir.ui.menu'].search([('id', 'child_of', root.id)]):
            if '(etiqueta)' in menu.name or '(etapa)' in menu.name:
                self.assertIn(self.env.ref('base.group_no_one'), menu.groups_id)

    def test_instruction_program_copies_real_master_relations(self):
        receiver = self.env['res.partner'].create({'name': 'Navigation receiver', 'step_export_receiver': True})
        season = self.env['step.temporada'].create({'name': 'Navigation season'})
        species = self.env['step.especie'].create({'name': 'Navigation species', 'type_especie': 'frutal', 'group_especie': 'seco'})
        # new() exercises the same onchange as the shipment form without creating business records.
        program = self.env['step.export.sales.program'].new({
            'partner_id': receiver.id, 'season_id': season.id, 'species_id': species.id})
        instruction = self.env['step.export.export'].new({'sales_program_id': program})
        instruction._onchange_sales_program_instruction()
        self.assertEqual(instruction.receiver_id, receiver)
        self.assertEqual(instruction.season_id, season)
        self.assertEqual(instruction.species_id, species)
