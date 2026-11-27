"""Record archived picking, quality and packing controls in the original private Cerro operator registry."""
import fcntl
import json
from pathlib import Path

from check_cerro_schema_counterexamples import native_read
from record_cerro_concept_reference import DEST, NATIVE, state


PROBES = (
    ('probe_cerro_reception_flow','exercise','picking-fruit-physical-u46','native-fruit-receipt-flow-u46.json'),
    ('probe_cerro_picking_lists','exercise','picking-quality-search-u46','native-picking-search-u46.json'),
    ('probe_cerro_picking_lists','search_cases','picking-quality-mixed-search-u46','native-picking-mixed-search-u46.json'),
    ('probe_cerro_packing_landscape','capture','packing-fields-u46','native-packing-fields-u46.json'),
    ('probe_cerro_pack_report_rows','controls','picking-pack-controls-u46','native-pack-report-controls-u46.json'),
    ('probe_cerro_pack_report_rows','capture','full-packing-operators-u46','native-pack-orders-u46.json'),
)


def run():
    with open('/run/lock/steps-environments.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for module,method,phase,name in PROBES:
            body=("import sys,json\nsys.path.insert(0,"+repr(str(DEST/'code'))+")\nfrom "+module+" import "+method+
                  "\nprint('PACKING_ORIGINAL',json.dumps("+method+"(env),sort_keys=True))")
            pointers=state(NATIVE)
            try:
                result=native_read(body,phase,'PACKING_ORIGINAL')
            finally:
                state(NATIVE,pointers)
                assert state(NATIVE)==pointers
            path=DEST/name
            if path.exists():
                assert json.loads(path.read_bytes())==result, name
            else:
                with path.open('x') as evidence:
                    json.dump(result,evidence,sort_keys=True)


if __name__=='__main__':
    run()
