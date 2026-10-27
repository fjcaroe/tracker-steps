"""Summarize accepted private HR proofs without publishing business values."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def test_count(path):
    text=path.read_text(encoding='utf-8-sig')
    assert not re.search(r' (ERROR|CRITICAL) ',text),str(path)
    counts=re.findall(r'0 failed, 0 error\(s\) of ([0-9]+) tests',text)
    assert counts,str(path)
    return max(map(int,counts))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--addon-commit',required=True)
    args=parser.parse_args();root=args.evidence.resolve();repo=args.repository.resolve()
    assert not args.output.resolve().is_relative_to(repo),'Evidence output must remain private'
    assert re.fullmatch('[0-9a-f]{7,40}',args.addon_commit)
    community=root/'community';cerro=root/'cerro-copy';engine=root/'payroll-engine'
    cp=read(community/'passed.json');sp=read(cerro/'passed.json');ep=read(engine/'passed.json')
    assert cp['profile']==sp['profile']=='hr' and sp['business_preserved']
    assert cp['writes_to_source'] is sp['writes_to_source'] is ep['writes_to_source'] is False
    files=read(community/'source-files.json');assert files==read(cerro/'source-files.json')
    actual={str(path.relative_to(repo)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
        for module in cp['modules'] for path in sorted((repo/module).rglob('*'))
        if path.is_file() and '__pycache__' not in path.parts}
    assert actual==files,'Repository addon package differs from the accepted package'
    before=read(cerro/'business-before.json');upgraded=read(cerro/'business-after-upgrade.json')
    assert before.keys()==upgraded.keys()
    assert all((row['rows'],row['hash'])==(upgraded[name]['rows'],upgraded[name]['hash']) for name,row in before.items())
    identity=read(cerro/'identity-before.json')
    assert read(cerro/'history-before.json')==read(cerro/'history-after.json')
    counters=[name for name in before if re.fullmatch(r'ir_sequence_[0-9]+(_[0-9]+)?',name)]
    audit=read(root/'audit.json')
    result={'addon_commit':args.addon_commit,'profile':'hr','modules':len(cp['modules']),'files':len(files),
        'source_files_sha256':hashlib.sha256((cerro/'source-files.json').read_bytes()).hexdigest(),
        'tests':{'community':test_count(community/'tests.log'),'cerro_copy':test_count(cerro/'tests.log'),
                 'oca_engine':test_count(engine/'tests.log')},
        'preserved':{'tables_projections':len(before)-len(counters),'standard_counters_during_upgrade':len(counters),
            **{name:len(identity[name]) for name in ('original_xmlids','ir_model','ir_model_fields',
                'ir_model_fields_selection','ir_model_access','ir_rule','ir_ui_menu','ir_model_relation')},
            'history_attachments_expiration':True,
            'permission_memberships':{name:before[name]['rows'] for name in
                ('res_groups_users_rel','res_company_users_rel','res_groups_implied_rel','rule_group_rel')}},
        'fixture_standard_counters_consumed':len(read(cerro/'fixture-counter-consumption.json')),
        'validated_environment_counts':{label:read(folder/'environment-counts.json') for label,folder in
            [('community',community),('cerro_copy',cerro),('oca_engine',engine)]},
        'source_inventory':audit['installed'],'payroll_counts':audit['counts'],
        'oca_revision':ep['oca_revision'],'official_community':ep['official_community'],
        'real_engine_native':ep['engine_native'],
        'source_code_matches_accepted_addons':True,'production_deployed':False,'qa_refreshed':False,
        'full_zero_enterprise_conversion_accepted':False}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
