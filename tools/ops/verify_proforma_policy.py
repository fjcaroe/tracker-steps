"""Verify the updated draft UI and the reported 33-to-46 case without live DML."""
import json
from pathlib import Path
from lxml import etree
from odoo.modules.module import get_module_path
from native_business_profile import scoped_business_environment
from fruit_proforma_checks import verify_ui, verify_copy_cycle

try:
    for name, version in EXPECTED.items():
        installed = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
        assert installed.latest_version == version
        assert Path(get_module_path(name)).resolve() == Path(ROOT)/name
    business = scoped_business_environment(env)
    verify_ui(business)
    view = business.ref('step_packing_fruit_proforma.fruit_proforma_form')
    arch = etree.fromstring(business['purchase.order'].get_view(view_id=view.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_fruit_refresh_taxes' and @invisible=\"step_fruit_state != 'draft'\"]")
    assert arch.xpath("//field[@name='step_fruit_previous_references' and @readonly='1']")
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        verify_copy_cycle(env, OUTPUT)
        if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
            from proforma_policy_case import refresh
            assert PROFORMA_POLICY_PLAN
            result = refresh(env, PROFORMA_POLICY_PLAN)
            actual = scoped_business_environment(env,
                company=env['res.company'].browse(PROFORMA_POLICY_PLAN['before']['company_id']))
            pdf, kind = actual['ir.actions.report']._render_qweb_pdf(
                'step_packing_fruit_proforma.report_fruit_proforma', [result['id']])
            assert kind == 'pdf' and pdf.startswith(b'%PDF')
            (Path(OUTPUT)/'t171-review-proforma.pdf').write_bytes(pdf)
            print('T171_POLICY_CASE_OK ' + json.dumps(result))
    elif PROFORMA_POLICY_PLAN:
        actual = scoped_business_environment(env,
            company=env['res.company'].browse(PROFORMA_POLICY_PLAN['before']['company_id']))
        order = actual['purchase.order'].browse(PROFORMA_POLICY_PLAN['before']['id'])
        assert order.step_fruit_dte_code == PROFORMA_POLICY_PLAN['target']['dte']
        assert order.step_fruit_withholding_tax_id.id == PROFORMA_POLICY_PLAN['target']['retention_id']
        assert order.step_fruit_state == 'draft' and not order.invoice_ids
        assert PROFORMA_POLICY_PLAN['before']['name'] in order.step_fruit_previous_references.splitlines()
        for actual, expected in zip((order.amount_untaxed, order.amount_tax, order.amount_total),
                                    PROFORMA_POLICY_PLAN['target']['totals']):
            assert order.currency_id.compare_amounts(actual, expected) == 0
    print('MANAGEMENT_REGISTRY_OK draft proforma tax update and native menus/forms')
finally:
    env.cr.rollback()
