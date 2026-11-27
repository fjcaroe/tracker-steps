"""Compare Steps support access, ticket values, downloads and a real stage transition across both providers."""
import argparse
import json
from pathlib import Path


def verify(native, community, original_trial, candidate_trial):
    if not __debug__:
        raise ValueError('Enable all comparisons.')
    assert (native['tickets'],native['messages'],native['linked_attachments'])==(243,1795,418)
    assert {k:v for k,v in native.items() if k!='permissions'} == {k:v for k,v in community.items() if k!='permissions'}
    def index(doc):
        return {(r['actor'],tuple(r['companies'])):r for r in doc['permissions']}
    before,after = index(native),index(community)
    assert len(before)==len(native['permissions'])==len(after)==len(community['permissions'])==7 and before.keys()==after.keys()
    cases=[]
    for key,original in before.items():
        current=after[key]
        assert {k:v for k,v in original.items() if k!='form'}=={k:v for k,v in current.items() if k!='form'}, key
        assert ('form' in original)==('form' in current)
        if 'form' in original:
            fields = {'name','ticket_ref','partner_id','user_id','team_id','stage_id','description','tag_ids',
                      'priority','x_studio_accin_correctiva','x_studio_causas_del_ticket','x_studio_etapa_intermedia'}
            assert fields <= set(original['form']['fields']) and fields <= set(current['form']['fields'])
            cases.append((len(original['form']['fields']),len(current['form']['fields'])))
    assert original_trial['action']==541 and candidate_trial['action']>0
    assert {k:v for k,v in original_trial.items() if k!='action'}=={k:v for k,v in candidate_trial.items() if k!='action'}
    assert original_trial['original_sequence']==7 and original_trial['sequence_advance']==1
    assert candidate_trial['reopened_in_new_stage'] and candidate_trial['has_ticket_reference']
    return {'tickets':native['tickets'],'messages':native['messages'],'linked_attachments':native['linked_attachments'],
            'permissions':len(before),'form_fields':sorted(set(cases)),'trial':candidate_trial}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('native','community','original_trial','candidate_trial'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(*(json.loads(path.read_bytes()) for path in vars(args).values()))))
