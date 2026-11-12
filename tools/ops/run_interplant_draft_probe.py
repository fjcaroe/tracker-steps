"""Replay an explicitly reported draft only in its certified disposable Cerro copy."""
import argparse
import configparser
import fcntl
import json
from pathlib import Path
import re
import subprocess

PROBE = '''
import json
from native_business_profile import scoped_business_environment
try:
    assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
    original = env['step.dispatch.guide'].search([('name','=',GUIDE_NAME)])
    assert len(original) == 1 and original.state == 'draft'
    business = scoped_business_environment(env,company=original.company_id)
    guide = business['step.dispatch.guide'].browse(original.id)
    destination = guide.step_destination_company_id
    assert destination and destination in business.user.company_ids
    assert business.companies == guide.company_id
    available = guide._destination_warehouses()
    assert available
    source = guide.company_id
    memberships = business.user.company_ids
    tags = guide.load_tag_ids
    guide._onchange_interplant_destination()
    assert guide.step_destination_warehouse_id
    selected = guide.step_destination_warehouse_id.with_company(destination)
    guide.action_confirm()
    receipt = guide.with_company(destination).step_destination_picking_id
    assert guide.picking_id.state == 'done' and receipt.state not in ('done','cancel')
    assert receipt.location_dest_id == selected.lot_stock_id
    assert not receipt.step_interplant_tag_ids.quant_ids.filtered(lambda q:q.quantity > 0)
    assert business.companies == source and business.user.company_ids == memberships
    boxes = sum(tags.mapped('box_count')); kilos = sum(tags.mapped('step_actual_kg'))
    assert sum(receipt.step_interplant_tag_ids.mapped('box_count')) == boxes
    assert abs(sum(receipt.step_interplant_tag_ids.mapped('step_actual_kg'))-kilos) < 0.01
    for line in receipt.move_line_ids:
        origin = line.step_interplant_origin_line_id
        assert line.owner_id == origin.owner_id and line.lot_id.name == origin.lot_id.name
        assert abs(line.quantity_product_uom-origin.quantity_product_uom) < 0.000001
    receipt.button_validate()
    assert receipt.state == 'done'
    assert abs(sum(receipt.step_interplant_tag_ids.quant_ids.mapped('quantity'))-sum(guide.picking_id.move_line_ids.mapped('quantity_product_uom'))) < 0.000001
    print('REPORTED_DRAFT_COPY_OK ' + json.dumps({'guide':guide.name,'source':source.id,
        'destination':destination.id,'warehouse':selected.id,'source_departed':True,
        'destination_pending':True,'destination_validation_done':True,'source_scope_unchanged':True,
        'tag_count':len(tags),'boxes':boxes,'kilos':kilos}))
finally:
    env.cr.rollback()
    print('PROBE_ROLLBACK_OK')
'''

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('run_id'); parser.add_argument('guide_name')
args = parser.parse_args()
assert re.fullmatch(r't209[a-z]+',args.run_id)
root = Path(__file__).resolve().parent
stage = Path('/opt/steps-validation')/('management_cerro_' + args.run_id)
qa = json.loads((stage/'qa_passed.json').read_text())
assert qa['database'] == 'MANAGEMENT_QA_CERRO_' + args.run_id
entry = json.loads((root/'environments.json').read_text())['environments']['cerro']
config = configparser.ConfigParser(interpolation=None); config.read(entry['config'])
user = subprocess.check_output(['systemctl','show','--value','--property=User',entry['service']],text=True).strip()
header = 'import sys\nsys.path.insert(0,' + repr(str(root)) + ')\nGUIDE_NAME=' + repr(args.guide_name) + '\n'
with open('/run/lock/steps-environments.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    result = subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell',
        '-c',entry['config'],'-d',qa['database'],'--addons-path='+str(stage/'addons')+','+config['options']['addons_path'],
        '--data-dir='+str(stage/'data'),'--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],
        input=header+PROBE,text=True,capture_output=True)
    (stage/'reported-draft-probe.log').write_text(result.stdout+result.stderr)
    assert result.returncode == 0 and 'REPORTED_DRAFT_COPY_OK' in result.stdout, result.stderr[-3500:]
    print(result.stdout.strip())
