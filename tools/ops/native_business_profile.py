"""Select an existing business editor in the canonical destination company.

Never widen permissions or infer the business company from the technical admin.
The Cerro fiscal identity is the same one used by the existing sales publisher.
"""


def scoped_existing_user_environment(env, user_id, company=None):
    """Select exactly the requested existing internal profile, with no fallback."""
    assert isinstance(user_id, int) and user_id > 1, 'Select an existing non-superuser profile'
    user = env['res.users'].browse(user_id).exists()
    assert len(user) == 1 and user.active and not user.share, 'An active internal user is required'
    company = company if company is not None else user.company_id
    assert len(company) == 1 and company in user.company_ids, 'The user is not authorized in this company'
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
    assert not scoped.su and scoped.user == user and scoped.company == company
    return scoped


def scoped_business_environment(env, company=None):
    cerro = env.cr.dbname in ('CERRO_EL_PLOMO', 'QA-CERROELPLOMO') or env.cr.dbname.startswith(('MANAGEMENT_QA_CERRO_', 'MANAGEMENT_QA_QA-CERRO_'))
    company = company or (env['res.company'].search([('vat', '=', '76943293-0'), ('parent_id', '=', False)]) if cerro else env.ref('base.main_company'))
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
