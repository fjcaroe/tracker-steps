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
            for node in ast.walk(tree):
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
