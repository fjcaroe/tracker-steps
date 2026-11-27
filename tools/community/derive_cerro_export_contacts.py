"""Compose the historical Cerro contact directory from the free native suppliers."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

SOURCE = {
    'step_export/models/step_export_master_extensions.py': 'ed202372b7f6b6805fafb70acdcf3f3bcb552da6ca5f570c6b0780d86dc7918a',
    'step_export_receiver_profile/models.py': '4426cf3881ab905b1cca3b9e5bc1581e32fd9d53a0123bc0babc07e60b17920a',
    'step_export_client_revision/models/revision.py': 'c4b37dc632c1b625d8d9361dab7e3a537a332cb2625aec20dfdf4fda12ac869d',
    'step_producer_daily_estimate/models/daily.py': 'c822df7bff5111f7579f5ef717732e9714a7e0ff8f9307ebdf97b5c098d29115',
    'step_cerro_studio_exports/views/customizations.xml': '393f75ca632c957812178958b2378827a690a035924aa0aa532d708c613ae2a9',
}


def part(source, original, new=None):
    node, = [node for node in ast.parse(source).body if isinstance(node, ast.ClassDef) and node.name == original]
    code = ast.get_source_segment(source, node)
    return code.replace('class ' + original + '(', 'class ' + (new or original) + '(', 1)


def derive(source, output):
    contents = {}
    for name, expected in SOURCE.items():
        contents[name] = (source / name).read_text(encoding='utf8')
        if hashlib.sha256(contents[name].encode()).hexdigest() != expected:
            raise ValueError('Source changed for ' + name)
        manifest = source / name.split('/')[0] / '__manifest__.py'
        if ast.literal_eval(manifest.read_text(encoding='utf8'))['license'] != 'LGPL-3':
            raise ValueError('Unqualified licensing for ' + name)
    core, receiver, roles, markets, xml = contents.values()
    role_map, = [n for n in ast.parse(roles).body if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'ROLES']
    code = 'from odoo import _, api, fields, models\nfrom odoo.exceptions import ValidationError\n\n\n'
    code += ast.get_source_segment(roles,role_map) + '\n\n\n'
    code += '\n\n\n'.join((part(markets,'Market'),part(core,'ResPartner'),
                               part(roles,'Partner','ExportPartnerRoles'),part(receiver,'Partner','ReceiverProfile'))) + '\n'
    ast.parse(code)
    views = ET.fromstring(xml)
    child, = [v for v in views if v.attrib['id'] == 'export_partners']
    only = ET.Element('odoo')
    only.append(child)
    output.mkdir(parents=True,exist_ok=False)
    template = Path(__file__).with_name('cerro_export_contacts_template')
    for file in ('__init__.py','__manifest__.py','hooks.py'):
        shutil.copy2(template / file, output / file)
    (output / 'models.py').write_text(code,encoding='utf8',newline='\n')
    (output / 'views').mkdir()
    ET.ElementTree(only).write(output/'views/customizations.xml',encoding='utf-8',xml_declaration=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    derive(args.source,args.output)
