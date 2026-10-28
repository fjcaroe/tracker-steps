"""Verify exported private API evidence against this checkout, without database access."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2]
    def read(mode,name):
        return json.loads((args.evidence/mode/(name+'.json')).read_text(encoding='utf-8'))
    packets=[read(mode,'source-files') for mode in ('community','cerro-reference')]
    assert packets[0]==packets[1], 'Different addon packets'
    for name,digest in packets[0].items():
        blob=subprocess.check_output(['git','-C',str(repo),'show','HEAD:'+name])
        assert hashlib.sha256(blob).hexdigest()==digest, name
        assert (repo/name).read_bytes().replace(b'\r\n',b'\n')==blob.replace(b'\r\n',b'\n'),name
    results={mode:read(mode,'passed') for mode in ('community','cerro-reference')}
    assert results['community']['counts']['enterprise']==0
    assert results['cerro-reference']['counts']['enterprise']==140
    assert all(not r['writes_to_source'] and not r['historical_conversion'] and not r['simpledigital_certified'] for r in results.values())
    assert len({r['source_files_sha256'] for r in results.values()})==1
    validator=subprocess.check_output(['git','-C',str(repo),'show','HEAD:tools/community/validate_payroll_api.py'])
    assert all(r['validator_sha256']==hashlib.sha256(validator).hexdigest() for r in results.values())
    before=read('cerro-reference','business-before')
    for name in ('business-after-upgrade','business-after'):
        after=read('cerro-reference',name)
        assert before.keys()==after.keys()
        assert all((v['rows'],v['hash'])==(after[k]['rows'],after[k]['hash']) for k,v in before.items()),name
    original=read('cerro-reference','identity-before');current=read('cerro-reference','identity-after')
    for name,rows in original.items():
        if rows and 'id' in rows[0]:
            indexed={row['id']:row for row in current[name]}
            assert all(indexed.get(row['id'])==row for row in rows),name
        else:
            assert all(row in current[name] for row in rows),name
    assert read('cerro-reference','history-before')==read('cerro-reference','history-after')
    result={'results':results,'original_business_contracts_preserved':len(before),
        'original_identity_rows_preserved':{key:len(rows) for key,rows in original.items()},
        'exact_packet_matches_checkout':True,'full_cerro_conversion':False,
        'simpledigital_certified':False,'deadline_resolved':False}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
