"""Admit the Steps expense document action and remove unused OCR inheritance on its restored company copy."""
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess

from admit_steps_fiscal_status import METADATA
from admit_steps_support_portal import release
from audit_steps_sales_schema import objects
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import check_modules, full_snapshot, save
from restore_native_product_backup import query
from restore_steps_expenses import ANCHORS, TARGET, WORK
from restore_sys_previred_pair import LOCK, require


MODULE = 'step_expense_documents'
PACKAGE = '28b5ba914b7d0a2047b8a7478889e56bc323bf7f68e1da95de9f547e7d3e7e4a'
OCR = [3511, 3512, 3513, 3514]


def arches():
    return query(TARGET, "SELECT md5(string_agg(jsonb_build_array(id,inherit_id,arch_db)::text,'' ORDER BY id)) FROM ir_ui_view")


def run():
    require(Path(__file__).resolve().parent == WORK/'code' and (WORK/'expense-view-migration.json').is_file(),
            'wrong-expense-copy')
    area = WORK/'expense-documents'
    overlay = release(MODULE, area/(PACKAGE+'.tar'), PACKAGE, area)
    args = json.loads((WORK/'private-args.json').read_bytes())
    require(args[args.index('-d')+1] == TARGET and '--no-http' in args and '--net' in args, 'unexpected-expense-profile')
    marker = area/'baseline.json.gz'
    if not marker.exists():
        active = check_modules(TARGET, 'hr_expense')
        require(len(active) == 166 and MODULE not in active and 'step_payment_in_process' in active,
                'expected-restored-166-product')
        initial = {'providers': active, 'catalog': full_snapshot(TARGET, ANCHORS), 'objects': objects(TARGET),
                   'views': arches(), 'active_views': json.loads(query(TARGET,
                   'SELECT json_agg(id ORDER BY id) FROM ir_ui_view WHERE active'))}
        temp = marker.with_suffix('.pending')
        temp.write_bytes(gzip.compress(json.dumps(initial).encode()))
        temp.replace(marker)
    initial = json.loads(gzip.decompress(marker.read_bytes()))
    paths, = [idx for idx,v in enumerate(args) if v.startswith('--addons-path=')]
    roots = args[paths].split('=',1)[1].split(',')
    args[paths] = '--addons-path='+','.join([str(overlay)]+[p for p in roots if p != str(overlay)])
    expected = {**initial['providers'], MODULE: ['18.0.1.0.0','AGPL-3']}
    sequence_activity = {}
    for mode in ('install', 'update'):
        active = check_modules(TARGET, 'hr_expense')
        if mode == 'update' or MODULE not in active:
            command = args.copy()
            command.remove('shell')
            with (area/(mode+'.log')).open('ab') as log:
                subprocess.run(guarded_command(command+['-i' if mode == 'install' else '-u', MODULE], WORK,
                                               initial['catalog']), check=True, stdout=log, stderr=log)
        require(check_modules(TARGET, 'hr_expense') == expected and objects(TARGET) == initial['objects'],
                'wrong-expense-modules-or-schema')
        current = full_snapshot(TARGET, ANCHORS)
        frozen = initial['catalog']
        require(all(current[k] == frozen[k] for k in frozen if k not in ('public_tables','sequence_values')),
                'expense-schema-changed')
        changed = {n for n,row in frozen['public_tables'].items() if row != current['public_tables'][n]}
        require(changed <= METADATA, 'unexpected-expense-data-change-'+str(sorted(changed-METADATA)))
        enabled = set(json.loads(query(TARGET, 'SELECT json_agg(id ORDER BY id) FROM ir_ui_view WHERE active')))
        require(enabled == set(initial['active_views'])-set(OCR) and arches() == initial['views'],
                'unrelated-expense-view-changed')
        sequence_activity[mode] = sorted(n for n,v in frozen['sequence_values'].items() if current['sequence_values'][n] != v)
        save(WORK/'private-args.json', args)
    result = {'database': TARGET, 'modules': len(expected), 'package': PACKAGE, 'original_ocr_views': OCR,
              'unchanged_tables': len(frozen['public_tables'])-len(changed), 'changed_metadata': sorted(changed),
              'sql_objects': len(initial['objects']), 'sequence_activity': sequence_activity}
    save(area/'admission.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run()
