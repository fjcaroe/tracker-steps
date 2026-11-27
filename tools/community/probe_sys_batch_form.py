"""Create a new payroll batch through its original menu's default form."""
from datetime import date
import re
from uuid import uuid4

from lxml import etree
from odoo.tests import Form


def probe(env, company_id, uid):
    if not __debug__ or not re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', env.cr.dbname):
        raise RuntimeError('Use normal Python and a private SyS payroll restore.')
    runs = env['hr.payslip.run'].with_user(uid).with_context(allowed_company_ids=[company_id], tracking_disable=True)
    assert not runs.env.su and runs.env.company.id == company_id
    action = runs.env.ref('hr_payroll.action_hr_payslip_run_tree')
    menu = runs.env['ir.ui.menu'].search([('action', '=', '%s,%s' % (action._name, action.id))])
    assert menu and menu.id in runs.env['ir.ui.menu']._visible_menu_ids()
    view = runs.env.ref('hr_payroll.hr_payslip_run_form')
    rendered = runs.get_view(view_type='form')
    root = etree.fromstring(rendered['arch'].encode())
    assert rendered['id'] == view.id and not root.xpath('//field[@name="journal_id"]')
    assert all(n in runs._fields for n in root.xpath('//field/@name'))
    assert all(callable(getattr(runs, n, None)) for n in root.xpath('//button[@type="object"]/@name'))
    try:
        form = Form(runs, view=view)
        form.name = 'STEP_SYS_FORM_' + uuid4().hex
        form.date_start = date(2026, 10, 1)
        form.date_end = date(2026, 10, 31)
        batch = form.save()
        assert batch.company_id == runs.env.company and batch.state == 'draft' and not batch.slip_ids
        if 'journal_id' in runs._fields:
            configured = runs.env.ref('l10n_cl_simpledigital_payroll.structure_chile').journal_id
            assert batch.journal_id and batch.journal_id == configured and configured.company_id == runs.env.company
        return {'menu': menu.id, 'action': action.id, 'view': view.id, 'created_without_journal_input': True,
                'company': company_id, 'operator': uid}
    finally:
        env.cr.rollback()
