"""Render a private layout preview from Development data; never an authenticated UI acceptance test."""
import argparse
import html
import json
from pathlib import Path
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    args.output.mkdir(parents=True,exist_ok=True)
    config=json.loads((Path.home()/'.odoo/desarrollo_api.json').read_text(encoding='utf-8'))
    def rpc(service,method,params):
        payload=json.dumps({'jsonrpc':'2.0','method':'call','params':{'service':service,'method':method,'args':params},'id':1}).encode()
        request=urllib.request.Request('https://desarrollo.stepsapp.cl/jsonrpc',data=payload,headers={'Content-Type':'application/json'})
        result=json.load(urllib.request.urlopen(request,timeout=60))
        if result.get('error'): raise RuntimeError(result['error'].get('message','RPC error'))
        return result['result']
    uid=rpc('common','authenticate',[config['db'],config['username'],config['api_key'],{}])
    assert uid,'Development authentication failed'
    def fmt(value,kind):
        if kind=='text': return html.escape(str(value or ''))
        if value is None:return '—'
        return format(value,',.1f').rstrip('0').rstrip('.').replace(',','|').replace('.',',').replace('|','.')+('%' if kind=='percent' else '')
    sections=[]
    for kind,title in [('producers','Comparativo de estimaciones'),('packing','Comparativo de procesos de Packing')]:
        data=rpc('object','execute_kw',[config['db'],uid,config['api_key'],'step.packing.order','operational_comparison',[],{'kind':kind,'filters':{}}])
        (args.output/(kind+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        cards=[]
        for table in data['tables']:
            columns=table['columns']
            head=''.join('<th scope="col">'+html.escape(c[1])+'</th>' for c in columns)
            def row(record):
                return '<tr>'+''.join('<td class="'+('o_agro_number' if c[2]!='text' else '')+'">'+fmt(record.get(c[0]),c[2])+'</td>' for c in columns)+'</tr>'
            body=''.join(row(record) for record in table['rows']) or '<tr><td colspan="%s">No hay datos para los filtros seleccionados.</td></tr>'%len(columns)
            cards.append('<article><h3>'+html.escape(table['title'])+'</h3><div class="o_agro_table_scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody><tfoot>'+row(table['total'])+'</tfoot></table></div></article>')
        filters=''.join('<label>'+label+'<select><option>Todas</option></select></label>' for label in ['Temporada','Mes','Semana','Especie'])
        sections.append('<section class="o_agro_comparison"><h2>'+title+'</h2><div class="o_agro_filters">'+filters+'</div><div class="o_agro_tables">'+''.join(cards)+'</div></section>')
    css=(root/'step_agro_analytics/static/src/comparison.scss').read_text(encoding='utf-8')
    baseline='body{margin:0;padding:12px;background:#f5f8f4;font-family:Arial,sans-serif}*{box-sizing:border-box}label{display:block}select{display:block;width:100%;border:1px solid #dce0e5;border-radius:4px;background:white;color:#243b4a}'
    document='<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisión de distribución T98/T99</title><style>'+baseline+css+'</style><main>'+''.join(sections)+'</main></html>'
    (args.output/'index.html').write_text(document,encoding='utf-8')
    print('Private layout preview generated; authenticated Odoo UI review remains separate')


if __name__=='__main__':main()
