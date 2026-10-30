"""Replay a private reported quadrature in a fresh clone, always rolled back."""
import json
from pathlib import Path
from odoo.exceptions import UserError


def verify_reported_quadrature(root, scoped, tools):
    if not root.cr.dbname.startswith('MANAGEMENT_QA_QA-CERRO_'):
        return
    plan_path=Path(tools).parents[1]/'packing-replay.json'
    if not plan_path.exists():
        return
    plan=json.loads(plan_path.read_text())
    record=scoped['step.packing.production'].browse(plan['production_id']).exists()
    if not record or record.company_id != scoped.company:
        return
    assert record.name==plan['expected_name'] and record.state=='created'
    assert len(record.step_packing_output_tag_ids)==plan['output_count']
    assert all(tag.step_tag_state=='validated' and tag.step_packing_production_id==record
               for tag in record.step_packing_output_tag_ids)
    record._check_packing_tags()
    products=(record.step_packing_input_tag_ids|record.step_packing_output_tag_ids).step_tag_line_ids.product_id
    unsupported=products.filtered(lambda product:not product.is_storable)
    if unsupported:
        try:
            record.action_step_packing_validate()
        except UserError as exc:
            assert 'controlar inventario' in str(exc)
        else:
            raise AssertionError('Non-inventory fruit passed native stock guard')
        assert record.state=='created' and not record.step_packing_transfer_id
        print('T137_REPORTED_QUADRATURE_OK pending_product_inventory=True rollback_required=True')
    else:
        record.action_step_packing_validate()
        assert record.state=='validated'
        print('T137_REPORTED_QUADRATURE_OK pending_product_inventory=False rollback_required=True')
