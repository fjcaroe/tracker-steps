"""Load Cerro's four canonical fruit-category relations on the first packing registry."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil

PACKING = 'step_packing'
PRODUCERS = 'step_producers'
DIGESTS = {
    'step_packing/__manifest__.py': '1f935a6ac9a878b76c095370a42a043ab2550531e82378fb1e2bd503e551fe1b',
    'step_packing/models/stock_picking.py': 'bc534c62c549ee592a195881966ca169a70d91fa6e0191519adc0dc60472d973',
    'step_packing/models/step_packing_picking_tag_line.py': '187abf1f9729e1cfe6de398965816079ee7ded9b62ed1dbf20f44a06c4685286',
    'step_producers/__manifest__.py': '333197e87c34170330627580d662e3f346e14ad15cf193212a51a14abd55c08a',
    'step_producers/models/purchase_contract.py': 'f2339e1bb58ebd837cdd35e2024180719ae3169ef8e1ae35966cf9c49e440d6b',
    'step_fruit_category_unification/models/catalogs.py': '54827aafc3c9c46a37c86665ccf99459ee1428c5c385255a8b9a5f42bdaaee71',
}


def span(text, class_name, member):
    cls, = [n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == class_name]
    candidates = [n for n in cls.body if (isinstance(n, ast.FunctionDef) and n.name == member) or
                  (isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id==member for t in n.targets))]
    node, = candidates
    start = min([node.lineno, *[d.lineno for d in getattr(node, 'decorator_list', [])]]) - 1
    return start, node.end_lineno


def derive(source, output):
    inputs = {}
    for name, expected in DIGESTS.items():
        text = (source / name).read_text(encoding='utf-8')
        if hashlib.sha256(text.encode()).hexdigest() != expected:
            raise ValueError('The admitted fruit-category source changed: ' + name)
        inputs[name] = text
    donor = inputs['step_fruit_category_unification/models/catalogs.py']
    owner_lines = donor.splitlines(keepends=True)

    def definition(cls, member):
        begin, end = span(donor, cls, member)
        return ''.join(owner_lines[begin:end])

    revised = {}
    for file, old_class, new_class, fields in (
        ('step_packing/models/stock_picking.py', 'StockPicking', 'Picking', ('fruit_category_id','fruit_class_id')),
        ('step_packing/models/step_packing_picking_tag_line.py', 'StepPackingPickingTagLine', 'ReceiptLine', ('category_id',)),
        ('step_producers/models/purchase_contract.py', 'ProducerPurchaseContractProduct', 'ContractProduct', ('category_id',)),
    ):
        text = inputs[file]
        for name in fields:
            begin, end = span(text, old_class, name)
            lines = text.splitlines(keepends=True)
            replacement = definition(new_class, name)
            if new_class == 'ReceiptLine':
                replacement = definition(new_class, '_check_company_auto') + replacement
            if new_class == 'Picking' and name == 'fruit_class_id':
                replacement += '\n' + definition(new_class, '_check_shared_fruit_categories')
            lines[begin:end] = [replacement]
            text = ''.join(lines)
        if new_class == 'Picking':
            text = text.replace('from odoo import fields, models', 'from odoo import api, fields, models')
        ast.parse(text)
        revised[file] = text
    packing = inputs['step_packing/__manifest__.py'].replace('"18.0.1.2.1"','"18.0.1.2.2"')
    packing = packing.replace('"step_packing_process_catalog", "product"', '"step_packing_process_catalog", "step_management_costs", "product"')
    assert 'step_management_costs' in ast.literal_eval(packing)['depends']
    revised['step_packing/__manifest__.py'] = packing
    producers = inputs['step_producers/__manifest__.py'].replace('18.0.1.9.1','18.0.1.9.2')
    assert ast.literal_eval(producers)['version'] == '18.0.1.9.2'
    revised['step_producers/__manifest__.py'] = producers
    if output.exists():
        raise ValueError('Choose a new private registry profile')
    output.mkdir(parents=True)
    for module in (PACKING, PRODUCERS):
        shutil.copytree(source / module, output / module, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name, text in revised.items():
        (output / name).write_text(text,encoding='utf-8',newline='\n')
    return {name:hashlib.sha256(text.encode()).hexdigest() for name,text in revised.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(derive(args.source,args.output),sort_keys=True))
