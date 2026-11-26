"""Open the original document library as an internal user without reading file or signature data."""
import json
import re
from pathlib import Path

from lxml import etree


def probe(env):
    assert re.fullmatch(r'MANAGEMENT_QA_(?:(?:STEPS|CERRO)_CUSTODY|SYS_LABOR_DOC)_[A-Z0-9_]{1,30}', env.cr.dbname)
    interfaces = Path('/proc/net/dev').read_text().splitlines()[2:]
    assert {row.split(':')[0].strip() for row in interfaces} == {'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    candidates = env['res.users'].search([
        ('active', '=', True), ('share', '=', False), ('id', '!=', 1),
        ('groups_id', 'in', env.ref('documents.group_documents_user').ids),
    ], order='id')
    ordered = sorted(candidates, key=lambda user: (user.has_group('base.group_system'), user.id))
    for user in ordered:
        scope = env(user=user.id, su=False, context={'allowed_company_ids': user.company_ids.ids})
        library = scope['documents.document']
        binary = library.search([('type', '=', 'binary'), ('folder_id.type', '=', 'folder'),
                                 ('attachment_id', '!=', False)], limit=1)
        if binary and binary.folder_id.has_access('read'):
            break
    else:
        raise AssertionError('no original internal reader with access to a filed document')
    assert not scope.su
    menu = scope.ref('documents.dashboard')
    assert menu.id in scope['ir.ui.menu']._visible_menu_ids() and menu.action.res_model == library._name
    view = library.get_view(view_id=scope.ref('documents.document_view_form').id, view_type='form')
    assert etree.fromstring(view['arch'].encode()).tag == 'form'
    rows = library.search([('folder_id', '=', binary.folder_id.id)])
    assert binary in rows
    binary.check_access('read')
    data = binary.read(['type', 'folder_id', 'attachment_id'], load=None)[0]
    assert data['type'] == 'binary' and data['folder_id'] == binary.folder_id.id
    assert data['attachment_id'] == binary.attachment_id.id
    binary.attachment_id.check_access('read')
    print('DOCUMENT_LIBRARY_NATIVE=' + json.dumps({
        'uid': user.id, 'system_group': user.has_group('base.group_system'),
        'visible_active_documents': library.search_count([]), 'folder_entries': len(rows),
        'dashboard_and_form': True, 'original_attachment_acl': True, 'transaction_read_only': True,
    }))
    env.cr.rollback()


if 'env' in globals():
    probe(env)
