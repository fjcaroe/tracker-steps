"""Compare invoice signing options in memory without storing signatures or editing invoices."""
from itertools import product


def run(env):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F','COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A')
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    scope = env(user=7, su=False, context={'allowed_company_ids': [1]})
    person = scope['res.users'].new({})
    rows = []
    types = ('entry', 'out_invoice', 'out_refund', 'in_invoice', 'in_refund', 'out_receipt', 'in_receipt')
    for enabled, assigned, signer, kind, state in product((False, True), (False, True), (False, True), types, ('draft','posted','cancel')):
        company = scope['res.company'].new({'sign_invoice': enabled, 'signing_user': person if assigned else False})
        move = scope['account.move'].new({'company_id': company, 'move_type': kind, 'state': state,
                                          'signing_user': person if signer else False})
        try:
            visible = bool(move.show_signature_area)
            signature = bool(move.signature)
        except AttributeError as exc:
            visible = signature = type(exc).__name__ + ':' + str(getattr(exc, 'name', ''))
        rows.append([enabled, assigned, signer, kind, state, visible, signature])
    env.cr.rollback()
    return {'database': env.cr.dbname, 'samples': rows}
