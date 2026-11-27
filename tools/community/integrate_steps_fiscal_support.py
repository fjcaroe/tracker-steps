"""Integrate the tested fiscal release into a restored copy of Steps sales, documents and support."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess

from admit_steps_fiscal_status import METADATA, MODULE, install_payload, regenerated_print_assets
from audit_steps_sales_schema import objects
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from recover_steps_fiscal_fields import CONTRACTS, WORK as FISCAL, exact_free_providers
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg
from restore_steps_sales_backup import BASE
from restore_sys_previred_pair import LOCK, require


TARGET = 'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A'
WORK = BASE/'steps-integrated-20261127U46A'
SEALED = BASE/'steps-sales-support-20261127U44H3/final-checkpoint'
CHECKPOINT = '4d50b17bdcf4cbe781c01569cbc12632e2dc114273497b56d4258ee298136dd1'
H3_SQL = '6ab22c9b15ce8074dad0e46ef9227cf935e4ebe1d7e021d7ff76e8b769a43485'


def attach_originals():
    pg('psql', '-X', '-v', 'ON_ERROR_STOP=1', '-d', TARGET, '-c', """DO $$ DECLARE changed integer; BEGIN
       IF current_database() <> 'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A' THEN RAISE EXCEPTION 'wrong database'; END IF;
       UPDATE ir_module_module SET state='installed' WHERE state='uninstalled' AND license='LGPL-3' AND
         ((name='l10n_cl' AND latest_version='18.0.3.1') OR (name='l10n_latam_invoice_document' AND latest_version='18.0.1.0'));
       GET DIAGNOSTICS changed = ROW_COUNT;
       IF changed <> 2 THEN RAISE EXCEPTION 'wrong original fiscal provider count'; END IF;
    END $$;""", stdout=subprocess.DEVNULL)


def integrate(checksum, repeat):
    require(Path(__file__).resolve().parent == WORK/'code' and WORK.resolve(strict=True) == WORK,
            'incorrect-steps-integration-directory')
    require(digest(SEALED/'checkpoint.json') == CHECKPOINT and digest(SEALED/'source.dump') == H3_SQL,
            'wrong-steps-support-release')
    accepted = json.loads((FISCAL/'releases'/checksum/'verified.json').read_bytes())
    require(accepted['package'] == checksum and accepted['modules'] == 163, 'tested-fiscal-release-required')
    frozen = json.loads(gzip.decompress((SEALED/'snapshot.json.gz').read_bytes()))
    providers = json.loads((SEALED/'providers.json').read_bytes())
    original_schema = json.loads(gzip.decompress((SEALED/'sql-objects.json.gz').read_bytes()))
    active = check_modules(TARGET)
    require(len(providers) == 162 and len(active) in (162,164,165) and all(active.get(n)==v for n,v in providers.items()),
            'restored-support-database-required')
    argv = json.loads((WORK/'private-args.json').read_bytes())
    require(argv[argv.index('-d')+1] == TARGET and '--no-http' in argv and '--net' in argv, 'wrong-integration-profile')
    overlay = exact_free_providers(set(providers),WORK/'fiscal-addons')
    version = install_payload(checksum,overlay)
    require(version.startswith('18.0.1.0.'), 'wrong-fiscal-field-provider')
    index, = [i for i,arg in enumerate(argv) if arg.startswith('--addons-path=')]
    roots = argv[index].split('=',1)[1].split(',')
    require(roots[0] in (str(WORK/'addons'),str(overlay)), 'wrong-integrated-addons-directory')
    if roots[0] != str(overlay):
        argv[index] = '--addons-path='+','.join([str(overlay),*roots])
    receipt = WORK/'fiscal-integration.json'
    if repeat:
        require(receipt.is_file() and json.loads(receipt.read_bytes())['package']==checksum and len(active)==165,
                'integrated-installation-required')
    if len(active)==162:
        verify_same(frozen,full_snapshot(TARGET))
        require(objects(TARGET)==original_schema,'restored-support-schema-drift')
        attach_originals()
        active = check_modules(TARGET)
    if len(active)==164 or repeat:
        command=argv.copy()
        command.remove('shell')
        with (WORK/'integrated-fiscal-install.log').open('ab') as log:
            subprocess.run(guarded_command(command+['-u' if repeat else '-i',MODULE],WORK,frozen),
                           stdout=log,stderr=log,check=True)
    final = check_modules(TARGET)
    require(final.keys()==providers.keys()|CONTRACTS.keys()|{MODULE} and final[MODULE]==[version,'LGPL-3']
            and all(final[name]==original for name,original in providers.items())
            and all(final[name]==[contract[0],'LGPL-3'] for name,contract in CONTRACTS.items()),
            'integrated-payables-module-inventory-differs')
    snapshot = full_snapshot(TARGET)
    require(objects(TARGET)==original_schema and all(frozen[k]==snapshot[k] for k in
            ('columns','constraints','sequence_definitions','relation_owner_and_acl')), 'integrated-fiscal-schema-drift')
    require(frozen['public_tables'].keys()==snapshot['public_tables'].keys(), 'integrated-fiscal-tables-differ')
    changed = {t for t,row in frozen['public_tables'].items() if snapshot['public_tables'][t]!=row}
    assets = regenerated_print_assets('COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3',TARGET) if 'ir_attachment' in changed else []
    business_changes=changed-METADATA-({'ir_attachment'} if assets else set())
    require(not business_changes,'integrated-business-data-changed-'+str(sorted(business_changes)))
    save(WORK/'private-args.json',argv)
    result={'source':CHECKPOINT,'database':TARGET,'modules':len(final),'package':checksum,'version':version,
            'protected_tables':len(snapshot['public_tables'])-len(changed),'changed_metadata':sorted(changed & METADATA),
            'regenerated_assets':assets,'repeat':repeat}
    save(WORK/('fiscal-repeat.json' if repeat else receipt.name),result)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checksum')
    parser.add_argument('--repeat',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        integrate(args.checksum,args.repeat)
