"""Exercise an existing client contract in an isolated clone; always roll back.

The caller supplies CONTRACT_ID, ADVANCE_PRODUCT_ID and ADVANCE_ACCOUNT_ID.
No client identifiers or configuration are stored in the public repository.
"""
import json

try:
    assert env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_'), 'Clone only'
    contract = env['step.producer.purchase.contract'].browse(CONTRACT_ID).exists()
    assert contract and contract.state == 'confirmed' and not contract.accounting_move_id
    company = contract.company_id
    product = env['product.product'].browse(ADVANCE_PRODUCT_ID).exists()
    account = env['account.account'].browse(ADVANCE_ACCOUNT_ID).exists()
    assert product and account and account.account_type == 'asset_current'
    company.write({'step_producer_advance_product_id': product.id,
                   'step_producer_advance_account_id': account.id})
    contract.action_account()
    move = contract.accounting_move_id
    installments = contract.installment_ids.filtered('active')
    assert move.state == 'posted'
    assert set(move.line_ids.mapped('account_id').ids) == set((account | contract.provision_account_id).ids)
    assert move.company_id == company and move.currency_id == contract.currency_id
    assert company.currency_id.is_zero(sum(move.line_ids.mapped('balance')))
    assert contract.currency_id.is_zero(sum(move.line_ids.mapped('amount_currency')))
    for installment in installments:
        entry = installment.provision_line_id
        assert entry.date_maturity == installment.date_due
        assert entry.step_producer_installment_id == installment
        assert contract.currency_id.is_zero(-entry.amount_currency - installment.amount)
    flow = env['step.cashflow'].with_company(company).create({'start_date': contract.accounting_date})
    flow.action_refresh()
    rows = flow.line_ids.filtered(lambda line: line.source_model == contract._name and line.source_id == contract.id)
    assert len(rows) == len(installments)
    assert contract.currency_id.is_zero(sum(rows.mapped('amount_origin')) - contract.scheduled_total)
    assert set(rows.mapped('due_date')) == set(installments.mapped('date_due'))
    print('PRODUCER_EXISTING_CONTRACT_FLOW_OK ' + json.dumps({
        'installments': len(installments), 'ledger_lines': len(move.line_ids),
        'cashflow_lines': len(rows), 'currency': contract.currency_id.name,
    }))
finally:
    env.cr.rollback()
