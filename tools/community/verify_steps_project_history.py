"""Compare the restored Steps project menus, linked farm masters and historical attachments."""
import argparse
import json
from pathlib import Path


TARGET = 'COMMUNITY_STEPS_PROJECT_20261127U51Q'
FIELDS_PENDING = {'project.project': {'total_budget_amount','total_budget_progress'},
                  'project.task': {'dependency_warning','planning_overlap','leave_warning'}}
BUDGET_KANBAN_FIELDS = {'account_id','company_id','x_plan2_id'}


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def verify(native, current, ref_trial, trial, install, preservation):
    check(native['database'] == 'MANAGEMENT_QA_STEPS_CRM_20261126U42C' and
          current['database'] == install['database'] == preservation['database'] == TARGET, 'Wrong project reference')
    check(install['modules']==173 and install['preserved_sql_objects']==15183 and install['new_sql_objects']==18 and
          preservation['tables']==1116 and install['files']==preservation['files']==1748 and install['addresses_preserved']==1586,
          'Incomplete project catalogue, contacts or physical storage')
    check(len(native['cases'])==len(current['cases'])==7,'Incomplete project permission matrix')
    menus = set()
    for old,new in zip(native['cases'],current['cases']):
        check(all(old[k]==new[k] for k in ('actor','companies','linked_documents')), 'Project attachment permissions or content differ')
        for name,row in old['models'].items():
            candidate = new['models'][name]
            check(all(row.get(k)==candidate.get(k) for k in ('rows','read','acl')), 'Project records or CRUD access differ')
            check({k:v for k,v in row.get('fields',{}).items() if k not in FIELDS_PENDING.get(name,set())}
                  ==candidate.get('fields',{}),'Project identities, stages, documents or farm master relations differ')
        for name,menu in old['menus'].items():
            observed = new['menus'][name]
            check(menu['visible']==observed['visible'],'Project menu visibility changed')
            if not menu['visible']:
                continue
            menus.add(name)
            check(menu['action']==observed['action'] and menu['model']==observed['model']
                  and menu['views'].keys()==observed['views'].keys(), 'The original project route changed')
            for key,view in observed['views'].items():
                expected = menu['views'][key]
                omitted = FIELDS_PENDING.get(menu['model'],set())
                if key == 'kanban' and menu['model']=='project.project':
                    # The retired budget card used these hidden fields. Their actual project values are still checked above.
                    omitted = omitted | BUDGET_KANBAN_FIELDS
                check(not view['undefined'] and view['id']==expected['id'] and
                      set(view['fields'])==set(expected['fields'])-omitted,
                      'Missing registered field in a project client view')
                if key=='form':
                    check(view['document_buttons']==expected['document_buttons'],'Task document action is missing')
    check(len(menus)==3,'Incomplete original project navigation')
    check(ref_trial['history_unchanged'] and {k:v for k,v in ref_trial.items() if k!='history_unchanged'}==trial
          and trial['moved_to_second_stage'] and trial['original_stages']==1,'Task creation, milestone or stage transition differs')
    complete,=[case for case in current['cases'] if case['actor']==2 and set(case['companies'])=={1,2}]
    counts={model:len(row.get('rows',[])) for model,row in complete['models'].items()}
    check(counts=={'project.project':1,'project.task':6,'project.milestone':2},'Historical project records missing')
    check(len(complete['linked_documents'])==2 and sum(len(v.get('files',[])) for v in complete['linked_documents'].values())==3
          and all(len(file)==3 for v in complete['linked_documents'].values() for file in v.get('files',[])),
          'Not all three original project files could be downloaded')
    return {'providers':173,'projects':1,'tasks':6,'milestones':2,'project_files':3,'menus':len(menus),
            'permissions':7,'new_task_and_stage_transition':True,'physical_files':1748,'preserved_sql_objects':15183,
            'address_records_preserved':1586}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts',type=Path,nargs=6)
    options = parser.parse_args()
    print(json.dumps(verify(*(json.loads(path.read_bytes()) for path in options.receipts)),sort_keys=True))
