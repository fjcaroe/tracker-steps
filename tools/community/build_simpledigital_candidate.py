"""Derive a private Community candidate from pinned AGPL provider runtime files.

Commercial documents, local settings, Git internals and testing data are excluded.
The actual provider remains named l10n_cl_simpledigital_payroll. No facade modules.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
from xml.etree import ElementTree as ET


XMLIDS = {
    'hr_payroll.group_hr_payroll_manager':'payroll.group_payroll_manager',
    'hr_payroll.view_hr_payslip_tree':'payroll.hr_payslip_view_tree',
    'hr_payroll.view_hr_payslip_form':'payroll.hr_payslip_view_form',
    'hr_payroll.payroll_hr_employee_view_form':'payroll.hr_employee_view_form',
    'hr_payroll.menu_hr_payroll_employees_root':'step_simpledigital_oca_base.payroll_employees',
    'hr_payroll.menu_hr_payroll_report':'step_simpledigital_oca_base.payroll_reports',
    'hr_work_entry_contract_enterprise.menu_hr_payroll_configuration':'payroll.payroll_menu_configuration',
    'hr_payroll.report_payslip':'step_simpledigital_oca_base.report_payslip',
    **{'hr_payroll.model_'+name:'payroll.model_'+name for name in (
        'hr_payslip','hr_payslip_worked_days','hr_payslip_input','hr_payslip_employees','hr_payslip_line')},
}


def adapt_payslip_report_xml(content):
    """Use the real AGPL layout with authorized stored-report values only."""
    tree = ET.fromstring(content)
    replacements = {
        "o.line_ids.filtered(lambda l: l.appears_on_payslip)": 'step_report_lines(o)',
        "o.worked_days_line_ids.filtered(lambda worked_days: worked_days.code != 'OUT')": 'step_report_days(o)',
        "sum(plines.filtered(lambda l: l.category_id.code == 'GROSS').mapped('total')) + sum(plines.filtered(lambda l: l.category_id.code == 'habIMP').mapped('total'))": "step_report_category_total(o, ['GROSS', 'habIMP'])",
        "sum(plines.filtered(lambda l: l.category_id.code == 'TOTAL_DESC').mapped('total'))": "step_report_category_total(o, ['TOTAL_DESC'])",
        'o.use_worked_day_lines': 'step_report_days(o)',
        'o.overtime_hours > 0': 'step_report_overtime_hours(o) is not None and step_report_overtime_hours(o) > 0',
        'round(o.overtime_hours, 2)': 'step_report_overtime_hours(o)',
        'o.net_wage': 'step_report_net(o)',
        'hl.total': 'step_report_total(hl)',
        'dl.total': 'step_report_total(dl)',
    }
    for key in ('hours', 'days'):
        original = 'number_of_' + key
        replacements['round(worked_days.' + original + ', 2)'] = (
            "round(step_report_day_value(worked_days, '%s'), 2) if step_report_day_value(worked_days, '%s') is not None else ''" % (key, key))
        replacements["round(sum(worked_days_lines.mapped('%s')), 2)" % original] = (
            "round(step_report_day_sum(o, '%s'), 2) if step_report_day_sum(o, '%s') is not None else ''" % (key, key))
    expected = {'plines': 0, 'worked_days_lines': 0}
    signatures = 0
    for node in tree.iter():
        if node.get('id') == 'signature_section':
            # Keep the original legal/signature block together in actual
            # wkhtmltopdf output; an orphaned name/RUN is not a usable signature.
            node.set('style', 'page-break-inside: avoid; break-inside: avoid;')
            signatures += 1
        for attr, original in list(node.attrib.items()):
            if not attr.startswith('t-'):
                continue
            value = replacements.get(original, original)
            for name in ('hl', 'dl', 'l'):
                value = value.replace(name + '.category_id.code', 'step_report_category(' + name + ')')
            if attr == 't-field' and value != original:
                node.attrib.pop(attr)
                node.set('t-out', value)
            elif attr == 't-esc':
                node.attrib.pop(attr)
                node.set('t-out', value)
            else:
                node.set(attr, value)
        if node.get('t-set') in expected:
            expected[node.get('t-set')] += 1
        if node.get('t-out') in ('step_report_total(hl)', 'step_report_total(dl)',
                                  'step_report_net(o)', 'total_haberes', 'total_descuentos'):
            node.set('t-if', node.get('t-out') + ' is not None')
    assert expected == {'plines': 1, 'worked_days_lines': 1}, 'Pinned provider report structure drift'
    assert signatures == 1, 'Pinned provider signature structure drift'
    result = ET.tostring(tree, encoding='unicode')
    assert 'o.net_wage' not in result and 'o.overtime_hours' not in result
    assert ".mapped('total')" not in result, 'Report must read authorized stored totals'
    forbidden = ('contract.wage', 'contract_id.wage', 'o.paid_amount', 'o.basic_wage',
                 'o.gross_wage', '_get_paid_amount', '_get_contract_wage')
    assert not any(value in result for value in forbidden), 'Current financial helpers are not historical report snapshots'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert str(args.output.resolve()).startswith('/opt/steps-validation/')
    pin=json.loads(Path(__file__).with_name('simpledigital_runtime_source.json').read_text(encoding='utf-8'))
    source=args.source.resolve();target=args.output/'l10n_cl_simpledigital_payroll'
    assert not target.exists()
    manifest=ast.literal_eval((source/'__manifest__.py').read_text(encoding='utf-8-sig'))
    assert manifest['license']==pin['license']=='AGPL-3' and manifest['version']==pin['version']
    assert all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in pin['files'].items()),'Provider runtime drift'
    target.mkdir(parents=True)
    changes=[]
    for name in pin['files']:
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if name=='__manifest__.py':continue
        shutil.copyfile(source/name,dest)
        if dest.suffix not in ('.xml','.py','.csv'):continue
        content=dest.read_text(encoding='utf-8-sig');before=content
        for old,new in XMLIDS.items():content=content.replace(old,new)
        if dest.suffix=='.xml':
            content=content.replace("@name='salary_computation'","@name='computation'")
            content=content.replace("@name='hr_payroll'","@name='payroll_settings'")
        if name in ('models/hr_contract.py','models/hr_employee.py'):
            tree=ast.parse(content)
            owners={id(node.value):node.targets[0].id for node in ast.walk(tree) if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)}
            for node in ast.walk(tree):
                if owners.get(id(node)) in ('income_tax_type','work_schedule_id'):continue
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='fields':
                    for keyword in node.keywords:
                        if keyword.arg=='required' and isinstance(keyword.value,ast.Constant) and keyword.value.value is True:
                            keyword.value=ast.Constant(False)
            content=ast.unparse(tree)+'\n'
        if name=='views/hr_employee.xml':
            tree=ET.fromstring(content)
            for record in tree.iter('record'):
                if record.get('id')=='view_employee_form_inherit_payslip_button':
                    for button in record.iter('button'):
                        if button.get('name')=='action_view_payslips':button.set('groups','hr.group_hr_user')
            content=ET.tostring(tree,encoding='unicode')
        if name=='data/hr_salary_structure.xml':
            tree=ET.fromstring(content)
            for record in tree.iter('record'):
                if record.get('id')=='structure_chile':
                    flag=ET.SubElement(record,'field',name='use_work_entries');flag.text='True'
            content=ET.tostring(tree,encoding='unicode')
        if name=='report/report_payslip_templates.xml':
            content=adapt_payslip_report_xml(content)
        if content!=before:
            dest.write_text(content,encoding='utf-8');changes.append(name)
    manifest['depends']=['step_simpledigital_oca_base']
    manifest['version']='18.0.1.1.0'
    (target/'__manifest__.py').write_text(repr(manifest)+'\n',encoding='utf-8')
    (args.output.parent/'provider-derivation.json').write_text(json.dumps({
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'license':'AGPL-3','author':manifest['author'],'source_files':pin['files'],
        'transformed_files':changes,'xmlid_map':XMLIDS,'community_compatible':False,
        'identity_conversion_accepted':False},indent=2),encoding='utf-8')
    print('SIMPLEDIGITAL_CANDIDATE_BUILT '+str(target))


if __name__=='__main__':main()
