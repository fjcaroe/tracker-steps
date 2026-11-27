"""Render Steps' posted invoices and credit notes through the existing report as two original users."""
from hashlib import sha256
from pathlib import Path
import re

from probe_sys_retained_provider_release import invoice_text


def run(env):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C','COMMUNITY_STEPS_CRM_FISCAL_20261127U45F')
    assert {row.split(':')[0].strip() for row in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    output = []
    for user in env['res.users'].browse([7,10]):
        assert user.active and not user.share
        scope=env(user=user.id,su=False,context={'allowed_company_ids':[1],'lang':user.lang})
        moves=scope['account.move'].search([('state','=','posted'),('move_type','in',('out_invoice','out_refund'))],order='id')
        assert len(moves)==21
        for move in moves:
            try:
                visible,_size=invoice_text(scope,move)
            except Exception as failure:
                cause=failure.__cause__ or failure
                output.append({'actor':user.id,'move':move.id,'error':type(failure).__name__,
                               'cause':type(cause).__name__,'technical_fields':re.findall(
                                   r"(?:attribute|field) '([a-zA-Z_][a-zA-Z0-9_]+)'",str(cause))})
                continue
            refs=move.l10n_cl_reference_ids
            output.append({'actor':user.id,'move':move.id,'kind':move.move_type,'references':len(refs),
                           'reference_numbers_printed':all(ref.origin_doc_number in visible for ref in refs),
                           'text':sha256(visible.encode()).hexdigest(),'template':move._get_name_invoice_report()})
    env.cr.rollback()
    return {'database':env.cr.dbname,'documents':output}
