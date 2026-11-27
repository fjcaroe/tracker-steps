"""Compose the inbound Cerro flow from the original, pinned free-software sources and the admitted reporting provider."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
REPORT = 'step_cerro_pack_reports'
OWNER = 'step_cerro_receipt_flow'
SOURCE_PINS = json.loads((HERE/'cerro_receipt_source_pins.json').read_text(encoding='utf8'))

WHOLE = {
    'settings':'step_inventory_packing/models/settings.py',
    'scale_profile':'step_inventory_packing/models/scale_profile.py',
    'fruit_reception':'step_inventory_packing/models/fruit_reception.py',
    'fruit_import':'step_inventory_packing/wizard/fruit_reception_import.py',
    'revision':'step_packing_reception_revision/models/reception.py',
    'simple':'step_packing_reception_revision/models/simple_reception.py',
}
PIECES = (
    ('tag', 'step_inventory_packing/models/fruit_package.py', {
        'StockQuantPackage': ('_onchange_step_producer','_check_step_tag','action_step_validate_tag'),
        'StepFruitPackageLine': ('uom_id','boxes','_sql_constraints','create','write','unlink')}),
    ('lot','step_packing_operations/models/process_control.py', {'FruitPackageLine':('lot_id','_check_lot')}),
    ('caliber','step_packing_operations/models/contract_valuation.py', {'FruitCaliber':('step_contract_caliber_id',)}),
    ('order_tags','step_packing_operations/models/production.py', {'PackingProduction':('step_packing_input_tag_ids',)}),
    ('season','step_export/models/step_export_forecast.py', {'ForecastFruitTag':('step_export_season_id',)}),
    ('report_packing','step_packing_ticket_revision/models.py', {
        'Picking':('step_receiving_packing_id','step_reception_product_ids','step_reception_packaging_ids',
                  'step_reception_container_qty','step_reception_net_kg','step_reception_avg_kg','_compute_step_reception_summary'),
        'TagLine':('step_fruit_gassed','step_fruit_chilled','step_fruit_palletized','step_legacy_kg_per_box'),
        'Package':('step_reception_tag_line_ids','step_packing_partner_id','_compute_report_packing')}),
    ('reversal','step_packing_reception_revision/models/receipt_reversal.py',{
        'Picking':('step_fruit_reversal_id','step_fruit_correction_of_id','step_fruit_reversal_reason','create','write')}),
    ('correction','step_packing_reception_revision/models/product_correction.py',{
        'ReceiptLine':('_rec_name','step_product_correction_move_ids','_matching_reception_moves','write'),
        'Move':('step_receipt_correction_line_id','step_receipt_correction_id','step_receipt_correction_direction','step_receipt_correction_reason','create','write')}),
    ('containers','step_inventory_packing/models/harvest_container.py',{
        'ProductTemplate':('step_is_harvest_container',),
        'HarvestContainerTransfer':('name','state','direction','company_id','producer_id','fruit_picking_id','warehouse_id','line_ids','picking_id','create','write','unlink'),
        'HarvestContainerTransferLine':('transfer_id','product_id','quantity','uom_id','_check_quantity','create','write','unlink'),
        'StockPicking':('step_container_transfer_ids','action_step_container_return')}),
    ('container_controls','step_harvest_container_control/models/control.py',{
        'ProductTemplate':('step_harvest_packaging_id','_check_step_harvest_packaging'),
        'ProductPackaging':('_check_step_container_mapping','_step_physical_container'),
        'StockPicking':('button_validate','_step_prepare_container_return','action_step_container_return'),
        'TransferLine':('lot_id',)}),
)
BASE_MODELS = {'step.scale.profile':[], 'step.fruit.reception.import':[],
               'step.harvest.container.transfer':['mail.thread','mail.activity.mixin'],
               'step.harvest.container.transfer.line':[]}
EXTRAS = {
    'reversal': "_REVERSE = object()\n_AUDIT = {'step_fruit_reversal_id','step_fruit_correction_of_id','step_fruit_reversal_reason'}\n",
    'correction': "_CORRECTION = object()\n_AUDIT_FIELDS = {'step_receipt_correction_line_id','step_receipt_correction_id','step_receipt_correction_direction','step_receipt_correction_reason'}\ndef _internal(records):\n    return records.env.context.get('_receipt_product_correction') is _CORRECTION\n",
}
BASE = "from collections import defaultdict\nfrom odoo import _, api, Command, fields, models\nfrom odoo.exceptions import AccessError, UserError, ValidationError\n"


def source(root, name):
    raw=(root/name).read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(raw).hexdigest()!=SOURCE_PINS[name]:
        raise ValueError('Changed original receipt provider: '+name)
    return raw.decode('utf8')


def emit(folder,name,content):
    path=folder/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content,encoding='utf8',newline='\n')


def changed(s,old,new):
    if s.count(old)!=1:
        raise ValueError('Unexpected occurrence of '+old)
    return s.replace(old,new)


def member(node):
    if isinstance(node,ast.FunctionDef):
        return node.name
    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name):
        return node.targets[0].id


def parts(text,classes,extras):
    lines=text.splitlines(keepends=True)
    tree={c.name:c for c in ast.parse(text).body if isinstance(c,ast.ClassDef)}
    output=[BASE,extras]
    for name,requested in classes.items():
        cls=tree[name]
        nodes={member(item):item for item in cls.body if member(item)}
        model=ast.literal_eval(nodes.get('_name',nodes.get('_inherit')).value)
        output.extend(['\n\n',lines[cls.lineno-1]])
        if model in BASE_MODELS:
            keys=['_name','_description','_order','_inherit']
        else:
            keys=[]
            output.append('    _inherit = '+repr(model)+'\n')
        for key in [x for x in keys if x in nodes]+list(requested):
            item=nodes[key]
            start=min([item.lineno]+[d.lineno for d in getattr(item,'decorator_list',[])])
            output.extend(['\n' if isinstance(item,ast.FunctionDef) else '',*lines[start-1:item.end_lineno]])
    return ''.join(output)


def derive(root,target):
    if target.exists():
        raise FileExistsError(target)
    app=target/OWNER
    report=target/REPORT
    donors=set()
    texts={}
    for label,path in WHOLE.items():
        texts[label]=source(root,path)
        donors.add(path.split('/')[0])
    texts['simple']=changed(texts['simple'],'package.step_export_shipment_ids or','package._has_archived_shipment() or')
    for label,path,classes in PIECES:
        texts[label]=parts(source(root,path),classes,EXTRAS.get(label,''))
        donors.add(path.split('/')[0])
    profile_path='step_application_profiles/models/profiles.py'
    profile=source(root,profile_path)
    donors.add('step_application_profiles')
    classes={'Users':('_step_application_levels',),'ModelAccess':('check',),
             'Picking':('create','write','button_validate'),'Package':('create','write'),
             'PackageLine':('create','write','unlink')}
    helper=next(n for n in ast.parse(profile).body if isinstance(n,ast.FunctionDef) and n.name=='require_fruit_operation')
    prefix=profile[:profile.index('class Users(')]+ast.get_source_segment(profile,helper)+'\n'
    touched=('step.fruit.reception.import','step.fruit.package.line','step.packing.picking.tag.line',
             'step.harvest.container.transfer','step.harvest.container.transfer.line','step.scale.profile',
             'stock.picking','stock.move','stock.move.line','stock.quant','stock.quant.package','stock.lot',
             'product.product','product.template','product.packaging')
    prefix+='RECEIPT_MODELS = '+repr(touched)+'\n'
    texts['access_profiles']=changed(parts(profile,classes,prefix),
        'if not permitted or self.env.su:return permitted',
        'if not permitted or self.env.su or model not in RECEIPT_MODELS:return permitted')
    for name in ['__init__.py','__manifest__.py','models.py','hooks.py']:
        txt=source(root,REPORT+'/'+name)
        if name=='__manifest__.py':
            txt=changed(txt,'18.0.1.0.0','18.0.1.0.1')
        if name=='models.py':
            txt=changed(txt,'    # The reporting provider', '    __slots__ = ()\n\n    def _allows_receipt_stock(self):\n        return False\n\n    # The reporting provider')
            txt=changed(txt,"if operation != 'read':","if operation != 'read' and not self._allows_receipt_stock():")
            for method,arg in [('create','values'),('write','values'),('unlink','')]:
                sig='    def '+method+'(self'+(', '+arg if arg else '')+'):\n        raise report_access()'
                txt=changed(txt,sig,sig.replace('        raise report_access()', '        if not self._allows_receipt_stock():\n            raise report_access()\n        return super().'+method+'('+arg+')'))
            txt=changed(txt,"    if REPORT_FIELDS.intersection(values):","    if REPORT_FIELDS.intersection(values) and not self._allows_receipt_stock():")
            txt=changed(txt,"        if any(REPORT_FIELDS.intersection(values) or values.get('is_fruit_tag') for values in vals_list):",
                "        if not self._allows_receipt_stock() and any(REPORT_FIELDS.intersection(values) or values.get('is_fruit_tag') for values in vals_list):")
            txt=changed(txt,"    _inherit = 'stock.quant.package'","    _inherit = 'stock.quant.package'\n\n    def _allows_receipt_stock(self):\n        return False")
        emit(report,name,txt)
    for name in ['__manifest__.py','permissions.py','hooks.py']:
        emit(app,name,(HERE/'cerro_receipt_parts'/name).read_text(encoding='utf8'))
    notices = ['Origen de las fuentes del módulo de recepción de Cerro.', '']
    for path, fingerprint in sorted(SOURCE_PINS.items()):
        donor=path.split('/')[0]
        license_name=ast.literal_eval((root/donor/'__manifest__.py').read_text(encoding='utf8'))['license']
        expected='AGPL-3' if donor=='step_packing_ticket_revision' else 'LGPL-3'
        if license_name!=expected:
            raise ValueError('Changed source license: '+donor)
        notices.append(f'{path}  {license_name}  SHA-256 (LF) {fingerprint}')
    emit(app,'SOURCE.txt','\n'.join(notices)+'\n')
    fields_by_model={}
    for label,txt in texts.items():
        emit(app,label+'.py',txt)
        for cls in [c for c in ast.parse(txt).body if isinstance(c,ast.ClassDef)]:
            defs={member(e):e for e in cls.body if member(e)}
            model=ast.literal_eval(defs.get('_name',defs.get('_inherit')).value)
            fields_by_model.setdefault(model,set()).update(
                key for key,e in defs.items() if isinstance(e,ast.Assign) and isinstance(e.value,ast.Call)
                and isinstance(e.value.func,ast.Attribute) and isinstance(e.value.func.value,ast.Name) and e.value.func.value.id=='fields')
    fields_by_model.setdefault('product.product',set()).update(fields_by_model['product.template'])
    emit(app,'bindings.py','BASE_MODELS = '+repr(BASE_MODELS)+'\nSOURCES = '+repr(sorted(donors))+
         '\nFIELDS = '+repr({m:sorted(items) for m,items in sorted(fields_by_model.items())})+'\n')
    emit(app,'__init__.py','from . import '+', '.join([*texts,'permissions'])+'\nfrom .hooks import adopt_originals\n')
    for name in ['static/src/scale_capture.xml','static/src/scale_capture.js']:
        emit(app,name,source(root,'step_inventory_packing/'+name))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    derive(opts.source,opts.output)
