"""Verify the published import menu and forms with an existing user and company.

This verification reads views and records, rolls back, and does not import data.
"""
import argparse
import configparser
import json
import os
from pathlib import Path
import re
import subprocess


PROBE = '''
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_existing_user_environment
try:
    assert env.cr.dbname == DATABASE
    business = scoped_existing_user_environment(env, USER_ID, env['res.company'].browse(COMPANY_ID))
    module = env['ir.module.module'].search([('name', '=', 'step_packing_ticket_revision'), ('state', '=', 'installed')])
    assert module.latest_version == VERSION
    source = Path(importlib.import_module('odoo.addons.step_packing_ticket_revision').__file__).resolve().parent
    assert source == ROOT / 'step_packing_ticket_revision'
    menu = business.ref('step_inventory_packing.menu_steps_fruit_process_reception')
    importer = business.ref('step_packing_ticket_revision.menu_external_fruit_reception_import')
    visible = business['ir.ui.menu']._visible_menu_ids()
    assert menu.id in visible and importer.id in visible
    model = business[importer.action.res_model]
    assert model.check_access_rights('create', raise_exception=False)
    arch = etree.fromstring(model.get_view(view_id=importer.action.view_id.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_import']") and arch.xpath("//button[@name='action_review']")
    assert arch.xpath("//field[@name='file']")
    action = business.ref('step_inventory_packing.action_steps_fruit_process_reception')
    views = {kind: view for view, kind in action.views}
    receipts = business['stock.picking']
    form = etree.fromstring(receipts.get_view(view_id=views['form'], view_type='form')['arch'])
    assert form.xpath("//field[@name='step_external_reception_folio']")
    assert form.xpath("//field[@name='fruit_guide_number']")
    listed = etree.fromstring(receipts.get_view(view_id=views['list'], view_type='list')['arch'])
    assert listed.xpath("//header/button[@name='%s']" % importer.action.id)
    print('EXTERNAL_RECEPTION_USER_OK ' + json.dumps({'database': DATABASE, 'user_id': USER_ID,
        'company_id': COMPANY_ID, 'version': VERSION, 'release': str(ROOT),
        'menu': True, 'list_import_button': True, 'wizard': True, 'native_receipt_form': True}))
finally:
    env.cr.rollback()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('commit')
    parser.add_argument('user_id', type=int)
    parser.add_argument('company_id', type=int)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-f0-9]{40}', args.commit)
    tools = Path(__file__).resolve().parent
    target = json.loads((tools / 'environments.json').read_text())['environments'][args.environment]
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    assert options['db_name'] == target['database']
    root = Path('/opt/steps-managed/releases') / args.environment / args.commit
    proof = json.loads((root / 'release.json').read_text())
    assert proof['commit'] == args.commit and proof['versions']['step_packing_ticket_revision'] == args.version
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    header = ('import sys\nsys.path.insert(0,' + repr(str(tools)) + ')\nDATABASE=' + repr(target['database'])
              + '\nUSER_ID=' + repr(args.user_id) + '\nCOMPANY_ID=' + repr(args.company_id)
              + '\nVERSION=' + repr(args.version) + '\nROOT=__import__("pathlib").Path(' + repr(str(root)) + ')\n')
    result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
        '-c', target['config'], '-d', target['database'], '--no-http', '--workers=0', '--max-cron-threads=0',
        '--log-level=error'], input=header + PROBE, text=True, capture_output=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'EXTERNAL_RECEPTION_USER_OK ' in result.stdout, 'Read ' + str(args.output)
    print(next(line for line in result.stdout.splitlines() if line.startswith('EXTERNAL_RECEPTION_USER_OK ')))


if __name__ == '__main__':
    main()
