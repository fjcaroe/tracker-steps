"""Apply one human-approved QA-Cerro date decision through native ORM.

Private plan: production_id, expected_name, previous_date, approved_date.
Fresh isolated clone, native business user, rollback rehearsal, full backup and
shared lease precede the same exact probe against the active training database.
No module upgrade, stock movement or refresh of customer exercises.
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

from customer_qa_clone_access import clone_database_access
from manage_management import query, tree_hash


PROBE = r'''
import json
from datetime import date
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment
try:
    scoped = scoped_business_environment(env)
    env.cr.execute('SELECT id FROM step_packing_production WHERE id=%s FOR UPDATE', [PLAN['production_id']])
    record = scoped['step.packing.production'].browse(PLAN['production_id']).exists()
    assert len(record) == 1 and record.name == PLAN['expected_name']
    assert record.company_id == scoped.company and record.state == 'validated'
    assert str(record.date) == PLAN['previous_date']
    assert str(record.step_legacy_process_date) == PLAN['approved_date']
    assert not record.step_previous_process_date
    menu = scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.action.res_model == record._name
    arch = etree.fromstring(record.get_view(view_type='form')['arch'])
    assert arch.xpath("//group[@name='ot_identity_left']/field[@name='date']")
    assert arch.xpath("//field[@name='step_previous_process_date']")
    versions = {}
    for module, version in [('step_packing_ticket_revision','18.0.1.0.0'),('step_packing_reception_revision','18.0.1.2.0')]:
        installed = env['ir.module.module'].search([('name','=',module)])
        assert installed.state == 'installed' and installed.latest_version == version
        versions[module] = version
    tags = scoped['stock.quant.package'].search([('step_packing_production_id','=',record.id)])
    field = tags._fields['step_packing_date']
    related = field.related.split('.') if isinstance(field.related,str) else field.related
    assert tuple(related) == ('step_packing_production_id','date'), repr(field.related)
    before = record.read(['date','step_previous_process_date','step_legacy_process_date','state'])[0]
    stock = {}
    for table in ('stock_quant','stock_move','stock_move_line','stock_quant_package','stock_picking'):
        env.cr.execute('SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,\'\' ORDER BY id),\'\')) FROM '+table+' t')
        stock[table] = env.cr.fetchone()
    env.cr.execute("SELECT md5(coalesce(string_agg((CASE WHEN id=%s THEN to_jsonb(t)-ARRAY['date','step_previous_process_date','write_uid','write_date'] ELSE to_jsonb(t) END)::text,'' ORDER BY id),'')) FROM step_packing_production t", [record.id])
    unchanged = env.cr.fetchone()
    record.with_context(tracking_disable=True,mail_notrack=True).write({
        'step_previous_process_date': record.date,
        'date': date.fromisoformat(PLAN['approved_date'])})
    env.flush_all()
    env.invalidate_all()
    assert str(record.date) == PLAN['approved_date']
    assert str(record.step_previous_process_date) == PLAN['previous_date']
    assert str(record.step_legacy_process_date) == PLAN['approved_date']
    assert record.state == 'validated'
    assert all(str(tag.step_packing_date) == PLAN['approved_date'] for tag in tags)
    # Also exercise the related projection when the OT has no output tags yet.
    virtual = scoped['stock.quant.package'].new({'step_packing_production_id': record.id})
    assert str(virtual.step_packing_date) == PLAN['approved_date']
    for table, expected in stock.items():
        env.cr.execute('SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,\'\' ORDER BY id),\'\')) FROM '+table+' t')
        assert env.cr.fetchone() == expected, 'Unexpected inventory change: '+table
    env.cr.execute("SELECT md5(coalesce(string_agg((CASE WHEN id=%s THEN to_jsonb(t)-ARRAY['date','step_previous_process_date','write_uid','write_date'] ELSE to_jsonb(t) END)::text,'' ORDER BY id),'')) FROM step_packing_production t", [record.id])
    assert env.cr.fetchone() == unchanged
    proof = {'database':env.cr.dbname,'user':scoped.uid,'company':scoped.company.id,
        'before':before,'after':record.read(['date','step_previous_process_date','step_legacy_process_date','state'])[0],
        'tags':tags.ids,'tag_dates':[str(t.step_packing_date) for t in tags],
        'native_menu_form':True,'versions':versions,'inventory_unchanged':True,'committed':COMMIT}
    if COMMIT:
        env.cr.commit()
        env.invalidate_all()
        assert str(record.date) == PLAN['approved_date']
        assert str(record.step_previous_process_date) == PLAN['previous_date']
        assert all(str(t.step_packing_date) == PLAN['approved_date'] for t in tags)
    else:
        env.cr.rollback()
    print('PACKING_DATE_DECISION_OK '+json.dumps(proof,default=str))
finally:
    env.cr.rollback()
'''


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    assert os.geteuid()==0
    plan=json.loads(args.plan.read_text())
    assert set(plan)=={'production_id','expected_name','previous_date','approved_date'}
    assert type(plan['production_id']) is int and plan['production_id']>0
    for key in ('previous_date','approved_date'):
        datetime.strptime(plan[key],'%Y-%m-%d')
    assert plan['previous_date'] != plan['approved_date']
    args.evidence.mkdir(parents=True,mode=0o700,exist_ok=False)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    clone='MANAGEMENT_QA_QA-CERRO_date'+stamp
    database='QA-CERROELPLOMO'; user='cerroqa_odoo18'
    conf=Path('/etc/odoo18-qa-cerroelplomo.conf')
    config=configparser.ConfigParser();config.read(conf);opts=config['options']
    assert opts['db_name']==database and opts['db_user']==user
    # Hash only actual addon directories, never unrelated repository/node trees.
    resolved={}
    for root in opts['addons_path'].split(','):
        for manifest in Path(root.strip()).glob('*/__manifest__.py'):
            resolved.setdefault(manifest.parent.name,manifest.parent)
    sources={str(path):tree_hash(path) for path in resolved.values()}
    baseline={'config':hashlib.sha256(conf.read_bytes()).hexdigest(),'sources':sources}
    # The probe imports only this reviewed helper; allow traversal of evidence.
    args.evidence.chmod(0o755)
    helper=args.evidence/'native_business_profile.py'
    helper.write_text(Path(__file__).with_name('native_business_profile.py').read_text())
    helper.chmod(0o644)
    def probe(db,commit):
        header='import sys\nsys.path.insert(0,'+repr(str(args.evidence))+')\nPLAN='+repr(plan)+'\nCOMMIT='+repr(commit)+'\n'
        result=subprocess.run(['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',str(conf),'-d',db,
            '--db-filter=^'+db+'$','--no-http','--workers=0','--max-cron-threads=0','--log-level=critical',
            ],input=header+PROBE,text=True,capture_output=True)
        (args.evidence/('live.log' if commit else 'clone.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0, result.stdout+result.stderr
        lines=[line.split('PACKING_DATE_DECISION_OK ',1)[1] for line in result.stdout.splitlines() if line.startswith('PACKING_DATE_DECISION_OK ')]
        assert len(lines)==1, result.stdout+result.stderr
        return json.loads(lines[0])
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        for entry in Path('/proc').glob('[0-9]*/cmdline'):
            try: argv=entry.read_bytes().decode(errors='replace').split('\0')
            except OSError: continue
            if any(Path(arg).name=='odoo-bin' for arg in argv):
                assert not any(arg in ('-u','-i','--update','--init') or arg.startswith(('--update=','--init=')) for arg in argv), 'Concurrent upgrade'
        with clone_database_access(query,clone,args.evidence):
            with (args.evidence/'source.dump').open('wb') as stream:
                os.fchmod(stream.fileno(),0o600)
                run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
            run('sudo','-u','postgres','createdb','-O',user,clone)
            query(clone,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with (args.evidence/'source.dump').open('rb') as stream:
                run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',user,'-d',clone,stdin=stream)
            query(clone,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            tested=probe(clone,False)
        assert baseline=={'config':hashlib.sha256(conf.read_bytes()).hexdigest(),'sources':{p:tree_hash(Path(p)) for p in sources}}
        backup=Path('/opt/steps_backups')/('packing_date_'+stamp)
        backup.mkdir(mode=0o700)
        with (backup/'source.dump').open('wb') as stream:
            run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
        run('sudo','-u','postgres','pg_restore','--list',str(backup/'source.dump'),stdout=subprocess.DEVNULL)
        (backup/'odoo.conf').write_bytes(conf.read_bytes())
        live=probe(database,True)
        assert tested['before']==live['before'] and tested['after']==live['after']
        proof={'plan':plan,'tested':tested,'live':live,'backup':str(backup),'baseline':baseline}
        (args.evidence/'decision.json').write_text(json.dumps(proof,indent=2))
        print('PACKING_DATE_CORRECTION_COMPLETE backup='+str(backup),flush=True)
    args.evidence.chmod(0o700)


if __name__=='__main__':main()
