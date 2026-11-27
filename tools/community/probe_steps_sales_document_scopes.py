"""Reopen the original sales pipeline and check every document decision after installing support."""
from pathlib import Path

from probe_document_library_community import check_matrix
from probe_steps_crm_pipeline import run as open_pipeline


def run(env, matrix):
    assert __debug__ and env.cr.dbname in ('COMMUNITY_STEPS_CRM_DOC_20261127U44P','COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3',
            'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A', 'COMMUNITY_STEPS_EXPENSE_20261127U50E', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F')
    assert {row.split(':')[0].strip() for row in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    assert len(matrix['documents'])==len(set(matrix['documents']))==98
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    pipeline = open_pipeline(env,inspect_only=True)
    assert pipeline['phase']=='inspected' and pipeline['full_form']['records']==9 and pipeline['full_form']['fields']==72
    assert pipeline['full_form']['values']=='c16475d9351129e493c871c226f50e3f85bf3eb324db4c44fc3a226505e64b26'
    env.cr.execute('SET TRANSACTION READ ONLY')
    scopes, decisions = check_matrix(env,matrix)
    assert (scopes,decisions)==(7,686)
    env.cr.rollback()
    return {'sales':pipeline['full_form'],'documents':98,'user_company_scopes':scopes,'permission_decisions':decisions}
