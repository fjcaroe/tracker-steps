from odoo.tests import Form, TransactionCase, tagged
from odoo.exceptions import UserError


def exercise_split(env, operator):
    company = operator.company
    setup = env['stock.picking'].with_company(company).env
    warehouse = setup['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    producer = setup['res.partner'].create({'name': 'QA154 productor', 'is_productor': True})
    species = setup['step.especie'].create({'name': 'QA154 especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
    group = setup['step.grupo.variedad'].create({'name': 'QA154 grupo', 'especie_id': species.id})
    variety = setup['step.variedad'].create({'name': 'QA154 variedad', 'cod_variedad': 'QA154',
                                            'especie_id': species.id, 'grupo_variedad_id': group.id})
    kg = setup.ref('uom.product_uom_kgm')
    product = setup['product.product'].create({'name': 'QA154 fruta', 'is_storable': True,
                                               'uom_id': kg.id, 'uom_po_id': kg.id, 'tracking': 'lot'})
    lot = setup['stock.lot'].create({'name': 'QA154 lote', 'product_id': product.id, 'company_id': company.id})
    source = setup['stock.quant.package'].create({
        'name': f'QA154-{lot.id}', 'is_fruit_tag': True, 'step_tag_kind': 'C',
        'step_producer_id': producer.id, 'especie_id': species.id, 'variedad_id': variety.id,
        'fruit_type': 'conventional', 'box_count': 152,
        'step_tag_line_ids': [(0, 0, {'producer_id': producer.id, 'product_id': product.id,
            'lot_id': lot.id, 'quantity': 339.84, 'boxes': 152, 'kilos': 339.84})],
    })
    setup['stock.quant']._update_available_quantity(
        product, warehouse.lot_stock_id, 339.84, lot_id=lot, package_id=source, owner_id=producer)
    source.action_step_validate_tag()
    ot = setup['step.packing.production'].create({
        'company_id': company.id, 'raw_product_id': product.id, 'fruit_grower_id': producer.id,
        'fruit_variety_id': variety.id, 'step_packing_input_tag_ids': [(6, 0, source.ids)],
    }).with_env(operator)
    action = ot.action_split_input_tag()
    form = Form(operator[action['res_model']].with_context(**action['context']))
    form.source_id = source.with_env(operator)
    form.process_boxes = 100
    form.process_kg = 223.58
    wizard = form.save()
    wizard.action_split()
    process = ot.step_packing_input_tag_ids
    balance = operator['stock.quant.package'].search([('name', '=', source.name + '-2')])
    assert process.name == source.name + '-1'
    assert source.step_tag_state == 'repalletized' and not sum(source.quant_ids.mapped('quantity'))
    assert len(balance) == 1 and balance not in ot.step_packing_input_tag_ids
    for tag, boxes, weight in ((process, 100, 223.58), (balance, 52, 116.26)):
        assert tag.step_tag_state == 'validated'
        assert tag.step_actual_boxes == boxes and round(tag.step_actual_kg, 2) == weight
        assert tag.variedad_id.id == variety.id
        assert tag.step_tag_line_ids.source_package_id.id == source.id
        assert tag.quant_ids.owner_id.id == producer.id and tag.quant_ids.lot_id.id == lot.id
        assert round(sum(tag.quant_ids.mapped('quantity')), 2) == weight
    assert round(ot.step_packing_input_kg, 2) == 223.58
    return wizard


@tagged('post_install', '-at_install')
class TestSplit(TransactionCase):
    def test_partial_split_preserves_stock_and_rejects_retry(self):
        wizard = exercise_split(self.env, self.env)
        with self.assertRaises(UserError):
            wizard.action_split()

