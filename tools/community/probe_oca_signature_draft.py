"""Exercise only the unsigned draft workflow of the OCA provider in a clean Community database."""
import base64
import io
import json
import re
from pathlib import Path

from lxml import etree
from reportlab.pdfgen.canvas import Canvas


def probe(env):
    assert re.fullmatch(r'COMMUNITY_LABOR_SIGN_[A-Z0-9_]{1,30}', env.cr.dbname)
    assert {row.split(':')[0].strip() for row in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    modules = env['ir.module.module'].search([('state', '=', 'installed')])
    assert not modules.filtered(lambda mod: mod.license == 'OEEL-1')
    provider = modules.filtered(lambda mod: mod.name == 'sign_oca')
    assert provider.latest_version == '18.0.1.4.4' and provider.license == 'AGPL-3'
    user = env.ref('base.user_admin')
    scope = env(user=user.id, su=False, context={'allowed_company_ids': user.company_ids.ids,
                                              'mail_notify_force_send': False, 'bin_size': False})
    assert not scope.su and scope.user.has_group('sign_oca.sign_oca_group_user')
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.drawString(80, 750, 'Prueba privada de documento sin firma')
    canvas.save()
    original = stream.getvalue()
    Request = scope['sign.oca.request']
    assert Request.search_count([]) == 0
    draft = Request.create({'name': 'Ensayo privado', 'filename': 'ensayo.pdf',
                            'data': base64.b64encode(original), 'company_id': scope.company.id})
    assert draft.state == '1_draft' and base64.b64decode(draft.data) == original
    assert not draft.signer_ids and draft.user_id == scope.user
    action = draft.get_formview_action()
    assert action['res_model'] == Request._name and action['res_id'] == draft.id
    arch = etree.fromstring(Request.get_view(view_id=scope.ref('sign_oca.sign_oca_request_form_view').id,
                                            view_type='form')['arch'].encode())
    assert arch.xpath('//field[@name="signer_ids"]') and arch.xpath('//button[@name="configure"]')
    draft.cancel()
    assert draft.state == '3_cancel'
    env.cr.rollback()
    assert Request.search_count([]) == 0
    print('OCA_SIGNATURE_DRAFT=' + json.dumps({'uid': user.id, 'pdf_preserved': True,
          'draft_form': True, 'cancelled': True, 'signers': 0, 'enterprise_modules': 0,
          'installed_modules': len(modules), 'provider': provider.latest_version}))


if 'env' in globals():
    probe(env)
