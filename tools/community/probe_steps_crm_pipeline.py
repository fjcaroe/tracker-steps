"""Open and exercise the original Steps sales pipeline with its existing non-admin salesperson."""
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import traceback
from uuid import uuid4

from lxml import etree
from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval
from odoo.modules.module import get_manifest, get_module_path



def digest(rows):
    return sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def verify_providers(env):
    from prepare_steps_crm_cohort import FREE, RUNTIME, SOURCE_MANIFESTS
    if not re.fullmatch(r'COMMUNITY_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Use the private Steps Community CRM restore.')
    modules = env['ir.module.module'].search([('state', '=', 'installed')])
    runtime = RUNTIME.resolve(strict=True)
    checks = {}
    for module in modules:
        path = Path(get_module_path(module.name)).resolve(strict=True)
        actual = Path(sys.modules['odoo.addons.' + module.name].__file__).resolve(strict=True)
        assert path.is_relative_to(runtime) and actual.parent == path
        manifest = get_manifest(module.name)
        assert manifest['license'] == module.license and module.license in FREE
        assert manifest['version'] == module.latest_version
        checks[module.name] = sha256((path / '__manifest__.py').read_bytes()).hexdigest()
    assert len(checks) == 157 and digest(checks) == SOURCE_MANIFESTS
    return {'active': len(checks), 'official_manifest_digest': digest(checks)}


def form_specification(compiled):
    models = {model: value['fields'] for model, value in compiled['models'].items()}
    root = etree.fromstring(compiled['views']['form']['arch'].encode())
    fields = {'id': {}}
    for element in root.xpath('.//field[@name]'):
        model, group = 'crm.lead', fields
        for node in [*reversed(list(element.iterancestors('field'))), element]:
            name = node.get('name')
            description = models[model][name]
            request = group.setdefault(name, {})
            if node is not element:
                group = request.setdefault('fields', {})
                if description['type'] in ('one2many', 'many2many'):
                    request.setdefault('limit', 20)
                model = description['relation']
            elif description['type'] == 'many2one':
                request.setdefault('fields', {'display_name': {}})
    return fields


def run(env, *, inspect_only=False):
    if not __debug__ or (env.cr.dbname != 'COMMUNITY_STEPS_EXPENSE_20261127U50E' and not re.fullmatch(r'(?:COMMUNITY|MANAGEMENT_QA)_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname)):
        raise ValueError('Use a dedicated Steps CRM restore.')
    if inspect_only:
        env.cr.execute('SHOW transaction_read_only')
        assert env.cr.fetchone() == ('on',)
    leads = env['crm.lead'].with_user(7).with_context(allowed_company_ids=[1], tracking_disable=True,
        mail_create_nosubscribe=True, mail_notrack=True, mail_notify_force_send=False)
    actor = leads.env
    assert not actor.su and not actor.user.has_group('base.group_system')
    assert actor.company.id == 1 and actor.user.has_group('sales_team.group_sale_salesman')
    result = {'database': env.cr.dbname, 'uid': actor.uid, 'phase': 'menu'}
    try:
        with env.cr.savepoint() as trial:
            menus = actor['ir.ui.menu']
            visible = menus._visible_menu_ids()
            menu = actor.ref('crm.menu_crm_opportunities')
            server_action = actor.ref('crm.action_your_pipeline')
            assert menu.id in visible and menu.action == server_action
            action_values = server_action.run()
            action = actor.ref('crm.crm_lead_action_pipeline')
            assert action_values['id'] == action.id and action_values['res_model'] == 'crm.lead'
            action_context = action_values.get('context') or {}
            if isinstance(action_context, str):
                action_context = safe_eval(action_context, dict(uid=actor.uid, user=actor.user, context=actor.context,
                    allowed_company_ids=[1], active_id=False, active_ids=[], active_model=False))
            leads = leads.with_context(**action_context)
            result.update(action=action.id, server_action=server_action.id, menu=menu.id, phase='form')
            view = actor.ref('crm.crm_lead_view_form')
            form_id = next((ident for ident, kind in action_values['views'] if kind == 'form'), False)
            form = leads.get_view(view_id=form_id, view_type='form')
            assert form['id'] == view.id
            fields = etree.fromstring(form['arch'].encode()).xpath('//field/@name')
            assert {'name', 'partner_id', 'stage_id', 'user_id'} <= set(fields)
            result.update(view=view.id, form_fields=len(set(fields)), phase='visibility')
            accessible = leads.with_context(active_test=False).search([], order='id')
            mine = accessible.filtered(lambda r: r.user_id == actor.user)
            assert mine and accessible
            result['visible_leads'] = [len(accessible), digest(accessible.ids)]
            result['owned_leads'] = [len(mine), digest(mine.ids)]
            contacts = actor['res.partner'].with_context(active_test=False).search([], order='id')
            result['visible_contacts'] = [len(contacts), digest(contacts.ids)]
            result['phase'] = 'full_form_read'
            compiled = leads.get_views([(form_id, 'form')], options={'action_id': action.id})
            specification = form_specification(compiled)
            values = mine.web_read(specification)
            assert [row['id'] for row in values] == mine.ids
            result['full_form'] = {'records': len(values), 'fields': len(specification),
                'schema': digest(specification), 'values': digest(values),
                'field_digests': {name: digest([row[name] for row in values]) for name in specification}}
            original = mine.filtered(lambda r: r.partner_id and r.active)[:1]
            if not original:
                original = accessible.filtered(lambda r: r.partner_id and r.active)[:1]
            assert original and original.partner_id in contacts
            data, = original.web_read({k: {} for k in ('id','name','stage_id','partner_id','user_id','company_id')})
            result['original_relationships'] = digest(data)
            if inspect_only:
                result['phase'] = 'inspected'
                return result
            result['phase'] = 'create'
            form = Form(leads.with_context(default_type='opportunity'), view=view)
            tag = 'STEPS_CRM_TEST_' + uuid4().hex
            form.name = tag
            form.partner_id = original.partner_id
            record = form.save()
            assert record.id not in accessible.ids and record.partner_id == original.partner_id
            assert record.type == 'opportunity' and record.user_id == actor.user
            result['phase'] = 'advance'
            stages = actor['crm.stage'].search([('id', '!=', record.stage_id.id),
                ('team_id', 'in', [False, record.team_id.id]), ('is_won', '=', False)], order='sequence,id')
            assert stages
            with Form(record, view=view) as updated:
                updated.stage_id = stages[0]
            result['selected_stage'] = stages[0].id
            assert record.stage_id == stages[0]
            record.action_set_won_rainbowman()
            assert record.stage_id.is_won and record.probability == 100
            result['won_stage'] = record.stage_id.id
            trial.rollback()
            result['phase'] = 'rolled_back'
            assert not leads.search_count([('name','=',tag)])
    except Exception as exc:
        frame = traceback.extract_tb(exc.__traceback__)[-1]
        result['error'] = type(exc).__name__
        result['method'] = frame.name
        result['origin'] = '/'.join(frame.filename.replace('\\', '/').split('/')[-3:])
        result['line'] = frame.lineno
        message = str(exc)
        result['technical_names'] = sorted(set(re.findall(
            r"(?:[Mm]odel |[Ff]ield |[Cc]ampo |[Mm]odelo |[Cc]olumn )['\"]([a-z_][a-z0-9_.]{0,100})['\"]", message)))
        if isinstance(exc, KeyError) and len(exc.args)==1 and re.fullmatch(r'[a-z_][a-z0-9_.]+',str(exc.args[0])):
            result['missing'] = exc.args[0]
    finally:
        env.cr.rollback()
        env.invalidate_all(flush=False)
    return result
