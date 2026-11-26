"""Rehearse and apply an explicitly approved correction of intact C-tag weights.

Private JSON plan identifies the company, existing business user and every row,
including its previous/approved kilograms. No customer data belongs in Git.
The receipt distribution must already contain the approved weights. Preserve
historical receipt/product-correction moves and add native inventory deltas for
third-party stock. No module upgrade, valuation, accounting or notifications.
"""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess


MODULES = ('step_inventory_packing', 'step_packing_operations',
           'step_packing_reception_revision', 'step_packing_ticket_revision',
           'step_packing_tare', 'step_packing_tag_company')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_plan(plan):
    require(plan['ticket'] == 240 and plan['database'] == 'CERRO_EL_PLOMO', 'Wrong ticket/destination')
    require(type(plan['user_id']) is int and plan['user_id'] > 1, 'Existing business user required')
    require(type(plan['company_id']) is int and plan['company_id'] > 0, 'Explicit company required')
    require(len(plan['tags']) == 7, 'The approved scope contains seven tags')
    require(len({row['package_id'] for row in plan['tags']}) == 7, 'Repeated tag')
    require(len({row['name'] for row in plan['tags']}) == 7, 'Repeated reference')
    for row in plan['tags']:
        require(all(type(row[k]) is int and row[k] > 0 for k in (
            'package_id', 'detail_id', 'receipt_line_id', 'picking_id',
            'lot_id', 'product_id', 'owner_id', 'location_id', 'boxes')), 'Invalid identity')
        require(0 < row['old_kg'] < row['new_kg'], 'Only the approved positive corrections are supported')
    require(round(sum(row['old_kg'] for row in plan['tags']), 2) == 4300.5, 'Previous total differs')
    require(round(sum(row['new_kg'] for row in plan['tags']), 2) == 4455.4, 'Approved total differs')


def repair(env, plan):
    """One transaction; caller commits only after all preservation checks pass."""
    from lxml import etree
    from odoo import Command
    from odoo.addons.step_inventory_packing.models.fruit_package import StepFruitPackageLine
    from odoo.tools import SQL
    from odoo.tools.float_utils import float_compare
    from native_business_profile import scoped_existing_user_environment

    validate_plan(plan)
    require(env.cr.dbname == plan['database'] or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_t240_'), 'Unexpected database')
    env.cr.execute("SET LOCAL lock_timeout='10s'")
    # Also prevents a new OT, repalletization or purchase claim while validating.
    env.cr.execute('LOCK TABLE stock_picking, stock_move, stock_move_line, stock_quant, '
                   'stock_quant_package, step_fruit_package_line, step_packing_picking_tag_line, '
                   'step_packing_production, step_packing_repack_line, purchase_order '
                   'IN SHARE ROW EXCLUSIVE MODE')
    env.invalidate_all()
    company = env['res.company'].browse(plan['company_id']).exists()
    require(len(company) == 1 and company.name == plan['company_name'], 'Company differs')
    scoped = scoped_existing_user_environment(env, plan['user_id'], company)
    scoped = scoped(context=dict(scoped.context, tracking_disable=True, mail_notrack=True,
                                 mail_create_nosubscribe=True, mail_notify_force_send=False))
    require(scoped.user.has_group('stock.group_stock_manager'), 'Existing inventory manager required')
    kg = scoped.ref('uom.product_uom_kgm')
    packages = scoped['stock.quant.package'].browse([r['package_id'] for r in plan['tags']])
    require(len(packages.exists()) == 7, 'Missing tag')
    packages.check_access('write')
    wizard = scoped['step.reception.product.correction']
    checks, status = [], []
    for spec in plan['tags']:
        tag = packages.browse(spec['package_id'])
        row = scoped['step.packing.picking.tag.line'].browse(spec['receipt_line_id']).exists()
        detail = tag.step_tag_line_ids
        receipt = tag.step_process_reception_id
        require(tag.name == spec['name'] and tag.company_id == company and tag.step_packing_company_id == company
                and tag.is_fruit_tag and tag.step_tag_kind == 'C' and tag.step_tag_state == 'validated', 'Tag identity/state differs')
        require(receipt.id == spec['picking_id'] and receipt.company_id == company
                and receipt.state == 'done' and receipt.step_fruit_reception_kind == 'process', 'Receipt differs')
        require(len(row) == 1 and row.package_id == tag and row.picking_id == receipt
                and row.product_id.id == spec['product_id'] and row.stock_lot_id.id == spec['lot_id'], 'Receipt row differs')
        require(len(detail) == 1 and detail.id == spec['detail_id'] and detail.product_id == row.product_id
                and detail.lot_id == row.stock_lot_id and detail.producer_id.id == spec['owner_id'], 'Detail differs')
        require(tag.step_producer_id == detail.producer_id and receipt.partner_id == detail.producer_id
                and detail.producer_id != company.partner_id, 'Third-party owner differs')
        require(tag.box_count == spec['boxes'] and detail.boxes == spec['boxes']
                and row.quantity == spec['boxes'] and row.box_count == spec['boxes'], 'Boxes differ')
        require(not float_compare(row.kilos, spec['new_kg'], precision_digits=2), 'Receipt does not contain approved weight')
        require(not float_compare(row.step_import_stock_quantity, spec['old_kg'], precision_digits=2), 'Import snapshot differs')
        require(detail.product_id.is_storable and detail.uom_id == kg and row.product_id.uom_id == kg, 'Kilogram stock required')
        quants = tag.quant_ids.filtered(lambda q: q.quantity or q.reserved_quantity)
        require(len(quants) == 1, 'Intact stock required')
        quant = quants
        require(quant.company_id == company and quant.location_id.id == spec['location_id']
                and quant.location_id == receipt.location_dest_id and quant.location_id.usage == 'internal'
                and quant.product_id == detail.product_id and quant.owner_id == detail.producer_id
                and quant.lot_id == detail.lot_id and not quant.reserved_quantity, 'Stock identity/reservation differs')
        require(not tag.step_packing_production_id and not detail.source_package_id, 'A process/split is already linked')
        check = wizard.new({'picking_id': receipt.id})
        check._check_unused(tag)
        detail._check_open_ot()
        old = not float_compare(detail.kilos, spec['old_kg'], precision_digits=2)
        new = not float_compare(detail.kilos, spec['new_kg'], precision_digits=2)
        require(old or new, 'Weight changed concurrently')
        require(not float_compare(detail.quantity, detail.kilos, precision_digits=2)
                and not float_compare(quant.quantity, detail.kilos, precision_digits=2), 'Detail and stock disagree')
        history = scoped['stock.move.line'].search([
            ('state', '!=', 'cancel'), '|', ('package_id', '=', tag.id), ('result_package_id', '=', tag.id)])
        require(history and all(line.state == 'done' and line.company_id == company for line in history), 'Pending/foreign movement')
        prefix = 'T240: ' + tag.name
        for line in history:
            require(line.picking_id == receipt or line.move_id.step_receipt_correction_line_id == row
                    or (new and line.move_id.origin == prefix and line.product_id == detail.product_id
                        and line.lot_id == detail.lot_id and line.owner_id == detail.producer_id), 'Later movement exists')
        previous = scoped['stock.move'].search([('origin', '=', prefix), ('company_id', '=', company.id)])
        if old:
            require(not previous, 'Correction already exists with previous weight')
        else:
            require(len(previous) == 1 and previous.state == 'done'
                    and not float_compare(previous.quantity, spec['new_kg']-spec['old_kg'], precision_digits=2), 'Idempotency audit differs')
        status.append('old' if old else 'new')
        checks.append((spec, tag, row, detail, quant))
    require(len(set(status)) == 1, 'Partially corrected plan requires review')

    def fingerprints():
        result = {}
        tables = ('stock_picking', 'stock_move', 'stock_move_line', 'stock_quant_package',
                  'step_packing_picking_tag_line', 'step_packing_production', 'step_packing_repack_line',
                  'purchase_order', 'purchase_order_line', 'account_move', 'account_move_line',
                  'stock_valuation_layer', 'stock_lot', 'product_template', 'res_partner',
                  'mail_mail', 'mail_notification')
        for table in tables:
            env.cr.execute(SQL('SELECT id,md5(to_jsonb(t)::text) FROM %s t ORDER BY id', SQL.identifier(table)))
            result[table] = dict(env.cr.fetchall())
        env.cr.execute('SELECT id,md5((to_jsonb(t)-CASE WHEN id=ANY(%s) '
                       "THEN ARRAY['kilos','quantity','write_date','write_uid'] ELSE ARRAY[]::text[] END)::text) "
                       'FROM step_fruit_package_line t ORDER BY id', [[r['detail_id'] for r in plan['tags']]])
        result['step_fruit_package_line'] = dict(env.cr.fetchall())
        return result

    before = fingerprints()
    # Preserve every quant outside the exact inventory/internal pairs.
    allowed_quant_keys = set()
    for spec, tag, row, detail, quant in checks:
        place = detail.product_id.with_company(company).property_stock_inventory
        require(place and place.usage == 'inventory' and place.company_id == company and not place.scrap_location, 'Inventory location differs')
        for location in (place, quant.location_id):
            allowed_quant_keys.add((detail.product_id.id, location.id, detail.lot_id.id,
                                    tag.id if location == quant.location_id else None, detail.producer_id.id, company.id))
    env.cr.execute('SELECT id,product_id,location_id,lot_id,package_id,owner_id,company_id,to_jsonb(t) FROM stock_quant t')
    quant_before = {r[0]: (tuple(r[1:7]), r[7]) for r in env.cr.fetchall()}
    moves = scoped['stock.move']
    if status[0] == 'old':
        for spec, tag, row, detail, quant in checks:
            inventory = detail.product_id.with_company(company).property_stock_inventory
            delta = round(spec['new_kg'] - spec['old_kg'], 2)
            move = scoped['stock.move'].with_company(company).create({
                'name': 'T240: Corrección de kilos de tarja ' + tag.name, 'origin': 'T240: ' + tag.name,
                'company_id': company.id, 'product_id': detail.product_id.id, 'product_uom': kg.id,
                'product_uom_qty': delta, 'location_id': inventory.id,
                'location_dest_id': quant.location_id.id, 'state': 'confirmed', 'is_inventory': True,
                'picked': True, 'restrict_partner_id': detail.producer_id.id,
                'move_line_ids': [Command.create({
                    'company_id': company.id, 'product_id': detail.product_id.id, 'product_uom_id': kg.id,
                    'quantity': delta, 'lot_id': detail.lot_id.id, 'owner_id': detail.producer_id.id,
                    'location_id': inventory.id, 'location_dest_id': quant.location_id.id,
                    'result_package_id': tag.id, 'picked': True})]})
            move._action_done(cancel_backorder=True)
            require(move.state == 'done' and not move.stock_valuation_layer_ids and not move.picking_id, 'Native delta failed/valued')
            # Reviewed, one-off maintenance: bypass only the ordinary immutable
            # detail guard, retaining native ORM fields and constraints.
            super(StepFruitPackageLine, detail).write({'quantity': spec['new_kg'], 'kilos': spec['new_kg']})
            moves |= move
    env.flush_all()
    env.invalidate_all()
    after = fingerprints()
    for table, rows in before.items():
        require(all(after[table].get(k) == v for k, v in rows.items()), 'Historical row changed: ' + table)
        require(table in ('stock_move', 'stock_move_line') or rows.keys() == after[table].keys(), 'Rows added/removed: ' + table)
    require(set(after['stock_move']) - set(before['stock_move']) == set(moves.ids), 'Unexpected new moves')
    require(set(after['stock_move_line']) - set(before['stock_move_line']) == set(moves.move_line_ids.ids), 'Unexpected new move lines')
    env.cr.execute('SELECT id,product_id,location_id,lot_id,package_id,owner_id,company_id,to_jsonb(t) FROM stock_quant t')
    quant_after = {r[0]: (tuple(r[1:7]), r[7]) for r in env.cr.fetchall()}
    require(quant_before.keys() <= quant_after.keys(), 'Existing quants removed')
    for key, (identity, values) in quant_after.items():
        if key in quant_before:
            require(identity == quant_before[key][0], 'Quant identity changed')
        if identity not in allowed_quant_keys:
            require(key in quant_before and values == quant_before[key][1], 'Unrelated stock changed')
    for identity in allowed_quant_keys:
        previous = sum(float(v['quantity']) for k, v in quant_before.values() if k == identity)
        actual = sum(float(v['quantity']) for k, v in quant_after.values() if k == identity)
        spec = next(s for s in plan['tags'] if s['lot_id'] == identity[2] and s['owner_id'] == identity[4])
        delta = 0 if status[0] == 'new' else round(spec['new_kg'] - spec['old_kg'], 2)
        expected = delta if identity[3] else -delta
        require(not float_compare(actual - previous, expected, precision_digits=2), 'Inventory delta differs')
    rows = []
    for spec, tag, row, detail, quant in checks:
        require(not float_compare(tag.step_actual_kg, spec['new_kg'], precision_digits=2)
                and not float_compare(detail.quantity, spec['new_kg'], precision_digits=2)
                and not float_compare(quant.quantity, spec['new_kg'], precision_digits=2)
                and not quant.reserved_quantity, 'Corrected totals differ')
        require(tag.box_count == spec['boxes'] and detail.boxes == spec['boxes'], 'Boxes changed')
        tag._check_step_tag()
        rows.append({'name': tag.name, 'package_id': tag.id, 'old_kg': spec['old_kg'],
                     'kilos': tag.step_actual_kg, 'stock_kg': quant.quantity, 'boxes': tag.box_count,
                     'receipt_kg': row.kilos, 'lot_id': quant.lot_id.id, 'owner_id': quant.owner_id.id})
    # Exercise the business profile's real menu, effective form, and web read.
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    for xmlid in ('step_packing_operations.menu_packing_reception_process',
                  'step_inventory_packing.menu_steps_fruit_packages'):
        menu = scoped.ref(xmlid)
        require(menu.id in visible and menu.action, 'Native menu inaccessible: ' + xmlid)
    arch = etree.fromstring(packages.get_view(view_type='form')['arch'])
    require(arch.xpath("//field[@name='step_actual_kg']"), 'Native tag form missing kilograms')
    web = packages.web_read({'name': {}, 'step_actual_kg': {}, 'box_count': {}, 'step_tag_state': {}})
    require(len(web) == 7 and round(sum(r['step_actual_kg'] for r in web), 2) == 4455.4, 'Native web read differs')
    versions = {m.name: m.latest_version for m in env['ir.module.module'].search([('name', 'in', MODULES), ('state', '=', 'installed')])}
    require(len(versions) == len(MODULES), 'Missing installed module')
    return {'database': env.cr.dbname, 'company_id': company.id, 'user_id': scoped.uid,
            'rows': rows, 'total_kg': round(sum(r['kilos'] for r in rows), 2),
            'boxes': sum(r['boxes'] for r in rows), 'added_kg': 154.9,
            'moves': moves.ids, 'already_applied': status[0] == 'new',
            'native_menu_form_web_read': True, 'historical_rows_preserved': True,
            'accounting_valuation_notifications_unchanged': True, 'versions': versions}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def query(database, sql):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1',
                                    '-d', database, '-Atc', sql], text=True).strip()


def baseline(config):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(config)
    require(cfg['options']['db_name'] == 'CERRO_EL_PLOMO' and cfg['options']['db_user'] == 'cerro_odoo18', 'Canonical config differs')
    resolved = {}
    for root in cfg['options']['addons_path'].split(','):
        for manifest in Path(root.strip()).glob('*/__manifest__.py'):
            resolved.setdefault(manifest.parent.name, manifest.parent)
    sources = {}
    # Hash the effective stock/packing stack, not unrelated frontend/vendor
    # assets that happen to live below a legacy addon root.
    relevant = {name: path for name, path in resolved.items()
                if name in MODULES or name.startswith(('stock', 'step_inventory', 'step_packing', 'step_producer'))}
    for name, path in relevant.items():
        h = hashlib.sha256()
        for source in sorted(path.rglob('*')):
            if source.is_file() and '__pycache__' not in source.parts and source.suffix in ('.py', '.xml', '.csv', '.js', '.css', '.scss'):
                h.update(str(source.relative_to(path)).encode()); h.update(source.read_bytes())
        sources[name] = h.hexdigest()
    return {'config': digest(config), 'sources': sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('rehearse', 'apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Root lease/backup privileges required')
    plan = json.loads(args.plan.read_text())
    validate_plan(plan)
    config = Path('/etc/odoo18-cerroelplomo.conf')
    stage = args.stage.resolve()
    require(str(stage).startswith('/opt/steps-validation/t240-') and len(stage.parts) == 4, 'Private task stage required')
    script = Path(__file__).resolve()
    identity = {'plan': digest(args.plan), 'tool': digest(script), 'profile': digest(script.with_name('native_business_profile.py'))}

    def probe(database, label):
        header = ('import sys,json\nsys.path.insert(0,' + repr(str(script.parent)) + ')\n'
                  'from correct_reception_weights import repair\n'
                  'result=repair(env,' + repr(plan) + ')\nenv.cr.commit()\n'
                  'print("RECEPTION_WEIGHT_OK "+json.dumps(result))\n')
        process = subprocess.run(['sudo', '-u', 'cerro_odoo18', '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
            'shell', '-c', str(config), '-d', database, '--db-filter=^'+database+'$', '--no-http',
            '--workers=0', '--max-cron-threads=0', '--log-level=critical'], input=header, text=True, capture_output=True)
        (stage / (label+'.log')).write_text(process.stdout + process.stderr)
        lines = [s.split('RECEPTION_WEIGHT_OK ', 1)[1] for s in process.stdout.splitlines() if s.startswith('RECEPTION_WEIGHT_OK ')]
        require(process.returncode == 0 and len(lines) == 1, 'Probe failed; inspect private ' + label + '.log')
        return json.loads(lines[0])

    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for entry in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = entry.read_bytes().decode(errors='replace').split('\0')
            except OSError:
                continue
            if any(Path(a).name == 'odoo-bin' for a in argv):
                require(not any(a in ('-u', '-i', '--update', '--init') or a.startswith(('--update=', '--init=')) for a in argv), 'Concurrent upgrade')
        current = baseline(config)
        if args.mode == 'rehearse':
            stage.mkdir(mode=0o755, exist_ok=False)
            (stage/'identity.json').write_text(json.dumps(identity))
            stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            clone = 'MANAGEMENT_QA_CERRO_t240_' + stamp
            require(not query('postgres', "SELECT 1 FROM pg_database WHERE datname='"+clone+"'"), 'Fresh copy required')
            backup = stage/'source.dump'
            with backup.open('xb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                subprocess.run(['sudo','-u','postgres','pg_dump','-Fc',plan['database']], stdout=stream, check=True)
            with backup.open('rb') as stream:
                subprocess.run(['sudo','-u','postgres','pg_restore','--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
            subprocess.run(['sudo','-u','postgres','createdb','-O','cerro_odoo18',clone], check=True)
            query(clone, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with backup.open('rb') as stream:
                subprocess.run(['sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments',
                                '--role','cerro_odoo18','-d',clone], stdin=stream, check=True)
            query(clone, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            tested = probe(clone, 'clone')
            repeated = probe(clone, 'clone-idempotent')
            require(not tested['already_applied'] and repeated['already_applied'] and not repeated['moves'], 'Idempotency rehearsal failed')
            require(current == baseline(config), 'Runtime changed during rehearsal')
            proof = {'identity': identity, 'baseline': current, 'clone': clone, 'tested': tested, 'idempotent': repeated}
            (stage/'certificate.json').write_text(json.dumps(proof, indent=2))
            print('RECEPTION_WEIGHT_REHEARSED ' + json.dumps({'clone':clone,'total_kg':tested['total_kg'],'idempotent':True}))
        else:
            proof = json.loads((stage/'certificate.json').read_text())
            require(identity == proof['identity'] and current == proof['baseline'], 'Plan/tool/runtime differs from rehearsal')
            require(not (stage/'live.json').exists(), 'Delivery already recorded')
            backup = stage/'before-live.dump'
            with backup.open('xb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                subprocess.run(['sudo','-u','postgres','pg_dump','-Fc',plan['database']], stdout=stream, check=True)
            with backup.open('rb') as stream:
                subprocess.run(['sudo','-u','postgres','pg_restore','--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
            (stage/'odoo.conf').write_bytes(config.read_bytes()); (stage/'odoo.conf').chmod(0o600)
            live = probe(plan['database'], 'live')
            require(live['rows'] == proof['tested']['rows'] and live['versions'] == proof['tested']['versions'], 'Live result differs')
            (stage/'live.json').write_text(json.dumps({'result':live, 'backup_sha256':digest(backup), 'identity':identity}, indent=2))
            print('RECEPTION_WEIGHT_APPLIED '+json.dumps({'total_kg':live['total_kg'],'boxes':live['boxes'],'moves':live['moves']}))


if __name__ == '__main__':
    main()
