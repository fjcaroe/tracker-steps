"""Compare original dump rows to a clone; output column names only, never values."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('environment',choices=['development','steps']);p.add_argument('run_id');a=p.parse_args()
    assert re.fullmatch('[a-z0-9_]{1,20}',a.run_id)
    stage=Path('/opt/steps-validation')/('whatsapp_'+a.environment+'_'+a.run_id)
    database='WHATSAPP_QA_'+a.environment.upper()+'_'+a.run_id
    for table in ['helpdesk_ticket','mail_message','ir_attachment']:
        dump=subprocess.check_output(['pg_restore','--data-only','--table='+table,'-f','-',str(stage/'source.dump')],text=True)
        match=re.search(r'COPY public\.'+table+r' \(([^\n]+)\) FROM stdin;\n(.*?)\n\\\.',dump,re.S)
        if not match:continue
        columns=[c.strip().strip('"') for c in match[1].split(',')]
        assert all(re.fullmatch('[a-z0-9_]+',c) for c in columns)
        source={r.split('\t')[columns.index('id')]:r.split('\t') for r in match[2].splitlines() if r}
        selected=','.join('"'+c+'"' for c in columns)
        current=subprocess.check_output(['sudo','-u','postgres','psql','-d',database,'-Atc','COPY (SELECT '+selected+' FROM '+table+') TO STDOUT'],text=True)
        target={r.split('\t')[columns.index('id')]:r.split('\t') for r in current.splitlines() if r}
        changes=Counter();different=0;missing=0
        for key,record in source.items():
            if key not in target:
                missing+=1
                metadata=dict(zip(columns,record))
                print(json.dumps({'missing_metadata':{'table':table,'model':metadata.get('res_model'),
                    'public':metadata.get('public'),'mime':metadata.get('mimetype'),
                    'generated_asset':metadata.get('url','').startswith('/web/assets/')}}))
                continue
            fields=[c for c,x,y in zip(columns,record,target[key]) if x!=y]
            if fields:different+=1;changes.update(fields)
        print(json.dumps({'table':table,'original':len(source),'missing':missing,'changed':different,'columns':dict(changes)}))


if __name__=='__main__':main()
