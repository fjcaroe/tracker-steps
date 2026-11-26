"""Apply the reviewed Steps QWeb template on private SyS without replaying AGPL seeds."""

from hashlib import sha256
from io import BytesIO
import re

from lxml import etree
from odoo.tools import file_open
from odoo.tools.convert import convert_xml_import


VIEW = 'step_simpledigital_oca_base.report_payslip'
SOURCE_SHA = '895aae7587abcfe714575e3e3bee20f056de3d3cb9c41f672f070f2a1dbe2a0a'
PREVIOUS = 'a0e62f2abf600aad5638d5f0a9ab11268139b9ad52dbcc12373f002378dd7841'
ACCEPTED = '5eb9344a17a712b019f8bfa4d1c78897d9b8db89cf659b72b203174ec45abefd'


def fingerprint(env, ident):
    env.cr.execute('SELECT arch_db FROM ir_ui_view WHERE id=%s FOR UPDATE', (ident,))
    arch, = env.cr.fetchone()
    if set(arch) != {'en_US'}:
        raise ValueError('Review existing translated payroll templates before updating this view')
    return sha256(arch['en_US'].encode()).hexdigest()


def run(env):
    if not re.fullmatch(r'COMMUNITY_SYS_STORED_REPORT_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('A private restored SyS report database is required')
    if env['ir.module.module'].search_count([('name', '=', 'step_payroll_oca_sys_history'), ('state', '=', 'installed')]) != 1:
        raise ValueError('The real SyS payroll provider must already be installed')
    action = env.ref('hr_payroll.action_report_payslip')
    view = env.ref(VIEW)
    if (action.report_name != 'hr_payroll.report_payslip_lang' or action.model != 'hr.payslip'
            or view.key != VIEW or view.mode != 'primary' or view.inherit_id != env.ref('payroll.report_payslip')):
        raise ValueError('Expected the original report action and existing Steps primary QWeb template')
    with env.cr.savepoint():
        before = fingerprint(env, view.id)
        if before == ACCEPTED:
            return {'updated': False, 'view_id': view.id, 'action_id': action.id, 'template_sha256': before}
        if before != PREVIOUS:
            raise ValueError('Existing Steps template differs from the reviewed SyS source')
        with file_open('step_simpledigital_oca_base/views/compatibility.xml', 'rb') as stream:
            source = stream.read().replace(b'\r\n', b'\n')
        if sha256(source).hexdigest() != SOURCE_SHA:
            raise ValueError('Expected the reviewed Community template source')
        tree = etree.fromstring(source)
        template, = tree.xpath('./template[@id="report_payslip" and @inherit_id="payroll.report_payslip"]')
        xml = etree.Element('odoo')
        xml.append(template)
        extracted = BytesIO(etree.tostring(xml))
        extracted.name = 'step_simpledigital_oca_base/views/compatibility.xml'
        convert_xml_import(env, 'step_simpledigital_oca_base', extracted, mode='update')
        env.flush_all()
        after = fingerprint(env, view.id)
        if after != ACCEPTED or env.ref(VIEW) != view or env.ref('hr_payroll.action_report_payslip') != action:
            raise ValueError('The original identifiers and accepted QWeb architecture must survive the update')
        return {'updated': True, 'view_id': view.id, 'action_id': action.id, 'template_sha256': after}
