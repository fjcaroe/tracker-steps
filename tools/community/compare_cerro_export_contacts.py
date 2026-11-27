"""Recheck all readable receiver role values and native write restrictions on both complete private registries."""
import argparse
import configparser
import fcntl
import hashlib
import json
import subprocess
from pathlib import Path

from check_cerro_combined_budget import PACKAGE,BUDGET
from check_cerro_export_contacts import CONTACTS,directory,profile
from check_cerro_studio_strict import ROOT,addon_roots,run
from compare_cerro_studio_receipts import receipt
from restore_cerro_native_catalog_graph import TRIAL as NATIVE, TARGET as NATIVE_DB
from restore_cerro_studio_strict import SOURCE

def main(fresh=False):
    db,dest,freight,_=profile(fresh)
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        final=dest/'qualified-export-contacts.json'
        assert (NATIVE/'verified-histories.json').is_file() and final.is_file()
        body='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        body+="from probe_cerro_export_contacts import capture,exercise\n"
        body+="data=capture(env)\nexercise(env)\nassert capture(env)==data\nprint('CERRO_CONTACTS',json.dumps(data,sort_keys=True))\nenv.cr.rollback()"
        conf=Path('/etc/odoo18-cerroelplomo.conf')
        parser=configparser.ConfigParser(interpolation=None)
        parser.read(conf)
        receipt_files=json.loads((ROOT/'tools/cerro_native_providers_receipt.json').read_text())
        paths=','.join(str(Path('/opt/steps-validation')/name) for name in receipt_files['roots'])
        cmd=['unshare','--net','runuser','-u','cerro_odoo18','--','/usr/bin/python3.10','/opt/odoo18/odoo-bin',
             'shell','-c',str(conf),'-d',NATIVE_DB,'--db-filter=^'+NATIVE_DB+'$','--db_host=/var/run/postgresql',
             '--data-dir='+str(NATIVE/'data'),'--logfile='+str(NATIVE/'data/contacts.log'),'--without-demo=all',
             '--workers=0','--max-cron-threads=0','--load=base,web','--no-http','--stop-after-init',
             '--addons-path='+paths+','+parser['options']['addons_path']]
        native=NATIVE/'native-contact-roles.log'
        with native.open('w') as out:
            subprocess.run(cmd,input=body,text=True,stdout=out,stderr=out,check=True)
        assert directory(db)==directory(SOURCE)
        run('compared-contact-roles',[],body,database=db,directory=dest,
            roots=[CONTACTS,freight,BUDGET,PACKAGE,*addon_roots(db)])
        values=receipt(dest/'compared-contact-roles.log','CERRO_CONTACTS')
        assert values==receipt(native,'CERRO_CONTACTS') and len(values)==9
        assert directory(db)==directory(SOURCE)
        result=json.loads(final.read_text())
        result['comparison_contexts']=len(values)
        result['readable_roles_sha256']=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()
        (dest/'qualified-compared-export-contacts.json').write_text(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fresh',action='store_true')
    main(parser.parse_args().fresh)
