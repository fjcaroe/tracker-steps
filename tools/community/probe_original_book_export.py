"""Read the real Simple Digital Libro export on the private original Cerro pair."""
import csv
from datetime import date
import hashlib
import io
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from werkzeug.exceptions import Forbidden
from odoo.http import Response

from odoo.addons.l10n_cl_simpledigital_payroll.controllers import libro_remuneraciones as provider

from probe_original_draft_amounts import CASES, capture_ytd, run_case
from probe_original_structure_required import require_private_pair
from probe_original_unmapped_accounting import snapshot


def read_csv(endpoint, company_id, include_header):
    response = endpoint(
        date_from='2026-11-01', date_to='2026-11-30', include_header=str(include_header), company_id=company_id)
    assert response.mimetype == 'text/csv', 'The real provider did not return a CSV attachment'
    assert 'charset=windows-1252' in response.headers['Content-Type']
    assert response.headers['Content-Disposition'].startswith('attachment;')
    body = response.get_data()
    assert int(response.headers['Content-Length']) == len(body)
    return list(csv.reader(io.StringIO(body.decode('cp1252')), delimiter=';'))


def run(env, database):
    require_private_pair(env, database)
    community = '_HANDOVER_' in database
    before = snapshot(env)
    assert before[2:4] == (0, 0)
    case = next(spec for spec in CASES if spec['structure'] == 2)
    marker = 'STEP_BOOK_' + uuid4().hex
    try:
        closed = run_case(env, case, community, {}, marker)
        draft = run_case(env, case, community, {}, marker,
            period=(date(2026, 11, 9), date(2026, 11, 13)),
            contract=closed.contract_id, entry_hours=(8, 0))
        journal = closed.struct_id.with_company(closed.company_id).journal_id
        assert journal
        if community:
            closed.contract_id.sudo().write({'journal_id': journal.id})
        closed.with_context(without_compute_sheet=True).action_payslip_done()
        assert closed.state == 'done' and draft.state in ('draft', 'verify')
        totals = capture_ytd(closed, {})
        assert next(float(value) for _, code, value in totals if code == 'BASIC') == 360000
        assert next(float(value) for _, code, value in capture_ytd(draft, {}) if code == 'BASIC') == 720000
        contract_counts = snapshot(env)
        route, = [rule for rule in env['ir.http'].routing_map().iter_rules()
                  if rule.endpoint.__name__ == 'export_libro_remuneraciones_csv']
        endpoint = route.endpoint
        assert endpoint.routing['type'] == 'http' and endpoint.routing['auth'] == 'user'
        request = SimpleNamespace(env=closed.env, make_response=Response)
        with patch.object(provider, 'request', request):
            if community:
                from odoo.addons.step_simpledigital_oca_security import controllers
                with patch.object(controllers, 'request', request):
                    assert endpoint.__module__ == controllers.__name__
                    rows = read_csv(endpoint, closed.company_id.id, True)
                    assert read_csv(endpoint, closed.company_id.id, False) == rows[1:]
                    try:
                        read_csv(endpoint, 0x7fffffff, True)
                    except Forbidden:
                        pass
                    else:
                        raise AssertionError('A foreign company bypassed the export guard')
            else:
                assert endpoint.__module__ == provider.__name__
                rows = read_csv(endpoint, closed.company_id.id, True)
                assert read_csv(endpoint, closed.company_id.id, False) == rows[1:]
        header, row = rows
        assert len(header) == len(row) and len(header) >= 140
        wage_column, = [index for index, name in enumerate(header) if name.endswith('(2101)')]
        assert int(row[wage_column]) == 360000
        env.invalidate_all()
        assert snapshot(env) == contract_counts
        assert capture_ytd(closed, {}) == totals and closed.state == 'done'
        result = {
            'uid': closed.env.uid,
            'structure_id': closed.struct_id.id,
            'rows': 1,
            'columns': len(header),
            'header_sha256': hashlib.sha256('\n'.join(header).encode()).hexdigest(),
            'basic_2101_clp': int(row[wage_column]),
            'draft_excluded': True,
            'preserved_stored_totals': True,
            'foreign_company_denied': community,
        }
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {**result, 'fixture_rolled_back': True}

