"""Compare all original Steps binary links for the public visitor and existing external accounts."""
from collections import Counter
from hashlib import sha1, sha256
import json
import logging
from pathlib import Path

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import EnvironBuilder
from odoo import http


def run(env):
    native = env.cr.dbname == 'MANAGEMENT_QA_STEPS_CRM_20261126U42C'
    assert __debug__ and (native or env.cr.dbname in ('COMMUNITY_STEPS_CRM_DOC_20261127U44P',
                                                      'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3',
            'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A', 'COMMUNITY_STEPS_EXPENSE_20261127U50E', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F'))
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    env.cr.execute("""SELECT d.id,a.file_size,a.checksum FROM documents_document d JOIN ir_attachment a ON a.id=d.attachment_id
                      WHERE d.type='binary' AND a.store_fname IS NOT NULL ORDER BY d.id""")
    originals = env.cr.fetchall()
    assert len(originals)==81
    documents = env['documents.document'].with_context(active_test=False)
    if native:
        from odoo.addons.documents.controllers.documents import ShareRoute
        actual = ShareRoute().documents_content
        references = {pk:documents.browse(pk).access_token for pk,_,_ in originals}
    else:
        from odoo.addons.step_document_library_portal.controllers.documents import SharedDocument
        actual = SharedDocument().content
        references = {pk:documents.browse(pk)._original_external_reference() for pk,_,_ in originals}
    assert len(set(references.values()))==81 and all(references.values())
    public = env.ref('base.public_user')
    portal = env['res.users'].search([('share','=',True),('active','=',True),('id','!=',public.id)])
    assert portal and all(user.has_group('base.group_portal') for user in portal)
    result = {}
    original_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        for user in public | portal:
            scope = env(user=user.id,su=False,context={'allowed_company_ids':[user.company_id.id]})
            client = EnvironBuilder(path='/documents/content/',environ_base={'REMOTE_ADDR':'127.0.0.1'})
            req = http.Request(http.HTTPRequest(client.get_environ()))
            req.env,req.db,req.params = scope,env.cr.dbname,{}
            req.session = http.Session({'db':env.cr.dbname,'uid':None if user==public else user.id,'debug':''},sid=None,new=True)
            req.session.can_save = False
            http._request_stack.push(req)
            rows = []
            try:
                for pk,size,checksum in originals:
                    try:
                        response = actual(references[pk],download=True)
                    except (Forbidden,NotFound) as exc:
                        rows.append([pk,exc.code,None])
                        continue
                    try:
                        status = response.code if isinstance(response,(Forbidden,NotFound)) else response.status_code
                        assert status in (200,403,404)
                        strong = None
                        if status==200:
                            total, short, long = 0,sha1(),sha256()
                            for chunk in response.iter_encoded():
                                total += len(chunk)
                                short.update(chunk)
                                long.update(chunk)
                            assert total==size and short.hexdigest()==checksum
                            strong=long.hexdigest()
                        rows.append([pk,status,strong])
                    finally:
                        if hasattr(response,'close'):
                            response.close()
            finally:
                http._request_stack.pop()
                client.close()
            result[str(user.id)] = {'public':user==public,'responses':dict(Counter(row[1] for row in rows)),
                'status_and_bytes':sha256(json.dumps(rows,separators=(',',':')).encode()).hexdigest()}
    finally:
        logging.disable(original_level)
        env.cr.rollback()
    return {'files':len(originals),'scopes':result}
