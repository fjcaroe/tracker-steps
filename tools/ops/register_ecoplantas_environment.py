"""Register the verified T176 customer demo without changing promotion policy."""
import argparse
import json
from pathlib import Path


ENTRY={'label':'ECOPLANTAS demo','url':'https://ecoplantas.stepsapp.cl','port':8084,
       'database':'ECOPLANTAS','service':'odoo18-ecoplantas.service',
       'config':'/etc/odoo18-ecoplantas.conf','role':'customer-demo','deploy_enabled':False,
       'authorization':'T176 y confirmación del solicitante: base independiente de demostración, sin traslado de suscripción'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--registry',type=Path,action='append',required=True)
    args=parser.parse_args()
    live=json.loads((args.evidence/'verified.json').read_text())
    published=json.loads((args.evidence/'published.json').read_text())
    assert live['database']=='ECOPLANTAS' and live['native_menus_and_forms']
    assert live['source_database_denied'] and live['license_copied'] is False
    assert published['url']==ENTRY['url'] and published['database']==ENTRY['database']
    for path in args.registry:
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        policy=json.dumps(data['policy'],sort_keys=True)
        old=data['environments'].get('ecoplantas')
        assert old is None or old==ENTRY,'Preserve a different existing registration'
        assert not any(value.get('database')=='ECOPLANTAS' or value.get('port')==8084
            for key,value in data['environments'].items() if key!='ecoplantas')
        data['environments']['ecoplantas']=ENTRY
        assert json.dumps(data['policy'],sort_keys=True)==policy
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('ECOPLANTAS_REGISTRY_OK '+str(path))


if __name__=='__main__':main()
