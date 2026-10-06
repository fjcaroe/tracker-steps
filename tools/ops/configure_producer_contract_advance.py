"""Configure explicitly approved existing masters inside an Odoo shell.

Call configure_advance(company_id, product_id, account_id, account_code,
journal_id, provision_account_id). The caller owns commit/rollback and must
validate in the target clone before applying to Desarrollo. No accounts,
products, journal types or user permissions are created or replaced.
"""
def configure_advance(company_id, product_id, account_id, account_code,
                      journal_id, provision_account_id, reclassify_empty_contract_journal=False):
    assert env.cr.dbname == 'LAB_TAREAS' or env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_')
    company = env['res.company'].browse(company_id).exists()
    product = env['product.product'].browse(product_id).exists()
    account = env['account.account'].with_company(company).browse(account_id).exists()
    journal = env['account.journal'].browse(journal_id).exists()
    provision = env['account.account'].browse(provision_account_id).exists()
    assert company and product and account and journal and provision
    assert product.active and product.type == 'service'
    assert not product.company_id or product.company_id == company
    assert account.code == account_code and company in account.company_ids
    assert account.account_type == 'asset_current' and not account.deprecated
    assert company in provision.company_ids and not provision.deprecated
    assert provision.account_type.startswith('liability_')
    assert journal.company_id == company and journal.type in ('general', 'purchase')
    if reclassify_empty_contract_journal:
        # A never-used contract journal can become a general journal without
        # replacing the master or changing any fiscal/posted documents.
        assert not env['account.move'].search_count([('journal_id', '=', journal.id)])
        for name, field in company._fields.items():
            if field.type == 'many2one' and field.comodel_name == 'account.journal':
                assert company[name] != journal, 'Journal already used by company setting: ' + name
        journal.write({'type': 'general', 'l10n_latam_use_documents': False})
    assert not journal.l10n_latam_use_documents, 'Provisions must use a journal without fiscal documents'
    assert company.step_producer_advance_account_id in (account, env['account.account'])
    assert company.step_producer_advance_product_id in (product, env['product.product'])
    # Extend a nonempty whitelist only with the client-approved advance account.
    if journal.account_control_ids:
        assert provision in journal.account_control_ids
        if account not in journal.account_control_ids:
            journal.write({'account_control_ids': [(4, account.id)]})
    company.write({'step_producer_advance_product_id': product.id,
                   'step_producer_advance_account_id': account.id})
    company._check_contract_advance_company()
    return company
