"""Verify the monthly accounting book menus, workbook and company/date scope."""
import base64
import importlib
import json
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from odoo import fields


MODULE = 'step_account_monthly_books'
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
KEYS = ('sales', 'purchases', 'fees')

try:
    installed = env['ir.module.module'].search([('name', '=', MODULE), ('state', '=', 'installed')])
    assert installed.latest_version == EXPECTED[MODULE]
    assert Path(importlib.import_module('odoo.addons.' + MODULE).__file__).resolve().parent == Path(ROOT) / MODULE
    users = env['res.users'].search([('share', '=', False), ('id', '!=', 1)])
    accountants = users.filtered(lambda user: user.has_group('account.group_account_invoice')
                                 or user.has_group('account.group_account_readonly'))
    assert accountants
    results = {}
    for key in KEYS:
        sample_domain = [
            ('state', '=', 'posted'),
            ('move_type', 'in', ('out_invoice', 'out_refund') if key == 'sales' else ('in_invoice', 'in_refund')),
            ('l10n_latam_document_type_id.country_id', '=', env.ref('base.cl').id),
            ('l10n_latam_document_type_id.internal_type', 'in', ('invoice', 'invoice_in', 'credit_note', 'debit_note')),
            ('l10n_latam_document_type_id.code', 'in' if key == 'fees' else 'not in', ('70', '71')),
            ('company_id', 'in', accountants.company_ids.ids),
        ]
        sample = env['account.move'].search(sample_domain, order='invoice_date desc, id desc', limit=1)
        company = sample.company_id or accountants[0].company_id
        eligible = accountants.filtered(lambda user: company in user.company_ids)
        user = (eligible.filtered(lambda user: user.company_id == company) or eligible)[0]
        scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
        menu = scoped.ref(f'{MODULE}.menu_{key}')
        expected_parent = 'receivables' if key == 'sales' else 'payables'
        assert menu.parent_id.parent_id == scoped.ref(f'account.menu_finance_{expected_parent}')
        assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
        action = menu.action
        assert action.target == 'new' and action.context == "{'default_book': '%s'}" % key
        wizard_model = scoped[action.res_model]
        arch = ElementTree.fromstring(wizard_model.get_view(view_id=action.view_id.id, view_type='form')['arch'])
        assert {item.get('name') for item in arch.findall('.//field')} == {'month', 'year', 'book'}
        assert arch.find(".//button[@name='action_download']") is not None
        day = sample.invoice_date or fields.Date.today()
        wizard_values = {'month': str(day.month), 'year': day.year, 'book': key}
        wizard = wizard_model.new(wizard_values)
        moves = wizard._moves()
        if sample and sample.with_env(scoped).has_access('read'):
            assert sample.id in moves.ids
        assert all(move.company_id == company and move.invoice_date.month == day.month
                   and move.invoice_date.year == day.year and move.state == 'posted' for move in moves)
        if env.cr.dbname.startswith('MANAGEMENT_QA_'):
            wizard = wizard_model.create(wizard_values)
            download = wizard.action_download()
            assert download['target'] == 'download' and f'/{wizard.id}/file_data/' in download['url']
            workbook = base64.b64decode(wizard.file_data)
        else:
            workbook = wizard._xlsx()
        with ZipFile(BytesIO(workbook)) as xlsx:
            strings = [''.join(element.itertext()) for element in ElementTree.fromstring(xlsx.read('xl/sharedStrings.xml'))]
            sheet = ElementTree.fromstring(xlsx.read('xl/worksheets/sheet1.xml'))
            def cell(address):
                return sheet.find(".//m:c[@r='%s']/m:v" % address, NS)
            assert strings[int(cell('A5').text)] == 'Correlativo'
            assert strings[int(cell('A2').text)] == 'RUT'
            if moves:
                last = 5 + len(moves)
                assert int(cell(f'A{last}').text) == len(moves)
                assert len(sheet.findall('.//m:f', NS)) == {'sales': 6, 'purchases': 8, 'fees': 4}[key]
        results[key] = len(moves)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 217, 'version': installed.latest_version,
          'menus': True, 'wizard': True, 'excel': True, 'posted_documents_by_book': results}))
finally:
    env.cr.rollback()
