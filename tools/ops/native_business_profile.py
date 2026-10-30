"""Select an existing business editor in the canonical destination company.

Never widen permissions or infer the business company from the technical admin.
The Cerro fiscal identity is the same one used by the existing sales publisher.
"""


def scoped_business_environment(env):
    cerro = env.cr.dbname in ('CERRO_EL_PLOMO', 'QA-CERROELPLOMO') or env.cr.dbname.startswith(('MANAGEMENT_QA_CERRO_', 'MANAGEMENT_QA_QA-CERRO_'))
    company = env['res.company'].search([('vat', '=', '76943293-0'), ('parent_id', '=', False)]) if cerro else env.ref('base.main_company')
    assert len(company) == 1, 'Canonical business company must be unambiguous'
    candidates = env['res.users'].search([
        ('active', '=', True), ('share', '=', False), ('id', '!=', 1),
        ('company_ids', 'in', company.ids)], order='id')
    editors = candidates.filtered(lambda user: user.has_group('base.group_system')
                                  and user.has_group('account.group_account_manager'))
    preferred = editors.filtered(lambda user: user.company_id == company)
    user = (preferred or editors)[:1]
    assert user, 'An existing country/port business editor is required; do not grant permissions'
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
    assert not scoped.su and scoped.company == company and company in user.company_ids
    return scoped
