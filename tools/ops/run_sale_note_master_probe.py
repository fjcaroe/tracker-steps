"""Exercise the existing export sale masters in a certified Cerro copy."""
import argparse
import configparser
import fcntl
import json
from pathlib import Path
import re
import subprocess


PROBE = """
import json
from types import SimpleNamespace
from lxml import etree
from odoo import Command
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment

try:
    assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
    main = scoped_business_environment(env)
    company = main.company
    if COMPANY_ID:
        company = env['res.company'].search([('id', '=', COMPANY_ID), ('id', 'child_of', main.company.id)])
        assert len(company) == 1
    business = scoped_business_environment(env, company=company)
    order_model = business['sale.order']
    menu = business.ref('step_export.menu_step_export_sale_orders')
    assert menu.id in business['ir.ui.menu']._visible_menu_ids()
    context = safe_eval(menu.action.context, {})
    order_model = order_model.with_context(**context)
    product = business['product.product'].search([('default_code', '=', PRODUCT_CODE)])
    assert len(product) == 1 and product.step_export_enabled
    partner = main['sale.order'].search([('step_export_sale', '=', True),
                                        ('company_id', '=', main.company.id)], limit=1).partner_id.with_env(business)
    assert partner
    tree = etree.fromstring(order_model.get_view(view_type='form')['arch'])
    mode_node, = tree.xpath(".//field[@name='step_export_sale_mode_id']")
    pack_node, = tree.xpath(".//field[@name='order_line']/list/field[@name='product_packaging_id']")
    values = {'company_id': company.id, 'product_id': product.id,
              'parent': SimpleNamespace(company_id=company.id, step_export_sale_context=True, step_box_pricing=True)}
    modes = business['step.export.sale.mode'].search(safe_eval(mode_node.get('domain'), values))
    packages = business['product.packaging'].search(safe_eval(pack_node.get('domain'), values))
    by_weight = packages.filtered(lambda package: package.step_export_kg_per_box == KILOS_PER_BOX)
    assert modes and len(by_weight) == 1
    note = order_model.create({
        'partner_id': partner.id, 'step_export_sale_mode_id': modes[0].id,
        'order_line': [Command.create({'product_id': product.id, 'product_uom_qty': BOXES,
            'price_unit': 5, 'tax_id': [Command.clear()]})],
    })
    line = note.order_line
    assert note.step_box_pricing and note.step_export_sale_mode_id == modes[0]
    assert line.product_packaging_id == by_weight and line.product_uom_qty == BOXES
    assert abs(line.step_document_kg - BOXES * KILOS_PER_BOX) < 0.001
    assert note.amount_total == 5 * BOXES
    note.step_price_kg = True
    assert note.amount_total == 5 * BOXES * KILOS_PER_BOX
    assert line.product_uom_qty == BOXES and line.product_packaging_id == by_weight
    if CONFIRM:
        note.action_confirm()
        moves = line.move_ids.filtered(lambda move: move.state != 'cancel')
        assert note.state == 'sale' and moves and moves.product_packaging_id == by_weight
        assert all(move.company_id == company for move in moves)
    print('SALE_NOTE_MASTER_COPY_OK ' + json.dumps({'company': company.id,
        'product_code': PRODUCT_CODE, 'boxes': BOXES, 'kilos': line.step_document_kg,
        'mode': modes[0].id, 'packaging': by_weight.id, 'price_by_box_and_kg': True,
        'delivery_confirmed': CONFIRM}))
finally:
    env.cr.rollback()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('product_code')
    parser.add_argument('boxes', type=int)
    parser.add_argument('kilos_per_box', type=float)
    parser.add_argument('--company-id', type=int)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    assert re.fullmatch(r't210[a-z0-9_]*', args.run_id)
    assert args.boxes > 0 and args.kilos_per_box > 0
    root = Path(__file__).resolve().parent
    stage = Path('/opt/steps-validation') / ('management_cerro_' + args.run_id)
    proof = json.loads((stage / 'qa_passed.json').read_text())
    assert proof['database'] == 'MANAGEMENT_QA_CERRO_' + args.run_id
    entry = json.loads((root / 'environments.json').read_text())['environments']['cerro']
    config = configparser.ConfigParser(interpolation=None)
    config.read(entry['config'])
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', entry['service']], text=True).strip()
    header = (f'import sys\nsys.path.insert(0, {str(root)!r})\nPRODUCT_CODE = {args.product_code!r}\n'
              f'BOXES = {args.boxes!r}\nKILOS_PER_BOX = {args.kilos_per_box!r}\n'
              f'COMPANY_ID = {args.company_id!r}\nCONFIRM = {args.confirm!r}\n')
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
            '-c', entry['config'], '-d', proof['database'],
            '--addons-path=' + str(stage / 'addons') + ',' + config['options']['addons_path'],
            '--data-dir=' + str(stage / 'data'), '--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=error'],
            input=header + PROBE, text=True, capture_output=True)
    (stage / 'sale-note-master-probe.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'SALE_NOTE_MASTER_COPY_OK' in result.stdout, result.stderr[-3500:]
    print(result.stdout.strip())


if __name__ == '__main__':
    main()
