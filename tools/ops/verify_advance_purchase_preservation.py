"""Compare original purchase COPY rows with a tested clone, without writing it.

The immutable source dump provides the original column list, so additional
addon columns do not hide a change to an existing purchase or source relation.
Only counts and hashes are recorded; business rows never enter the console.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def verify(stage):
    proof = json.loads((stage / 'qa_passed.json').read_text())
    database = proof['database']
    assert re.fullmatch('MANAGEMENT_QA_[A-Z_-]+_t175[a-z0-9_]*', database)
    dump = subprocess.check_output(['pg_restore', '--data-only', '--file=-',
                                    str(stage / 'source.dump')], text=True)
    results = {}
    for match in re.finditer(r'^COPY public\.(purchase_\w+) \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.\n',
                             dump, re.MULTILINE | re.DOTALL):
        table, columns, rows = match.groups()
        assert re.fullmatch(r'[\w", ]+', columns)
        sql = 'COPY (SELECT %s FROM public.%s) TO STDOUT;' % (columns, table)
        current = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-X', '-q',
            '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', sql], text=True)
        original_rows, current_rows = sorted(rows.splitlines()), sorted(current.splitlines())
        assert original_rows == current_rows, 'Existing purchase rows changed: ' + table
        results[table] = {'rows': len(original_rows),
            'sha256': hashlib.sha256('\n'.join(original_rows).encode()).hexdigest()}
    assert 'purchase_order' in results and 'purchase_order_line' in results
    result = {'database': database, 'release_sha256': proof['release_sha256'],
              'original_columns_preserved': True, 'tables': results}
    (stage / 'purchase-preservation.json').write_text(json.dumps(result, indent=2))
    print('T175_PURCHASE_PRESERVATION_OK ' + json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    assert args.stage.resolve().is_relative_to('/opt/steps-validation')
    verify(args.stage)
