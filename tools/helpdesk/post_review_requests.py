"""Post the explicitly authorized, brief client review requests, idempotently."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client

REQUESTS = {
    30: 'Contratos de compra está disponible en Desarrollo: https://desarrollo.stepsapp.cl. Pruebe un contrato con distintos precios de fruta y su calendario de anticipos.\nResponda «OK» si funciona; si falla, indique el contrato, el paso y el resultado esperado. No necesita responder nuevamente las definiciones que ya confirmó.',
    35: 'Exportaciones está disponible en Desarrollo: https://desarrollo.stepsapp.cl. Revise los menús y pruebe un embarque con gastos y liquidación del recibidor/IVV.\nResponda «OK» o indique la pantalla y el paso que falta o falla. Sus respuestas anteriores ya fueron consideradas.',
    38: 'Productores está disponible en Desarrollo: https://desarrollo.stepsapp.cl. Revise los menús y pruebe una liquidación y el consolidado por temporada/especie con sus ejercicios.\nResponda «OK» o indique el documento, el paso y el resultado esperado. No necesita repetir las respuestas ya entregadas.',
    41: 'Packing está disponible en Desarrollo: https://desarrollo.stepsapp.cl. Pruebe recepción → OT → materiales → cierre → costeo, con sus ejercicios.\nResponda «OK» o indique la OT y el paso que falla. La prueba con balanza física sigue separada en T45.',
    27: 'Las correcciones de Fletes están disponibles en Desarrollo: https://desarrollo.stepsapp.cl. Repita el caso que fallaba y revise planificación, registro y reporte.\nResponda «OK» o indique el flete y el paso que sigue fallando; puede adjuntar una captura. No necesita volver a responder las consultas anteriores.',
}


def plain(body):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', ' ', body or ''))).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--send', action='store_true', help='Only with explicit user authorization')
    parser.add_argument('--messages', type=Path, help='Explicitly reviewed mapping of ticket IDs to text')
    args = parser.parse_args()
    requests = REQUESTS if not args.messages else {int(k):v for k,v in json.loads(args.messages.read_text(encoding='utf-8-sig')).items()}
    assert all(k>0 and isinstance(v,str) and 0<len(v)<=3000 for k,v in requests.items())
    if not args.send:
        for ticket, body in requests.items():
            print(json.dumps({'ticket': ticket, 'body': body}, ensure_ascii=False))
        return
    cfg = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(cfg['db'], cfg['username'], cfg['api_key'], {})
    assert uid, 'Helpdesk authentication failed'
    rpc = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(cfg['db'], uid, cfg['api_key'], model, method, values, kwargs or {})
    for ticket, text in requests.items():
        body = ''.join('<p>'+html.escape(p)+'</p>' for p in text.split('\n'))
        previous = call('mail.message', 'search_read', [[('model','=','helpdesk.ticket'), ('res_id','=',ticket), ('message_type','=','comment')]], {'fields':['id','body'], 'order':'id desc', 'limit':100})
        matches = [m['id'] for m in previous if plain(m['body']) == plain(body)]
        if matches:
            print(json.dumps({'ticket':ticket, 'result':'already_posted', 'message':matches[0]}))
            continue
        exists = call('helpdesk.ticket', 'search_count', [[('id','=',ticket)]])
        assert exists == 1, 'Ticket missing'
        posted = call('helpdesk.ticket', 'message_post', [[ticket]], {'body':body, 'body_is_html':True, 'message_type':'comment', 'subtype_xmlid':'mail.mt_comment'})
        saved = call('mail.message', 'read', [[posted]], {'fields':['body','model','res_id']})[0]
        assert saved['model']=='helpdesk.ticket' and saved['res_id']==ticket and plain(saved['body'])==plain(body)
        print(json.dumps({'ticket':ticket, 'result':'posted_and_verified', 'message':posted}))


if __name__ == '__main__':
    main()
