"""Compose the complete free freight application with Cerro's original directory fields at its first registration."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

PINNED = {
    'step_operations_ui/models/freight.py':'0d4f8d04c3cfba4dd93edbedff7a5cd5eaef6f7edf2f3c9e703ea49fd81b1309',
    'step_operations_ui/models/__init__.py':'d961fda33f0f60d9e3a1ce45574138b9d030543c9c30d59bfa5fea509cfa078c',
    'step_operations_ui/__manifest__.py':'371ef300491ac40927fe143a958c50931b888e8e6942539c883a6d0984d805e0',
    'step_packing_ticket_revision/dispatch_type.py':'11eb3d06d8638e7803d5742a2b1e0120d64e13113f8a0aa3399184b24da84edb',
    'step_packing_interplant/dispatch.py':'1273c839a390d2ef85015a61ec18cc7fceecf8e56f2555b4ff643ac17b2be2bd',
}


def fragment(source,name):
    node, = [n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name==name]
    return ast.get_source_segment(source,node)


def derive(source,output):
    data={}
    for filename,digest in PINNED.items():
        content=(source/filename).read_text(encoding='utf8')
        if hashlib.sha256(content.encode()).hexdigest()!=digest:
            raise ValueError('The original freight declaration changed: '+filename)
        data[filename]=content
    for module in ('step_operations_ui','step_packing_ticket_revision','step_packing_interplant'):
        spec=ast.literal_eval((source/module/'__manifest__.py').read_text(encoding='utf8'))
        assert spec['license'] in ('AGPL-3','LGPL-3')
    directory=fragment(data['step_packing_ticket_revision/dispatch_type.py'],'FreightDispatchType')
    original="""self.env['step.dispatch.guide'].sudo().search_count([
                    ('dispatch_type_id', '=', record.id), ('company_id', 'not in', record.company_ids.ids),
            ], limit=1)"""
    assert directory.count(original)==1
    directory=directory.replace(original,'record._step_has_guide_outside_companies()')
    directory+="""

    def _step_has_guide_outside_companies(self):
        self.ensure_one()
        if 'step.dispatch.guide' in self.env:
            return self.env['step.dispatch.guide'].sudo().search_count([
                ('dispatch_type_id','=',self.id),('company_id','not in',self.company_ids.ids)],limit=1)
        # The fiscal application can be absent in the private Community cohort.
        # Enforce the same original company restriction on its stored guides.
        self.env.cr.execute("SELECT to_regclass('public.step_dispatch_guide')")
        if not self.env.cr.fetchone()[0]:
            return False
        self.env.cr.execute('''SELECT EXISTS (SELECT FROM step_dispatch_guide WHERE dispatch_type_id=%s
                               AND (company_id IS NULL OR company_id<>ALL(%s::integer[])))''',
                            (self.id,self.company_ids.ids))
        return self.env.cr.fetchone()[0]
"""
    directory+="\n    def _load_records_write(self, values):\n        owner=self.env.context.get('install_module')\n        name=self.env.context.get('install_xmlid','').split('.')[-1]\n        seeds={'freight_dispatch_type_retira_cliente','freight_dispatch_type_despacho_cliente',\n               'freight_dispatch_type_despacho_tercero'}\n        if owner=='step_operations_ui' and name in seeds and values.keys()=={'name','paga_flete'}:\n            frozen=self.env['ir.model.data'].search_count([('module','=',owner),('name','=',name),\n                ('model','=',self._name),('res_id','=',self.id),('noupdate','=',True)],limit=1)\n            if frozen:\n                return\n        return super()._load_records_write(values)\n"
    recipient=fragment(data['step_packing_interplant/dispatch.py'],'DispatchType')
    text='from odoo import _,api,fields,models\nfrom odoo.exceptions import AccessError,ValidationError\n\n\n'
    text+=directory+'\n\n\n'+recipient+'\n'
    ast.parse(text)
    shutil.copytree(source/'step_operations_ui',output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (output/'models/step_cerro_directory.py').write_text(text,encoding='utf8',newline='\n')
    init=data['step_operations_ui/models/__init__.py'].rstrip()+'\nfrom . import step_cerro_directory\n'
    (output/'models/__init__.py').write_text(init,encoding='utf8',newline='\n')
    manifest=data['step_operations_ui/__manifest__.py'].replace('18.0.2.7.3','18.0.2.7.5')
    manifest=manifest.replace('"LGPL-3"','"AGPL-3"')
    # The free canonical fleet and machinery providers now own the former agricultural fields.
    # Tracker has separate payroll wizards and supplies no API or menu used by this application.
    manifest=manifest.replace('"step_hr",','"step_agriculture_core", "step_operations_core",')
    assert 'step_hr' not in ast.literal_eval(manifest)['depends'] and {'step_machinery','step_mobilization'}<=set(ast.literal_eval(manifest)['depends'])
    assert ast.literal_eval(manifest)['version']=='18.0.2.7.5' and ast.literal_eval(manifest)['license']=='AGPL-3'
    (output/'__manifest__.py').write_text(manifest,encoding='utf8',newline='\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    derive(args.source,args.output)
