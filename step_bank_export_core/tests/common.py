"""Transactional, company-specific numbering for real payment fixtures only."""

PAYMENT_CODES = ('account.payment',)
BATCH_CODES = PAYMENT_CODES + ('account.outbound.batch.payment', 'account.inbound.batch.payment')


def private_finance_sequences(env, company, codes=PAYMENT_CODES):
    """Never consume or reset a preexisting business/document counter.

    next_by_code selects the current company before the global fallback. Check
    that same lookup without drawing a number. no_gap stores its next value in
    the new ir.sequence row, so ordinary fixture rollback also rolls it back.
    """
    company.ensure_one()
    sequences = env['ir.sequence'].sudo().with_company(company)
    for code in codes:
        existing = sequences.search([('code', '=', code), ('company_id', '=', company.id)])
        if existing:
            raise AssertionError('Use an isolated fixture company: existing sequence for %s, company %s' % (code, company.id))
        private = sequences.create({
            'name': 'Private finance fixture %s / %s' % (code, company.id),
            'code': code, 'company_id': company.id, 'implementation': 'no_gap',
            'use_date_range': False, 'prefix': 'QA/%s/%s/' % (company.id, code.replace('.', '_')),
            'padding': 6, 'number_next': 1,
        })
        selected = sequences.search([('code', '=', code), ('company_id', 'in', [company.id, False])],
                                    order='company_id', limit=1)
        if selected != private:
            raise AssertionError('Fixture sequence lookup selected an original counter: %s' % code)
