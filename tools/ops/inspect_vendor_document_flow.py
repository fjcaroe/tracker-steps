"""Read-only native Chilean supplier-document diagnosis (execute in Odoo shell).

Optionally supply VENDOR_ID to examine the reported supplier. No partner data,
invoice or configuration is saved, and the transaction always rolls back.
"""
import hashlib
import inspect
import json

from odoo.tools import config
from native_business_profile import scoped_business_environment


try:
    scoped = scoped_business_environment(env)
    previous = config['test_enable']
    config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    menu = scoped.ref('account.menu_action_move_in_invoice_type')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    action = menu.action
    assert action.res_model == 'account.move', (action._name, action.id)
    journals = scoped['account.journal'].search([('type', '=', 'purchase')])
    journal = journals.filtered('l10n_latam_use_documents')[:1]
    assert journal and scoped.company.account_fiscal_country_id.code == 'CL'
    partners = scoped['res.partner']
    vendor_id = globals().get('VENDOR_ID')
    vendor = partners.browse(vendor_id).exists() if vendor_id else partners.search([
        ('supplier_rank', '>', 0), ('country_id.code', '=', 'CL'),
        ('l10n_cl_sii_taxpayer_type', '=', '1'), ('vat', '!=', False)], limit=1)
    assert vendor, 'Specify an existing supplier with VENDOR_ID'
    moves = scoped['account.move'].with_context(default_move_type='in_invoice',
                                               default_journal_id=journal.id)
    form = Form(moves, view='account.view_move_form')
    empty_codes = [document.code for document in form.l10n_latam_available_document_type_ids]
    assert not empty_codes
    form.partner_id = vendor
    codes = [document.code for document in form.l10n_latam_available_document_type_ids]
    selected = form.l10n_latam_document_type_id.code
    assert selected in codes if codes else not selected
    if vendor.l10n_cl_sii_taxpayer_type == '1':
        assert '33' in codes, 'Registered Chilean supplier must allow electronic invoices'
    domestic = partners.search([('supplier_rank', '>', 0), ('country_id.code', '=', 'CL')])
    missing = domestic.filtered(lambda p: not p.l10n_cl_sii_taxpayer_type or not p.vat)
    sources = {}
    for cls in type(moves).__mro__:
        for method in ('_get_l10n_latam_documents_domain', '_compute_l10n_latam_available_document_types'):
            fn = cls.__dict__.get(method)
            if fn:
                path = inspect.getsourcefile(fn)
                sources[cls.__module__ + '.' + method] = {
                    'path': path,
                    'sha256': hashlib.sha256(inspect.getsource(fn).encode()).hexdigest(),
                }
    print('VENDOR_DOCUMENT_DIAGNOSIS ' + json.dumps({
        'database': scoped.cr.dbname, 'user_id': scoped.uid, 'company_id': scoped.company.id,
        'native_menu_and_form': True, 'journal_id': journal.id,
        'documents_enabled': journal.l10n_latam_use_documents,
        'empty_supplier_codes': empty_codes, 'supplier_id': vendor.id,
        'supplier_taxpayer_type': vendor.l10n_cl_sii_taxpayer_type,
        'supplier_country': vendor.country_id.code, 'supplier_has_vat': bool(vendor.vat),
        'available_codes': codes, 'selected_code': selected,
        'domestic_suppliers_missing_taxpayer_type_or_vat': len(missing),
        'versions': {name: scoped['ir.module.module'].search([('name', '=', name)]).latest_version
                     for name in ('account', 'l10n_cl', 'l10n_latam_invoice_document')},
        'sources': sources, 'saved': False,
    }))
finally:
    env.cr.rollback()
