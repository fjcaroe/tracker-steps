"""Record T233 publication and browser recheck silently, preserving its stage."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--reviewed-message', required=True, type=int)
    args = parser.parse_args()
    root = args.evidence
    publication = json.loads((root/'publication.json').read_text(encoding='utf-8'))
    gui = json.loads((root/'browser-review.json').read_text(encoding='utf-8'))
    for target in ('development', 'qa-cerro', 'cerro'):
        p = publication[target]
        assert p['backend_commit'] == '3bdbd5bbf62d65e9e005cf34b35757e4b730adda'
        assert p['web_commit'] == 'e14075aaef7a9e71448e087b52bd80e9cebacff0'
        assert p['web_version'] == '0.0.5' and p['addon_version'] == '18.0.1.2.1'
        assert len(p['served']) == 5 and p['served'] == publication['cerro']['served']
    assert gui['environment'] == 'cerro' and gui['database'] == 'CERRO_EL_PLOMO'
    assert all(gui[key] for key in ('plot_selector', 'plots_filtered_by_center',
        'plot_selection_reset', 'local_plot_saved', 'mobile_layout', 'no_native_business_writes'))
    assert hashlib.sha256((root/'cerro-cuartel-form.jpg').read_bytes()).hexdigest() == gui['screenshot_sha256']
    config = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
        'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method,
            values, dict({'context': context}, **(kwargs or {})))

    stage = call('helpdesk.ticket', 'read', [[233]], {'fields': ['stage_id']})[0]['stage_id'][0]
    assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
        ('res_id', '=', 233), ('id', '>', args.reviewed_message),
        '|', ('message_type', 'in', ['comment', 'email']), ('attachment_ids', '!=', False)]])
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', 233)]
    before = {name: set(call(name, 'search', [domain])) for name in ('mail.notification', 'mail.mail')}
    body = ('Revisado el aviso de actualización faltante en Cerro El Plomo. El servidor ya sirve '
        'Harvest 0.0.5 y Steps Harvest 18.0.1.2.1, con los mismos cinco archivos web y el mismo '
        'backend que Desarrollo y QA-Cerro. Se repitió el formulario móvil en Cerro: '
        'Configuración → Nivel de ubicación → Cuartel; OT → Nueva OT → Centro de costo → Cuartel. '
        'El centro Legacy mostró C14/C15; al cambiar de centro se borró la selección y cambiaron '
        'los cuarteles. La jornada local conservó C14 al guardar. No se sincronizaron documentos '
        'de producción durante la revisión. La configuración se conserva por navegador, base, '
        'usuario y empresa; configurarla en QA no la configura en Cerro. Recargar Harvest y '
        'verificar la versión 0.0.5 antes de repetir el recorrido. No se reprodujo una diferencia '
        'de publicación y no se repitió la instalación. Se conserva el estado del ticket para '
        'la validación del reporte del cliente. Web e14075aa; backend 3bdbd5bb.')
    note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 233,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>'+html.escape(body)+'</p>'}])
    assert call('helpdesk.ticket', 'read', [[233]], {'fields': ['stage_id']})[0]['stage_id'][0] == stage
    for name, ids in before.items():
        assert set(call(name, 'search', [domain])) == ids
    print('T233_REVIEW_RECORDED note=%s stage=%s NO_NOTIFICATIONS_OK' % (note, stage))


if __name__ == '__main__':
    main()
