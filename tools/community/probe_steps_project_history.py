"""Audit original Steps project records and the views returned by their menu actions, with real user scopes."""
from pathlib import Path
from hashlib import sha256

from lxml import etree
from odoo.exceptions import AccessError
from odoo.osv.expression import AND
from odoo.tools.safe_eval import safe_eval
from probe_steps_accounting_history import fingerprint


DATABASES = ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F',
             'COMMUNITY_STEPS_EXPENSE_20261127U50E', 'COMMUNITY_STEPS_PROJECT_20261127U51P',
             'COMMUNITY_STEPS_PROJECT_20261127U51Q')
FIELDS = {
    'project.project': ('name', 'active', 'user_id', 'company_id', 'partner_id', 'privacy_visibility', 'stage_id',
                        'date_start', 'date', 'task_ids', 'milestone_ids', 'account_id', 'allow_milestones',
                        'total_budget_amount', 'total_budget_progress', 'documents_folder_id', 'documents_tag_ids',
                        'use_documents', 'document_count'),
    'project.task': ('name', 'active', 'project_id', 'parent_id', 'child_ids', 'stage_id', 'state', 'priority',
                     'company_id', 'user_ids', 'partner_id', 'milestone_id', 'date_assign', 'date_deadline',
                     'allocated_hours', 'tag_ids', 'description', 'depend_on_ids', 'planned_date_begin', 'cost_id',
                     'num_op', 'grupo_variedad_id', 'variedad_id', 'step_agricultural_task', 'document_count',
                     'project_use_documents', 'planning_overlap', 'dependency_warning', 'leave_warning'),
    'project.milestone': ('name', 'project_id', 'deadline', 'is_reached', 'reached_date'),
}
MENUS = ('project.menu_projects', 'project.menu_project_management_all_tasks', 'project.menu_projects_config')


def linked_documents(scope, tasks):
    results = {}
    for task in tasks:
        if not task.document_count:
            continue
        task_view = task.get_view(view_type='form')
        arch = etree.fromstring(task_view['arch'])
        assert arch.xpath('//button[@name="action_view_documents_project_task"]')
        action = task.action_view_documents_project_task()
        assert action['res_model'] == 'documents.document'
        expression = action.get('domain', [])
        variables = scope['ir.actions.actions']._get_eval_context()
        variables.update(active_id=task.id, active_ids=task.ids, active_model=task._name)
        if isinstance(expression, str):
            expression = safe_eval(expression, variables)
        action_context = action.get('context', {})
        if isinstance(action_context, str):
            action_context = safe_eval(action_context, variables)
        folder = action_context.get('searchpanel_default_folder_id')
        filters = [('type', '!=', 'folder')]
        if folder:
            filters.append(('folder_id', '=', folder))
        try:
            documents = scope[action['res_model']].search(AND([expression, filters]), order='id')
        except AccessError:
            results[task.id] = dict(count=task.document_count, denied=True)
            continue
        files = []
        for document in documents:
            assert document.res_model == task._name and document.res_id == task.id
            try:
                if document.type == 'url':
                    files.append([document.id, 'link', sha256(document.url.encode()).hexdigest()])
                    continue
                attachment = document.attachment_id
                raw = attachment.raw
            except AccessError:
                files.append([document.id, 'denied'])
            else:
                assert raw and len(raw) == attachment.file_size
                files.append([document.id, len(raw), sha256(raw).hexdigest()])
        results[task.id] = dict(count=task.document_count, files=files)
    return results


def run(env):
    assert __debug__ and env.cr.dbname in DATABASES
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    users = env['res.users'].search([('id', '!=', 1), ('active', '=', True)]) | env.ref('base.public_user')
    cases = []
    for user in users.sorted('id'):
        companies = dict.fromkeys([tuple(user.company_ids.ids), (user.company_id.id,), *((c.id,) for c in user.company_ids)])
        for active in companies:
            scope = env(user=user.id, su=False, context={'allowed_company_ids': list(active), 'active_test': False})
            models, menus, documents = {}, {}, {}
            for name, wanted in FIELDS.items():
                model = scope[name]
                result = {'acl': {mode: model.check_access_rights(mode, raise_exception=False)
                                  for mode in ('read', 'write', 'create', 'unlink')}}
                try:
                    ids = model.search([], order='id')
                    available = sorted(set(wanted) & model.fields_get(list(wanted)).keys())
                    values = ids.read(available, load=None)
                except AccessError:
                    result['read'] = False
                else:
                    result.update(read=True, rows=ids.ids, fields={
                        key: fingerprint([(row['id'], row[key]) for row in values]) for key in available
                    })
                    if (name == 'project.task' and 'document_count' in available
                            and scope.user.has_group('base.group_user')):
                        documents = linked_documents(scope, ids)
                models[name] = result
            try:
                visible = scope['ir.ui.menu']._visible_menu_ids()
            except AccessError:
                visible = set()
            for xmlid in MENUS:
                menu = scope.ref(xmlid)
                if menu.id not in visible:
                    menus[xmlid] = {'visible': False}
                    continue
                action = menu.action
                model = scope[action.res_model]
                wanted = [(key, kind) for key, kind in action.views if kind in ('list','kanban','graph','pivot','form','calendar')]
                rendered = model.get_views(wanted, {'toolbar': True})
                defs = rendered['models'][model._name]
                defs = defs.get('fields', defs)
                views = {}
                for kind, view in rendered['views'].items():
                    node = etree.fromstring(view['arch'])
                    names = sorted(set(node.xpath('//field[not(ancestor::field)]/@name')))
                    views[kind] = {'id': view['id'], 'fields': names, 'undefined': sorted(set(names)-defs.keys())}
                    if kind == 'form':
                        views[kind]['document_buttons'] = node.xpath('//field[@name="document_count"]/ancestor::button[1]/@name')
                menus[xmlid] = {'visible': True, 'action': action.id, 'model': model._name, 'views': views}
            cases.append({'actor': user.id, 'companies': active, 'models': models, 'menus': menus, 'linked_documents': documents})
    env.cr.rollback()
    return {'database': env.cr.dbname, 'cases': cases}
