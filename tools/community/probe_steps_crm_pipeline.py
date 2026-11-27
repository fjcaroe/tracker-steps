"""Open and exercise the original Steps sales pipeline with its existing non-admin salesperson."""
from hashlib import sha256
import json
import re
import traceback
from uuid import uuid4

from lxml import etree
from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval


def digest(rows):
    return sha256(json.dumps(rows, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def run(env):
    if not __debug__ or not re.fullmatch(r'(?:COMMUNITY|MANAGEMENT_QA)_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Use a dedicated Steps CRM restore.')
    leads = env['crm.lead'].with_user(7).with_context(allowed_company_ids=[1], tracking_disable=True,
        mail_create_nosubscribe=True, mail_notrack=True, mail_notify_force_send=False)
    actor = leads.env
    assert not actor.su and not actor.user.has_group('base.group_system')
    assert actor.company.id == 1 and actor.user.has_group('sales_team.group_sale_salesman')
    result = {'database': env.cr.dbname, 'uid': actor.uid, 'phase': 'menu'}
    try:
        with env.cr.savepoint() as trial:
            action = actor.ref('crm.crm_lead_action_pipeline')
            menus = actor['ir.ui.menu']
            visible = menus._visible_menu_ids()
            paths = menus.search([('action', '=', f'{action._name},{action.id}')]).filtered(lambda m: m.id in visible)
            assert paths
            action_values = actor['ir.actions.actions']._for_xml_id('crm.crm_lead_action_pipeline')
            assert action_values['id'] == action.id and action_values['res_model'] == 'crm.lead'
            action_context = safe_eval(action_values.get('context') or '{}',
                dict(uid=actor.uid, user=actor.user, context=actor.context, allowed_company_ids=[1],
                     active_id=False, active_ids=[], active_model=False))
            leads = leads.with_context(**action_context)
            result.update(action=action.id, menus=sorted(paths.ids), phase='form')
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
            original = mine.filtered(lambda r: r.partner_id and r.active)[:1]
            if not original:
                original = accessible.filtered(lambda r: r.partner_id and r.active)[:1]
            assert original and original.partner_id in contacts
            data, = original.web_read({k: {} for k in ('id','name','stage_id','partner_id','user_id','company_id')})
            result['original_relationships'] = digest(data)
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
        message = str(exc)
        result['technical_names'] = sorted(set(re.findall(
            r"(?:[Mm]odel |[Ff]ield |[Cc]ampo |[Mm]odelo |[Cc]olumn )['\"]([a-z_][a-z0-9_.]{0,100})['\"]", message)))
        if isinstance(exc, KeyError) and len(exc.args)==1 and re.fullmatch(r'[a-z_][a-z0-9_.]+',str(exc.args[0])):
            result['missing'] = exc.args[0]
    finally:
        env.cr.rollback()
        env.invalidate_all(flush=False)
    return result
