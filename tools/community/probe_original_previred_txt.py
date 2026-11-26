"""Exercise the real Previred supplier TXT on a private original Cerro pair."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from werkzeug.exceptions import Forbidden

from odoo.http import Response
from odoo.addons.l10n_cl_simpledigital_payroll.controllers import previred_txt

from probe_original_draft_amounts import CASES, capture_ytd, run_case
from probe_original_structure_required import require_private_pair
from probe_original_unmapped_accounting import snapshot


def read_row(endpoint, company_id):
    response = endpoint(period='112026', company_id=str(company_id))
    assert response.status_code == 200 and response.mimetype == 'text/plain'
    assert response.headers['Content-Disposition'].startswith('attachment;')
    row, = response.get_data().decode('ascii').splitlines()
    fields = row.split(';')
    assert len(fields) == 105 and fields[8:10] == ['112026', '112026']
    return fields


def run(env, database):
    require_private_pair(env, database)
    community = '_HANDOVER_' in database
    before = snapshot(env)
    assert before[2:4] == (0, 0)
    case = next(spec for spec in CASES if spec['structure'] == 2)
    marker = 'STEP_PREVIRED_' + uuid4().hex
    try:
        slip = run_case(env, case, community, {}, marker)
        other_period = run_case(env, case, community, {}, marker,
            period=(date(2026, 12, 1), date(2026, 12, 31)),
            contract=slip.contract_id)
        journal = slip.struct_id.with_company(slip.company_id).journal_id
        assert journal
        if community:
            slip.contract_id.sudo().write({'journal_id': journal.id})
        for item in (slip, other_period):
            item.with_context(without_compute_sheet=True).action_payslip_done()
            assert item.state == 'done'
        stored = capture_ytd(slip, {}), capture_ytd(other_period, {})
        counts = snapshot(env)
        request = SimpleNamespace(env=slip.env, make_response=Response)
        with patch.object(previred_txt, 'request', request):
            if community:
                from odoo.addons.step_simpledigital_oca_security import controllers

                rule, = [rule for rule in env['ir.http'].routing_map().iter_rules()
                         if rule.rule == '/hr_payroll/previred/txt']
                endpoint = rule.endpoint
                assert endpoint.routing['auth'] == 'user'
                assert endpoint.__module__ == controllers.__name__
                with patch.object(controllers, 'request', request):
                    try:
                        read_row(endpoint, 0x7fffffff)
                    except Forbidden:
                        pass
                    else:
                        raise AssertionError('An unrelated company passed the Previred guard')
                    fields = read_row(endpoint, slip.company_id.id)
            else:
                # Observe the supplier body. The native Steps wizard performs
                # additional validation and has a different output contract.
                controller = previred_txt.PreviredExportController()
                route = type(controller).download_previred_txt
                fields = read_row(lambda **kw: route.original_endpoint(controller, **kw),
                                  slip.company_id.id)
        env.invalidate_all()
        assert snapshot(env) == counts
        assert (capture_ytd(slip, {}), capture_ytd(other_period, {})) == stored
        assert slip.state == other_period.state == 'done'
        result = {
            'operator_uid': slip.env.uid,
            'structure_id': slip.struct_id.id,
            'rows': 1,
            'columns': len(fields),
            'supplier_days': int(fields[12]),
            'afp_configured_on_contract': bool(slip.contract_id.afp_option),
            'health_institution_populated': bool(fields[74]),
            'other_period_excluded': True,
            'foreign_company_denied': community,
            'preserved_stored_totals': True,
        }
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {**result, 'fixture_rolled_back': True}
