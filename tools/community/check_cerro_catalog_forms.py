"""Compare all 23 original forms and menus after the corrected Cerro catalogue upgrade."""
import fcntl
import hashlib
import json

from check_cerro_catalog_contracts import DB, DEST, PACKET
from check_cerro_cold_studio import histories, NATIVE_SOURCE
from check_cerro_combined_budget import BUDGET, PACKAGE, guard
from check_cerro_export_contacts import CONTACTS, directory
from check_cerro_freight_directory import FREIGHT
from check_cerro_studio_strict import ROOT, addon_roots, run
from compare_cerro_studio_receipts import compare, receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import FINAL_DEST, FINAL_TARGET

PROBE = """import json,sys
sys.path.insert(0,{tools!r})
from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_client import capture as client
from probe_cerro_studio_navigation import capture as routes
print('CORRECTED_CERRO_VIEWS',json.dumps(dict(fullread=fullread(env),client=client(env),routes=routes(env)),sort_keys=True))
env.cr.rollback()
"""


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        accepted=json.loads((DEST/'accepted-contracts.json').read_bytes())
        assert accepted['census']['installed']==188
        run('catalogue-forms',[],PROBE.format(tools=str(ROOT/'tools')),database=DB,directory=DEST,
            roots=[PACKET,CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(DB)])
        post=receipt(DEST/'catalogue-forms.log','CORRECTED_CERRO_VIEWS')
        current=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),
                        receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),post)
        reference=json.loads((FINAL_DEST/'qualified-export-contacts.json').read_bytes())['matrix']
        for key in ('original_routes','matching_studio_values','matching_full_record'):
            assert set(reference[key]).issubset(current[key])
        assert guard('verify',DB)==guard('verify',FINAL_TARGET) and directory(DB)==directory(FINAL_TARGET)
        original_histories=histories(NATIVE_SOURCE)
        assert histories(DB)==original_histories
        result=dict(matrix=current,prior=reference,histories=original_histories,
                    contract_evidence_sha256=hashlib.sha256((DEST/'accepted-contracts.json').read_bytes()).hexdigest())
        (DEST/'accepted-views.json').write_text(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
