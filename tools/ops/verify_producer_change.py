"""Verify the installed native repacking flow with a rolled-back transaction."""
import importlib,json
from pathlib import Path
from odoo.addons.step_packing_producer_change.tests.test_producer_change import ProducerChangeCase
try:
    for name,version in EXPECTED.items():
        module=env['ir.module.module'].search([('name','=',name)])
        assert module.state=='installed' and module.latest_version==version
        assert Path(importlib.import_module('odoo.addons.'+name).__file__).resolve().parent==Path(ROOT)/name
    env=env(context=dict(env.context,tracking_disable=True,no_reset_password=True,mail_create_nosubscribe=True))
    case=ProducerChangeCase('test_change_stock_traceability_and_print')
    case.env=env
    case.cr=env.cr
    for name in ('test_change_stock_traceability_and_print','test_normal_repack_inherits_and_rejects_new_change','test_company_scope_and_effective_form'):
        getattr(case,name)()
    from odoo.addons.step_packing_producer_change.tests.test_receipt_producer import ReceiptProducerCase
    receipt_case = ReceiptProducerCase('test_received_producer_stock_history_and_repeat')
    receipt_case.env, receipt_case.cr = env, env.cr
    receipt_case.wh = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
    env.company.step_fruit_inventory_enabled = True
    receipt_case.producer = env['res.partner'].create({'name': 'QA246 productor', 'is_productor': True})
    receipt_case.fundo = env['step.fundo'].create({'name': 'QA246 fundo', 'partner_id': receipt_case.producer.id,
                                                'company_id': env.company.id})
    receipt_case.species = env['step.especie'].create({'name': 'QA246 especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
    kg = env.ref('uom.product_uom_kgm')
    receipt_case.product = env['product.product'].create({'name': 'QA246 fruta kg', 'is_storable': True,
        'uom_id': kg.id, 'uom_po_id': kg.id})
    receipt_case.packaging = env['product.packaging'].create({'name': 'QA246 caja', 'product_id': receipt_case.product.id, 'qty': 8})
    for name in ('test_received_producer_stock_history_and_repeat', 'test_reservations_remain_on_same_stock',
                 'test_internal_transfer_is_still_inventory', 'test_processed_dispatched_partial_and_missing_stock_rejected',
                 'test_stale_and_direct_changes_rejected', 'test_foreign_producer_and_read_only_user_rejected',
                 'test_forms_both_entry_points', 'test_inventory_manager_can_apply_without_sudo'):
        with env.cr.savepoint():
            getattr(receipt_case, name)()
    if '/steps-validation/' in ROOT:
        # The private test HTTP service has stopped before this rollback probe.
        # Serve static report assets/barcodes from the existing local destination.
        env['ir.config_parameter'].sudo().set_param('report.url', 'https://desarrollo.stepsapp.cl' if '/management_development_' in ROOT else 'https://cerroelplomo.stepsapp.cl')
        pdf,_=env['ir.actions.report']._render_qweb_pdf('step_inventory_fruit_tag.action_report_fruit_tag',case.target.ids)
        assert pdf.startswith(b'%PDF')
        (Path(ROOT).parent/'t87-tarja.pdf').write_bytes(pdf)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'ticket_id':246,'versions':EXPECTED,'forms':True,'menus':True,'stock':True,'traceability':True,'printed_producer':True,'company_security':True,'receipt_and_c_tag':True,'reservations':True,'internal_transfers':True,'original_moves_preserved':True}))
finally:
    env.cr.rollback()
