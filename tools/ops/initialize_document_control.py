"""Initialize missing T89 control rows with exact preservation of existing data."""
import argparse,configparser,fcntl,json,os,re,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('environment',choices=('development','cerro'))
p.add_argument('commit')
p.add_argument('--run-id',required=True)
p.add_argument('--live',action='store_true')
a=p.parse_args()
assert os.geteuid()==0 and re.fullmatch('[0-9a-f]{40}',a.commit) and re.fullmatch('[a-z0-9_]{1,24}',a.run_id)
target=json.loads(Path(__file__).with_name('environments.json').read_text())['environments'][a.environment]
stage=Path('/opt/steps-validation')/('management_'+a.environment+'_'+a.run_id)
assert json.loads((stage/'qa_passed.json').read_text())['commit']==a.commit
root=Path('/opt/steps-managed/releases')/a.environment/a.commit if a.live else stage/'addons'
assert json.loads((root/'release.json').read_text())['commit']==a.commit
cfg=configparser.ConfigParser(interpolation=None);cfg.read(target['config'])
user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
database=target['database'] if a.live else json.loads((stage/'qa_passed.json').read_text())['database']
code="""import json
try:
 env=env(context=dict(env.context,tracking_disable=True,mail_create_nosubscribe=True,mail_notrack=True))
 env.cr.execute('SELECT id FROM step_export_export ORDER BY id FOR UPDATE')
 shipments=env['step.export.export'].browse([row[0] for row in env.cr.fetchall()])
 env.cr.execute('SELECT id FROM step_export_shipping_document ORDER BY id FOR UPDATE')
 old_ids=[row[0] for row in env.cr.fetchall()]
 def ship_snapshot():
  env.cr.execute("SELECT COALESCE(jsonb_agg(to_jsonb(t)-'write_date' ORDER BY id),'[]') FROM step_export_export t")
  return env.cr.fetchone()[0]
 def old_documents():
  env.cr.execute("SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id),'[]') FROM step_export_shipping_document t WHERE id=ANY(%s)",[old_ids])
  return env.cr.fetchone()[0]
 before_ship,before_doc=ship_snapshot(),old_documents()
 before={s.id:set(s.documentation_ids.mapped('kind')) for s in shipments}
 types=set(env['step.export.document.type'].search([]).mapped('kind'))
 shipments.action_complete_document_control()
 env.flush_all()
 assert ship_snapshot()==before_ship,'A shipment value other than its update date changed'
 assert old_documents()==before_doc,'An existing documentation value changed'
 added=env['step.export.shipping.document'].search([('id','not in',old_ids)])
 for s in shipments:
  assert set(added.filtered(lambda d:d.shipment_id==s).mapped('kind'))==types-before[s.id]
 assert all(d.status=='pending' and not d.sent_on and not d.date for d in added)
 result={'commit':COMMIT,'shipments':len(shipments),'added_rows':len(added),'existing_documents_preserved':len(old_ids),'all_original_values_preserved':True,'added_ids':added.ids}
 if LIVE:env.cr.commit()
 print('DOCUMENT_CONTROL_INIT_OK '+json.dumps(result))
finally:env.cr.rollback()
"""
with open('/run/lock/steps-environments.lock','a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:args=command.read_bytes().decode(errors='replace').split('\x00')
        except OSError:continue
        if any(Path(arg).name=='odoo-bin' for arg in args):
            assert not any(arg in ('-i','-u','--update','--init') or arg.startswith(('--update=','--init=')) for arg in args)
    if a.live:
        assert json.loads((stage/'document_control_init_passed.json').read_text())['commit']==a.commit
        backup=Path('/opt/steps_backups')/('document_control_'+a.environment+'_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        shutil.copy2(target['config'],backup/'odoo.conf')
        with (backup/'database.dump').open('wb') as stream:
            subprocess.run(['sudo','-u','postgres','pg_dump','-Fc',database],stdout=stream,check=True)
    command=['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',target['config'],'-d',database,
        '--no-http','--workers=0','--max-cron-threads=0','--addons-path='+str(root)+','+cfg['options']['addons_path'],
        '--logfile=/tmp/steps-document-init-'+a.environment+'.log']
    result=subprocess.run(command,input='COMMIT='+repr(a.commit)+'\nLIVE='+repr(a.live)+'\n'+code,text=True,capture_output=True)
    match=re.search(r'DOCUMENT_CONTROL_INIT_OK (.+)',result.stdout)
    assert result.returncode==0 and match,result.stderr[-1800:]
    proof=json.loads(match[1])
    (backup/'initialization.json' if a.live else stage/'document_control_init_passed.json').write_text(json.dumps(proof))
    print(('DOCUMENT_CONTROL_INIT_LIVE_OK ' if a.live else 'DOCUMENT_CONTROL_INIT_COPY_OK ')+json.dumps(proof))
