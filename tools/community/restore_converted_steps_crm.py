"""Seal and restore the admitted Steps CRM cohort, its exact free runtime and complete physical filestore."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace

from complete_converted_filestore import complete
from custody_sys_previred_filestore import digest
from prepare_steps_crm_cohort import RUNTIME, SOURCE_MANIFESTS
from restore_converted_sys_cohort import restore, save
from restore_sys_previred_pair import LOCK, require
from verify_converted_sql_schema import verify


def recover(root, output, release, checksum, suffix):
    require(re.fullmatch('[A-Z0-9]{1,24}', suffix) and re.fullmatch('[a-f0-9]{64}', checksum),
            'expected-recovery-identities')
    require(root.resolve(strict=True) == root and root.is_relative_to('/opt/steps-validation')
            and release.resolve(strict=True) == release and digest(release) == checksum, 'private-sealed-inputs')
    source = root/'preservation.json'
    proof = json.loads(source.read_bytes())
    original_db = proof['community']
    require(re.fullmatch(r'COMMUNITY_STEPS_CRM_(?!RECOVERY_)[A-Z0-9_]+', original_db)
            and proof['preserved_tables_and_schema'] and proof['preserved_counters'] and proof['active'] == 157
            and proof['attachment_objects'] == 1744 and proof['manifest_sha256'] == SOURCE_MANIFESTS
            and proof['source_dump_sha256'] == '8247457c4469d314fb3eeb44202604a1c294cfa374d426f30f31c9a16144f7ca',
            'original-admitted-steps-cohort-required')
    target = 'COMMUNITY_STEPS_CRM_RECOVERY_'+suffix
    quotation_source = original_db.startswith('COMMUNITY_STEPS_CRM_QUOTE_')
    if quotation_source:
        forms = json.loads((root/'quotation-forms.json').read_bytes())
        require(forms['ui']['database'] == original_db and forms['ui']['inactive_views'] == [1443,1444,1445,1446]
                and forms['ui']['inactive_menu'] == 329 and forms['ui']['original_action_retained'] == 481
                and forms['sql']['preserved_counters'] and forms['sql']['unexpected_modules'] == [],
                'qualified-quotation-interface-required')
    args = SimpleNamespace(source=original_db, target=target, tablespace='steps_community_storage_20261028_community',
                           expected_active=157, output=output, release=release, release_sha256=checksum,
                           runtime=RUNTIME, addons=[RUNTIME/'addons',RUNTIME/'odoo/addons'],
                           source_data=root/'data', allow_forward_sequences_on_source=False)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(args)
        complete(output, root/'data/filestore'/original_db)
        verify(output)
        recovered = json.loads((output/'restore-proof.json').read_bytes())
        physical = json.loads((output/'sealed/filestore-physical.json').read_bytes())
        require(recovered['simultaneous_physical_tree_sha256'] == physical['tree_sha256']
                and not recovered['forward_manifests_on_source'] and recovered['counts'] == proof['counts']
                and recovered['rows'] == proof['rows'], 'frozen-steps-package-drift')
        if quotation_source:
            require(recovered['role_probe'].get('sale_quotation') == {
                'form_initialized':True, 'action':526, 'historical_orders':4}, 'restored-quotation-form-required')
            recovered['quotation_form_receipt_sha256'] = digest(root/'quotation-forms.json')
            save(output/'restore-proof.json',recovered)
    print('STEPS_COLD_RESTORE_COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','output','release'):
        parser.add_argument('--'+name, type=Path, required=True)
    for name in ('release-sha256','suffix'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    recover(args.candidate,args.output,args.release,args.release_sha256,args.suffix)
