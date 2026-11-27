"""Read original Steps support tickets through each existing user's Odoo permissions."""
from hashlib import sha256
import json
from pathlib import Path
import re

from lxml import etree
from odoo.exceptions import AccessError
from odoo.tests import Form


FIELDS = ('name', 'description', 'active', 'ticket_ref', 'team_id', 'stage_id', 'user_id', 'partner_id',
          'company_id', 'priority', 'kanban_state', 'tag_ids', 'assign_date', 'close_date',
          'x_studio_accin_correctiva', 'x_studio_causas_del_ticket', 'x_studio_etapa_intermedia')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'),
                             default=str).encode()).hexdigest()


def ticket_trial(env):
    if not __debug__ or env.cr.dbname not in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C',
                                               'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H',
                                               'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H2'):
        raise ValueError('Use the private Steps ticket pair.')
    assert {line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    user = env['res.users'].browse(7)
    assert user.active and not user.share and not user.has_group('base.group_system')
    scope = env(user=user.id,su=False,context={'allowed_company_ids':[user.company_id.id],
                'mail_notify_force_send':False, 'mail_create_nosubscribe':True})
    tickets = scope['helpdesk.ticket']
    original = tickets.search([],order='id')
    sample = original.filtered(lambda row:row.team_id and row.partner_id and row.stage_id)[:1]
    assert sample and scope.ref('helpdesk.helpdesk_ticket_menu_all').id in scope['ir.ui.menu']._visible_menu_ids()
    menu = scope.ref('helpdesk.helpdesk_ticket_menu_all')
    action = scope['ir.actions.actions']._for_xml_id('step_helpdesk_tickets.action_all' if
                env.cr.dbname.startswith('COMMUNITY_') else 'helpdesk.helpdesk_ticket_action_main_tree')
    assert action['id'] == menu.action.id
    form_id = next((pk for pk,kind in action['views'] if kind=='form'),None)
    env.cr.execute("""SELECT id,padding,number_increment FROM ir_sequence WHERE code='helpdesk.ticket'
        AND implementation='standard' AND active AND company_id IS NULL AND prefix IS NULL AND suffix IS NULL""")
    (sequence, padding, increment), = env.cr.fetchall()
    sequence_name = 'ir_sequence_' + str(sequence).zfill(3)
    def current_number():
        env.cr.execute("SELECT last_value FROM pg_sequences WHERE schemaname='public' AND sequencename=%s",
                       (sequence_name,))
        return env.cr.fetchone()[0]
    previous = current_number()
    with env.cr.savepoint() as trial:
        form = Form(tickets,view=form_id)
        form.name = 'Ensayo privado de soporte'
        form.team_id, form.partner_id = sample.team_id, sample.partner_id
        row = form.save()
        assert row and row.stage_id and row.team_id==sample.team_id and row.partner_id==sample.partner_id
        first = row.stage_id
        target = original.filtered(lambda r:r.team_id==row.team_id and r.stage_id and r.stage_id!=first)[:1].stage_id
        assert target
        row.write({'stage_id':target.id})
        env.flush_all()
        row.invalidate_recordset()
        fields = ['id','stage_id','team_id','partner_id','ticket_ref','name']
        reopened, = row.web_read({name:{} for name in fields})
        assert row.stage_id==target and reopened['id']==row.id and reopened['name']=='Ensayo privado de soporte'
        assert row.ticket_ref
        current = current_number()
        assert current == previous + increment and row.ticket_ref == str(current).zfill(padding)
        result = {'action':action['id'],'user':scope.uid,'selected_existing_master_ids':
                  fingerprint([sample.team_id.id,sample.partner_id.id,first.id,target.id]),
                  'has_ticket_reference':True,'original_sequence':sequence,'sequence_advance':increment,
                  'reopened_in_new_stage':True}
        trial.rollback()
    assert tickets.search([],order='id') == original
    env.cr.rollback()
    return result


def run(env):
    if not __debug__ or not re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_STEPS_CRM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Use an isolated original Steps sales and support copy.')
    assert {line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    env.cr.execute('SELECT id FROM helpdesk_ticket ORDER BY id')
    tickets = [row[0] for row in env.cr.fetchall()]
    assert len(tickets) == 243
    env.cr.execute("""SELECT id FROM ir_attachment WHERE res_model='helpdesk.ticket' AND res_id=ANY(%s)
                      AND store_fname IS NOT NULL ORDER BY id""", (tickets,))
    linked_files = [row[0] for row in env.cr.fetchall()]
    env.cr.execute("SELECT count(*) FROM mail_message WHERE model='helpdesk.ticket' AND res_id=ANY(%s)", (tickets,))
    messages, = env.cr.fetchone()
    users = env['res.users'].with_context(active_test=False).search([('id','!=',1),('active','=',True)])
    users |= env.ref('base.public_user')
    menus = ('helpdesk.menu_helpdesk_root','helpdesk.helpdesk_ticket_menu_my','helpdesk.helpdesk_ticket_menu_all')
    result = []
    for user in users.sorted('id'):
        companies = user.company_ids
        scopes = dict.fromkeys([tuple(companies.ids),(user.company_id.id,),*((c.id,) for c in companies)])
        for ids in scopes:
            actor = env(user=user.id, su=False, context={'allowed_company_ids': list(ids), 'active_test': False})
            assert not actor.su
            model = actor['helpdesk.ticket']
            entry = {'actor':user.id, 'companies':list(ids), 'internal':user.has_group('base.group_user')}
            try:
                visible = actor['ir.ui.menu']._visible_menu_ids()
                entry['menus'] = [key for key in menus if actor.ref(key).id in visible]
            except AccessError:
                entry['menus'] = None
            entry['rights'] = {op:model.check_access_rights(op,raise_exception=False)
                               for op in ('read','write','create','unlink')}
            if not entry['rights']['read']:
                result.append(entry)
                continue
            rows = model.search([], order='id')
            readable = sorted(set(FIELDS) & model.fields_get(list(FIELDS)).keys())
            values = rows.read(readable, load=None)
            assert [r['id'] for r in values] == rows.ids and set(rows.ids) <= set(tickets)
            entry.update(tickets=len(rows), readable_fields=readable, identities=fingerprint(rows.ids),
                         values=fingerprint(values),default_order=fingerprint(model.search([]).ids))
            writable = [row.id for row in rows if row.has_access('write')]
            entry.update(writable=len(writable), writable_ids=fingerprint(writable))
            if entry['menus'] and 'helpdesk.helpdesk_ticket_menu_all' in entry['menus']:
                entry['master_order'] = {name:fingerprint(actor[name].search([]).ids)
                                         for name in ('helpdesk.tag','helpdesk.team','helpdesk.stage')}
                menu = actor.ref('helpdesk.helpdesk_ticket_menu_all')
                action = actor['ir.actions.actions']._for_xml_id('step_helpdesk_tickets.action_all' if
                          env.cr.dbname.startswith('COMMUNITY_') else 'helpdesk.helpdesk_ticket_action_main_tree')
                assert action['id'] == menu.action.id
                assert action['res_model'] == model._name
                view_id = next((pk for pk,kind in action['views'] if kind == 'form'), False)
                view = model.get_view(view_id=view_id or None, view_type='form')
                fields = sorted(set(etree.fromstring(view['arch'].encode()).xpath('.//field/@name')))
                assert {'name','team_id','stage_id'} <= set(fields)
                entry['form'] = {'id':view['id'], 'action':action['id'], 'fields':fields}
                if rows:
                    opened = rows[0].web_read({name:{} for name in readable})
                    assert len(opened)==1 and opened[0]['id']==rows[0].id
                    entry['first_web_ticket'] = fingerprint(opened)
            try:
                files = actor['ir.attachment'].with_context(bin_size=False).search([('id','in',linked_files)],order='id')
            except AccessError:
                entry['attachment_search'] = False
                result.append(entry)
                continue
            entry['attachment_search'] = True
            samples = []
            for file in files.filtered(lambda f: 0 < f.file_size <= 2_000_000)[:4]:
                raw = file.raw
                assert len(raw)==file.file_size
                samples.append([file.id, len(raw), sha256(raw).hexdigest()])
            entry.update(attachments=len(files), files=fingerprint(files.ids), samples=len(samples),
                         sample_bytes=fingerprint(samples))
            result.append(entry)
    env.cr.rollback()
    return {'tickets':len(tickets), 'linked_attachments':len(linked_files),'messages':messages,'permissions':result}
