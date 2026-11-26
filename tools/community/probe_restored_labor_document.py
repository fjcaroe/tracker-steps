"""Exercise the private native SyS labor-document workflow without exposing the document."""
import base64
import hashlib
import json
import re
from pathlib import Path
from datetime import date

from lxml import etree
from psycopg2 import IntegrityError
from werkzeug.test import EnvironBuilder
from odoo import Command, http
from odoo.addons.web.controllers.binary import Binary
from odoo.exceptions import AccessError, UserError


def probe(env):
    community = env.cr.dbname.startswith('COMMUNITY_LABOR_FLOW_')
    assert re.fullmatch(r'(MANAGEMENT_QA_SYS_LABOR_DOC_|COMMUNITY_LABOR_FLOW_)[A-Z0-9_]{1,30}', env.cr.dbname)
    interfaces = Path('/proc/net/dev').read_text().splitlines()[2:]
    assert {row.split(':')[0].strip() for row in interfaces} == {'lo'}
    module = 'step_hr_contract_lifecycle.'
    if community:
        assert not env['ir.module.module'].search_count([('state', '=', 'installed'), ('license', '=', 'OEEL-1')])
        user = env.ref('base.user_admin')
        user.write({'groups_id': [Command.link(env.ref(group).id) for group in (
            'hr_contract.group_hr_contract_manager', 'payroll.group_payroll_manager', module + 'group_contract_management_issue',
            module + 'group_labor_template_config', module + 'group_contract_management_view')]})
        company = user.company_id
        users = user
    else:
        company = env['res.company'].browse(7)
        users = env['res.users'].browse([6, 2])
    oca = 'sign_oca_request_id' in env['hr.labor.document']._fields
    mapped_original_user = False
    if oca and not community and not users[0].has_group('sign_oca.sign_oca_group_user'):
        assert users[0].has_group('sign.group_sign_user')
        users[0].write({'groups_id': [Command.link(env.ref('sign_oca.sign_oca_group_user').id)]})
        mapped_original_user = True
    user = next(u for u in users if company in u.company_ids and
                (not oca or u.has_group('sign_oca.sign_oca_group_user')))
    scope = env(user=user.id, su=False, context={
        'allowed_company_ids': [company.id], 'mail_notify_force_send': False,
        'tracking_disable': not mapped_original_user, 'mail_create_nosubscribe': not mapped_original_user, 'bin_size': False,
    })
    assert not scope.su and scope.user.has_group(module + 'group_contract_management_issue')
    Document = scope['hr.labor.document']
    Wizard = scope['hr.contract.mass.print']
    menus = scope['ir.ui.menu']._visible_menu_ids()
    menu = scope.ref(module + 'menu_hr_labor_document')
    issue_menu = scope.ref(module + 'menu_hr_contract_mass_print')
    assert menu.id in menus and issue_menu.id in menus
    assert menu.action.res_model == Document._name and issue_menu.action.res_model == Wizard._name
    for model, view_id, field in ((Document, 'view_hr_labor_document_form', 'pdf_attachment_id'),
                                  (Wizard, 'view_hr_contract_mass_print_form', 'contract_ids')):
        view = model.get_view(view_id=scope.ref(module + view_id).id, view_type='form')
        assert etree.fromstring(view['arch'].encode()).xpath(f'//field[@name="{field}"]')
    if community:
        employee = scope['hr.employee'].create({'name': 'Trabajador de ensayo', 'company_id': company.id,
                                                 'lang': scope.user.lang})
        location = scope['hr.work.location'].create({'name': 'Predio de ensayo', 'company_id': company.id,
                                                       'address_id': company.partner_id.id})
        scope['hr.contract'].create({'name': 'Contrato de ensayo', 'employee_id': employee.id,
                                     'company_id': company.id, 'resource_calendar_id': company.resource_calendar_id.id,
                                     'wage': 1000, 'date_start': date.today(), 'state': 'open', 'work_location_id': location.id})
        template = scope['hr.labor.template'].create({'name': 'Plantilla de ensayo', 'company_id': company.id,
            'document_type': 'contract', 'date_from': date.today(), 'modality': 'plazo_fijo', 'lang': scope.user.lang,
            'body_html': '<p>{{trabajador.nombre}} / {{contrato.fundo}}</p>'})
        template.action_validate()
    template = scope['hr.labor.template'].search([
        ('company_id', '=', company.id), ('state', '=', 'validated'), ('document_type', '=', 'contract'),
    ], order='id', limit=1)
    assert template
    contracts = scope['hr.contract']
    eligible = [('company_id', '=', company.id), ('state', '=', 'open')]
    matching = eligible + ([('labor_modality', '=', template.modality)] if template.modality else [])
    contract = contracts.search(matching + [('labor_template_id', '=', template.id)], limit=1)
    original_link = bool(contract)
    original_modality = True
    if not contract:
        contract = contracts.search(matching, order='id', limit=1)
        if not contract:
            contract = contracts.search(eligible + [('labor_modality', '=', False)], order='id', limit=1)
            assert contract and template.modality
            contract.labor_modality = template.modality
            original_modality = False
        assert contract
        contract.labor_template_id = template
    assert contract.company_id == company and contract.employee_id
    assert Document.search_count([]) == 0
    wizard = Wizard.create({'contract_ids': [Command.link(contract.id)]})
    action = wizard.action_print()
    doc = wizard.generated_document_ids
    doc.ensure_one()
    assert action['res_model'] == Document._name and Document.search(action['domain']) == doc
    assert Document.search(contract.action_view_documents()['domain']) == doc
    assert doc.state == 'generated' and doc.generated_by == scope.user and doc.generated_date
    assert (doc.template_id, doc.template_version) == (template, template.version)
    assert (doc.contract_id, doc.employee_id, doc.company_id) == (contract, contract.employee_id, company)
    assert contract.document_state == 'generated' and doc.rendered_body_html
    if community:
        assert location.name in doc.rendered_body_html and employee.name in doc.rendered_body_html
    attachment = doc.pdf_attachment_id
    attachment.check_access('read')
    assert (attachment.res_model, attachment.res_id) == (doc._name, doc.id)
    raw = attachment.raw
    assert raw.startswith(b'%PDF-') and b'%%EOF' in raw[-128:]
    assert hashlib.sha256(raw).hexdigest() == doc.pdf_hash
    assert len(raw) == attachment.file_size and hashlib.sha1(raw).hexdigest() == attachment.checksum
    download_tested = hasattr(doc, 'action_open_pdf')
    if download_tested:
        action = doc.action_open_pdf()
        assert action == {'type': 'ir.actions.act_url', 'url': f'/web/content/{attachment.id}?download=true',
                          'target': 'download'}
        builder = EnvironBuilder(path=action['url'].split('?')[0], query_string={'download': 'true'})
        try:
            request = http.Request(http.HTTPRequest(builder.get_environ()))
            request.db = env.cr.dbname
            request.env = scope
            request.params = {'download': 'true'}
            http._request_stack.push(request)
            try:
                response = Binary().content_common(id=attachment.id, download='true')
                assert response.status_code == 200 and response.mimetype == 'application/pdf'
                response.direct_passthrough = False
                assert response.get_data() == raw
                response.close()
            finally:
                http._request_stack.pop()
        finally:
            builder.close()
        menu_form = Document.get_view(view_id=scope.ref(module + 'view_hr_labor_document_form').id, view_type='form')
        arch = etree.fromstring(menu_form['arch'].encode())
        assert arch.xpath('//button[@name="action_open_pdf"]')
        assert arch.xpath('//field[@name="cancel_reason" and not(ancestor::*[@invisible])]')
        try:
            doc.with_user(scope.ref('base.public_user')).action_open_pdf()
        except AccessError:
            pass
        else:
            raise AssertionError('public user must not open a private labor document')
    for record in (contract, contract.employee_id):
        assert scope['mail.message'].search_count([
            ('model', '=', record._name), ('res_id', '=', record.id),
            ('attachment_ids', 'in', attachment.ids),
        ]) == 1
    if not community:
        assert scope['sign.request']._fields['template_id'].required
        env.cr.execute('SELECT count(*) FROM sign_request')
        assert env.cr.fetchone()[0] == 0
    sign_rejection = None
    if oca:
        oca_action = doc.action_send_to_sign()
        request = doc.sign_oca_request_id
        assert request.state == '1_draft' and request.record_ref == doc and not request.signer_ids
        assert request.company_id == company and base64.b64decode(request.data) == raw
        assert oca_action['res_model'] == request._name and oca_action['res_id'] == request.id
        assert doc.action_send_to_sign()['res_id'] == request.id
        assert scope['sign.oca.request'].search_count([('record_ref', '=', f'{doc._name},{doc.id}')]) == 1
    else:
        try:
            with env.cr.savepoint():
                doc.action_send_to_sign()
                env.flush_all()
        except (UserError, IntegrityError) as exc:
            sign_rejection = type(exc).__name__
            if isinstance(exc, IntegrityError):
                assert exc.diag.table_name == 'sign_request' and exc.diag.column_name == 'template_id'
        else:
            raise AssertionError('inspect newly accepted provider path before repeating')
    assert doc.state == 'generated' and not doc.sign_reference
    if not community:
        env.cr.execute('SELECT count(*) FROM sign_request')
        assert env.cr.fetchone()[0] == 0
    try:
        with env.cr.savepoint():
            doc.action_cancel()
    except UserError:
        pass
    else:
        raise AssertionError('cancellation accepted without a reason')
    assert doc.state == 'generated'
    doc.cancel_reason = 'Ensayo de reversión en copia privada'
    doc.action_cancel()
    assert doc.state == 'cancelled' and doc.pdf_hash == hashlib.sha256(raw).hexdigest()
    if oca:
        assert request.state == '3_cancel' and doc.sign_oca_state == '3_cancel'
    scope.flush_all()
    env.cr.rollback()
    if mapped_original_user:
        assert not users[0].has_group('sign_oca.sign_oca_group_user')
    print('LABOR_DOCUMENT_NATIVE=' + json.dumps({
        'uid': user.id, 'community_fixture': community, 'menu_and_forms': True, 'original_template_assignment': original_link,
        'original_labor_modality': original_modality,
        'bulk_wizard': True, 'contract_history': True, 'employee_history': True,
        'original_pdf_and_digest': True, 'pdf_bytes': len(raw), 'cancellation': True,
        'authenticated_download_and_public_denial_tested': download_tested,
        'existing_send_rejected_as': sign_rejection, 'no_enterprise_request_created': True,
        'oca_draft_opened_twice_and_cancelled': oca,
        'oca_user_assigned_temporarily_from_original_sign_role': mapped_original_user,
        'rolled_back': True,
    }))


if 'env' in globals():
    probe(env)
