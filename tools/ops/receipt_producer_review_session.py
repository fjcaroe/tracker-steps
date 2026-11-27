"""Create/remove a private existing-user session for read-only T246 UI review."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
parser.add_argument('--cleanup', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parent
entry = json.loads((root / 'environments.json').read_text())['environments'][args.environment]
config = configparser.ConfigParser(interpolation=None)
config.read(entry['config'])
assert config['options']['db_name'] == entry['database']
user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', entry['service']], text=True).strip()
script = '''
import json
from pathlib import Path
from odoo import http
import odoo.addons.step_packing_producer_change as addon
proof = Path(PROOF)
if CLEANUP:
    data = json.loads(proof.read_text())
    session = http.root.session_store.get(data['session_id'])
    assert session.get('db') == env.cr.dbname
    http.root.session_store.delete(session)
    proof.unlink()
else:
    assert not proof.exists()
    assert env['ir.module.module'].search([('name','=','step_packing_producer_change')]).latest_version == '18.0.1.1.1'
    receipt = env['stock.picking'].search([('step_fruit_reception_kind','=','process'),('state','=','done'),
        ('fruit_tag_line_ids.package_id.step_tag_state','=','validated')], order='id desc', limit=1)
    assert receipt and receipt.fruit_tag_line_ids.package_id
    company = receipt.company_id
    candidates = env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),('company_ids','in',company.ids)])
    candidates = candidates.filtered(lambda u: u.has_group('stock.group_stock_manager'))
    for candidate in candidates:
        business = env(user=candidate, su=False, context=dict(env.context, allowed_company_ids=company.ids))
        try:
            business['stock.picking'].browse(receipt.id)._step_check_received_producer_access()
        except Exception:
            continue
        break
    else:
        raise AssertionError('No existing authorized inventory editor')
    assert not business.su
    tag = receipt.fruit_tag_line_ids.package_id.filtered(lambda t: t.step_tag_state == 'validated')[:1]
    business['stock.quant.package'].browse(tag.id).check_access('write')
    session = http.root.session_store.new()
    session.update({'db':env.cr.dbname,'uid':candidate.id,'login':candidate.login,
        'context':dict(candidate.with_user(candidate).context_get(), allowed_company_ids=company.ids),
        'session_token':candidate._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    release = json.loads((Path(addon.__file__).resolve().parent.parent / 'release.json').read_text())
    assert release['versions'] == {'step_packing_producer_change': '18.0.1.1.1'}
    proof.write_text(json.dumps({'version':'18.0.1.1.1','backend_commit':release['commit'],'session_id':session.sid,'url':URL,'company_id':company.id,'user_id':candidate.id,
        'receipt':receipt.id,'receipt_name':receipt.name,'tag':tag.id,'tag_name':tag.name,
        'producer':receipt.partner_id.display_name,'tags':receipt.fruit_tag_line_ids.package_id.mapped('name'),
        'receipt_action':business.ref('step_packing_operations.menu_packing_reception_process').action.id,
        'tag_action':business.ref('step_inventory_packing.menu_steps_fruit_packages').action.id}))
    proof.chmod(0o600)
env.cr.rollback()
print('T246_REVIEW_SESSION_OK')
'''
header = 'PROOF=' + repr('/tmp/t246-browser-' + args.environment + '.json') + '\nCLEANUP=' + repr(args.cleanup) + '\nURL=' + repr(entry['url']) + '\n'
result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
    '-c', entry['config'], '-d', entry['database'], '--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=critical'],
    input=header + script, text=True, capture_output=True)
assert result.returncode == 0 and 'T246_REVIEW_SESSION_OK' in result.stdout, result.stderr[-2000:]
print('T246_REVIEW_SESSION_REMOVED' if args.cleanup else 'T246_REVIEW_SESSION_READY')
