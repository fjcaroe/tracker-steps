"""Compare private clone preservation hashes, without printing customer values."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import csv
import io
import manage_management as manager

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'));p.add_argument('run_id')
a=p.parse_args();assert re.fullmatch('[a-z0-9_]{1,24}',a.run_id)
stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
before=json.loads((stage/'business_before.json').read_text())
manager.BUSINESS=tuple(before);manager.TICKET_REVISION='client-revision';manager.CLIENT_REVISION_INITIAL=True
db='MANAGEMENT_QA_'+a.environment.upper()+'_'+a.run_id
after=manager.snapshot(db)
for table in before:
    if before[table]!=after[table]:
        print('PRESERVATION_DIFFERENCE',table,before[table],after[table],flush=True)
        raw=subprocess.check_output(['pg_restore','--data-only','--table',table,'-f','-',str(stage/'source.dump')],text=True)
        match=re.search(r'COPY public\.'+re.escape(table)+r' \(([^)]+)\) FROM stdin;\n(.*?)\n\\\.',raw,re.S)
        assert match
        columns=match[1].split(', ')
        original={row[columns.index('id')]:dict(zip(columns,row)) for row in csv.reader(io.StringIO(match[2]),delimiter='\t',quoting=csv.QUOTE_NONE)}
        # Compare each original value as PostgreSQL text (types/rounding intact).
        sql="SELECT json_agg(json_build_object('id',id,'values',json_build_array("+','.join('COALESCE('+name+"::text,'\\N')" for name in columns)+"))) FROM "+table
        changed={}
        for row in json.loads(manager.query(db,sql)):
            old=original[str(row['id'])]
            differences=[name for name,value in zip(columns,row['values']) if old[name]!=value]
            for name in differences:changed[name]=changed.get(name,0)+1
        print('ORIGINAL_COLUMNS_CHANGED',table,json.dumps(changed),flush=True)
