"""Read actual filed documents through the original employee's access on the private Steps pair."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

from lxml import etree
from odoo import http
from odoo.addons.web.controllers.action import Action
from odoo.addons.web.controllers.binary import Binary
from odoo.exceptions import AccessError
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import EnvironBuilder


@contextmanager
def document_web_request(scope, path, params):
    builder = EnvironBuilder(path=path,query_string=params)
    try:
        request = http.Request(http.HTTPRequest(builder.get_environ()))
        request.db, request.env, request.params = scope.cr.dbname,scope,params
        request.session = http.Session({'uid':scope.uid,'db':scope.cr.dbname,'debug':''}, sid=None, new=True)
        request.session.can_save = False
        http._request_stack.push(request)
        try:
            yield
        finally:
            http._request_stack.pop()
    finally:
        builder.close()


def download(scope, attachment, size, checksum):
    with document_web_request(scope,'/web/content/'+str(attachment.id),{'download':'true'}):
        try:
            response = Binary().content_common(id=attachment.id,download='true')
        except (AccessError, Forbidden, NotFound):
            return None
        if isinstance(response, (Forbidden,NotFound)):
            return None
        try:
            if response.status_code in (403,404):
                return None
            assert response.status_code == 200
            response.direct_passthrough = False
            raw = response.get_data()
            assert len(raw) == size and hashlib.sha1(raw).hexdigest() == checksum
            return hashlib.sha256(raw).hexdigest()
        finally:
            if hasattr(response,'close'):
                response.close()


def read_filed_documents(env):
    native = env.cr.dbname == 'MANAGEMENT_QA_STEPS_CRM_20261126U42C'
    assert __debug__ and (native or env.cr.dbname in ('COMMUNITY_STEPS_CRM_DOC_20261127U43X',
                                                       'COMMUNITY_STEPS_CRM_DOC_20261127U44P',
                                                       'COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R',
                                                       'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3'))
    assert {line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    env.cr.execute("""SELECT a.id,a.file_size,a.checksum FROM documents_document d
        JOIN ir_attachment a ON a.id=d.attachment_id WHERE d.type='binary' AND a.store_fname IS NOT NULL""")
    originals = {key:(size,checksum) for key,size,checksum in env.cr.fetchall()}
    forms = 'documents.document_view_form' if native else 'step_document_library.library_form'
    people = env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)],order='id')
    samples = []
    denied = []
    for actor in people.filtered(lambda u: not u.has_group('base.group_system')):
        scope = env(user=actor.id,su=False,context={'allowed_company_ids':actor.company_ids.filtered('active').ids})
        library = scope['documents.document']
        menu = scope.ref('documents.dashboard')
        if menu.id not in scope['ir.ui.menu']._visible_menu_ids():
            continue
        assert not scope.su
        with document_web_request(scope,'/web/action/load',{}):
            action = Action().load(menu.action.id)
        assert action['res_model'] == library._name
        view = library.get_view(view_id=scope.ref(forms).id,view_type='form')
        assert etree.fromstring(view['arch'].encode()).tag == 'form'
        items = library.search([('type','=','binary'),('folder_id','!=',False),('attachment_id','!=',False)],order='id')
        checked = 0
        for doc in items:
            if not doc.folder_id.has_access('read'):
                continue
            attachment = doc.attachment_id
            size,checksum = originals.get(attachment.id,(0,None))
            if not 0 < size < 2_000_000:
                continue
            assert doc in library.search([('folder_id','=',doc.folder_id.id)])
            data = download(scope,attachment,size,checksum)
            if data is None:
                denied.append([actor.id,doc.id,attachment.id])
                continue
            if not native:
                assert doc in library.search(doc.folder_id.action_open()['domain'])
                assert doc.action_open()['url'] == '/web/content/'+str(attachment.id)+'?download=true'
            fields = doc.read(['id','folder_id','type','attachment_id'],load=None)[0]
            assert fields['attachment_id'] == attachment.id and fields['folder_id'] == doc.folder_id.id
            samples.append([actor.id,doc.id,doc.folder_id.id,attachment.id,size,data])
            checked += 1
            if checked == 4:
                break
    assert samples, 'no-original-nonadministrator-filed-document-sample'
    env.cr.rollback()
    return {'users': len({row[0] for row in samples}), 'reads': len(samples),
            'distinct_documents':len({row[1] for row in samples}),
            'denied':len(denied), 'denied_fingerprint':hashlib.sha256(json.dumps(denied).encode()).hexdigest(),
            'files_and_roles':hashlib.sha256(json.dumps(samples,separators=(',',':')).encode()).hexdigest()}
