"""Replay a private reception workbook in a certified copy and roll it back.

The plan selects an existing user's saved wizard, preserving their native
company, defaults and equivalences. It never imports into a published database.
"""
import argparse
import base64
import configparser
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import manage_management as management
from customer_qa_clone_access import clone_database_access


PROBE = '''
import json
from lxml import etree
from odoo import Command
from odoo.exceptions import UserError
from native_business_profile import scoped_existing_user_environment
try:
    assert env.cr.dbname == COPY_DATABASE
    original = env['step.external.fruit.reception.import'].browse(PLAN['wizard_id']).exists()
    assert len(original) == 1
    company = original.picking_type_id.company_id
    business = scoped_existing_user_environment(env, original.create_uid.id, company)
    source = business['step.external.fruit.reception.import'].browse(original.id)
    defaults = {field: source[field].id for field in (
        'picking_type_id', 'packing_id', 'season_id', 'product_id', 'category_id', 'fruit_class_id', 'template_id')}
    aliases = [Command.create({'source': row.source, 'kind': row.kind,
        'fundo_id': row.fundo_id.id, 'packaging_id': row.packaging_id.id}) for row in source.alias_ids]
    defaults.update(file=WORKBOOK, filename=FILENAME, save_template=False, alias_ids=aliases,
                    column_ids=[Command.create({'position': row.position, 'source': row.source,
                        'source_key': row.source_key, 'target': row.target}) for row in source.column_ids])
    model = business['step.external.fruit.reception.import']
    wizard = model.create(defaults)
    stock = env['stock.quant'].search([]).read(['quantity', 'reserved_quantity'])
    action = wizard.action_import()
    receipts = business['stock.picking'].search(action['domain'])
    assert len(receipts) == len(PLAN['folios'])
    assert set(receipts.mapped('step_external_reception_folio')) == set(PLAN['folios'])
    assert set(receipts.mapped('fruit_guide_number')) == set(PLAN['guides'])
    assert len(receipts.fruit_tag_line_ids) == PLAN['tags']
    assert sum(receipts.fruit_tag_line_ids.mapped('quantity')) == PLAN['boxes']
    assert abs(sum(receipts.fruit_tag_line_ids.mapped('kilos')) - PLAN['kilos']) < 0.00001
    assert receipts.company_id == company and set(receipts.mapped('state')) == {'draft'}
    assert all(receipt.partner_id == receipt.fruit_fundo_id.partner_id for receipt in receipts)
    assert not receipts.fruit_tag_line_ids.package_id
    assert env['stock.quant'].search([]).read(['quantity', 'reserved_quantity']) == stock
    try:
        with env.cr.savepoint():
            model.create(defaults).action_import()
    except UserError:
        duplicate_blocked = True
    else:
        raise AssertionError('Reimporting the workbook must be rejected')
    menu = business.ref('step_inventory_packing.menu_steps_fruit_process_reception')
    assert menu.id in business['ir.ui.menu']._visible_menu_ids()
    assert etree.fromstring(model.get_view(view_type='form')['arch']).xpath("//button[@name='action_import']")
    form = business.ref('step_packing_reception_revision.view_process_reception_form')
    assert etree.fromstring(receipts.get_view(view_id=form.id, view_type='form')['arch']).xpath(
        "//field[@name='step_external_reception_folio']")
    print('EXTERNAL_RECEPTION_CASE_OK ' + json.dumps({'company_id': company.id,
        'references': len(receipts), 'guides': len(PLAN['guides']), 'tags': PLAN['tags'],
        'boxes': PLAN['boxes'], 'kilos': PLAN['kilos'], 'drafts_only': True,
        'stock_unchanged': True, 'duplicate_blocked': duplicate_blocked, 'native_menu_and_forms': True}))
finally:
    env.cr.rollback()
    print('PROBE_ROLLBACK_OK')
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('run_id')
    parser.add_argument('plan', type=Path)
    parser.add_argument('workbook', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
    assert set(plan) == {'wizard_id', 'folios', 'guides', 'tags', 'boxes', 'kilos'}
    assert type(plan['wizard_id']) is int and plan['wizard_id'] > 0
    assert all(isinstance(plan[key], list) and plan[key] for key in ('folios', 'guides'))
    stage = Path('/opt/steps-validation') / ('management_' + args.environment + '_' + args.run_id)
    proof = json.loads((stage / 'qa_passed.json').read_text())
    database = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    assert proof['database'] == database
    release = json.loads((stage / 'addons/release.json').read_text())
    assert proof['commit'] == release['commit']
    for name, expected in release['files'].items():
        assert management.digest(stage / 'addons' / name) == expected
    target = json.loads((Path(__file__).parent / 'environments.json').read_text())['environments'][args.environment]
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(target['config'])
    options = cfg['options']
    assert options['db_name'] == target['database'] and database != target['database']
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    raw = args.workbook.read_bytes()
    header = ('COPY_DATABASE=' + repr(database) + '\nPLAN=' + repr(plan)
              + '\nWORKBOOK=' + repr(base64.b64encode(raw).decode())
              + '\nFILENAME=' + repr(args.workbook.name)
              + '\nimport sys\nsys.path.insert(0,' + repr(str(Path(__file__).parent)) + ')\n')
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        access = clone_database_access(management.query, database, stage, existing=True) if args.environment == 'qa-cerro' else nullcontext()
        with access:
            result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
                '-c', target['config'], '-d', database, '--db-filter=^' + database + '$',
                '--addons-path=' + str(stage / 'addons') + ',' + options['addons_path'],
                '--data-dir=' + str(stage / 'data'), '--no-http', '--workers=0', '--max-cron-threads=0',
                '--log-level=error'], input=header + PROBE, text=True, capture_output=True)
    (stage / 'external-reception-case.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'EXTERNAL_RECEPTION_CASE_OK ' in result.stdout and 'PROBE_ROLLBACK_OK' in result.stdout, 'Read ' + str(stage / 'external-reception-case.log')
    item = json.loads(next(line.partition('EXTERNAL_RECEPTION_CASE_OK ')[2]
                          for line in result.stdout.splitlines() if line.startswith('EXTERNAL_RECEPTION_CASE_OK ')))
    item.update(database=database, commit=proof['commit'], workbook_sha256=hashlib.sha256(raw).hexdigest(), rolled_back=True)
    (stage / 'external-reception-case.json').write_text(json.dumps(item, indent=2))
    print('EXTERNAL_RECEPTION_COPY_OK ' + json.dumps(item))


if __name__ == '__main__':
    main()
