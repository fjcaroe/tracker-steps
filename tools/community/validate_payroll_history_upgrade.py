"""Exercise actual 1.0 -> 1.1 OCA upgrade admission and original-value adoption.

A synthetic, real-engine private fixture is not certification of customer history.
No production mode, expiry changes, parallel models or invented payroll values.
"""
import argparse
import ast
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess


def run(*args,**kw):return subprocess.run(args,check=True,**kw)


def sql(db,query):
    return run('sudo','-u','postgres','psql','-XAt','-v','ON_ERROR_STOP=1','-d',db,
               input=query,text=True,capture_output=True).stdout.strip()


def payroll_rows(env,slip_id):
    data={}
    for name,where in (('hr_payslip','id'),('hr_payslip_line','slip_id'),('hr_payslip_worked_days','payslip_id')):
        env.cr.execute("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]'::jsonb) FROM "+name+' t WHERE '+where+'=%s',(slip_id,))
        data[name]=env.cr.fetchone()[0]
    env.cr.execute('SELECT move_id FROM hr_payslip WHERE id=%s',(slip_id,))
    move_id=env.cr.fetchone()[0]
    if move_id:
        for table,column in (('account_move','id'),('account_move_line','move_id')):
            env.cr.execute("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]'::jsonb) FROM "+table+' t WHERE '+column+'=%s',(move_id,))
            data[table]=env.cr.fetchone()[0]
    return data


def exercise(env,mode,root):
    """Runs through Odoo shell against real models, using a normal payroll actor."""
    from odoo import api
    from odoo.exceptions import UserError
    assert re.fullmatch('COMMUNITY_PAYROLL_API_HISTORY_UPGRADE_[A-Za-z0-9_]+',env.cr.dbname)
    root=Path(root);path=root/'seed.json'
    if mode=='seed':
        from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
        class FixtureBase:
            @classmethod
            def setUpClass(cls):pass
        class Fixture(PayrollContractMixin,FixtureBase):
            payroll_group='payroll.group_payroll_manager'
            oca=True
        # Finish the real company's chart precommit before creating salary journals.
        # TransactionCase normally settles these callbacks; this probe uses a real cursor.
        from unittest.mock import patch
        company_class=type(env['res.company']);original_create=company_class.create
        def create_ready_company(records,values):
            company=original_create(records,values)
            records.env.cr.flush()
            return company
        Fixture.env=env
        with patch.object(company_class,'create',create_ready_company):Fixture.setUpClass()
        case=Fixture()
        case.rule.code='BASIC'
        case.rule.copy({'code':'GROSS','sequence':2,'amount_python_compute':"result = result_rules['BASIC']['total']"})
        case.rule.copy({'code':'NET','sequence':3,'amount_python_compute':"result = result_rules['GROSS']['total']"})
        slip=case.slip()
        kind=case.scope['hr.work.entry.type'].create({'name':'Private upgrade attendance','code':'PRIVATE_UPGRADE'})
        day=case.scope['hr.payslip.worked_days'].create({'name':kind.name,'code':kind.code,'payslip_id':slip.id,
            'contract_id':case.contract.id,'work_entry_type_id':kind.id,'number_of_days':2,'number_of_hours':16})
        slip.compute_sheet()
        # Capture authentic values while draft. Never derive closed history after the fact.
        amounts={name:slip[name] for name in ('basic_wage','gross_wage','net_wage')}
        days={'amount':day.amount,'is_paid':day.is_paid}
        slip.action_payslip_done();slip.paid=True;env.flush_all()
        assert slip.move_id and not case.scope.su
        assert abs(sum(slip.move_id.line_ids.mapped('balance')))<0.00001
        env.cr.execute("SELECT model||'.'||name,id FROM ir_model_fields WHERE model IN ('hr.payslip','hr.payslip.line','hr.payslip.worked_days')")
        fields=dict(env.cr.fetchall())
        data={'actor':case.scope.uid,'company':case.company.id,'contract':case.contract.id,'slip':slip.id,'day':day.id,
              'amounts':amounts,'days':days,'original_rows':payroll_rows(env,slip.id),'field_ids':fields}
        path.write_text(json.dumps(data,indent=2),encoding='utf-8');env.cr.commit()
    else:
        seed=json.loads(path.read_text(encoding='utf-8'))
        scope=api.Environment(env.cr,seed['actor'],{'allowed_company_ids':[seed['company']]},su=False)
        slip=scope['hr.payslip'].browse(seed['slip']);day=scope['hr.payslip.worked_days'].browse(seed['day'])
        assert slip.step_history_locked and not scope.su
        assert {name:slip[name] for name in seed['amounts']}==seed['amounts']
        assert {name:day[name] for name in seed['days']}==seed['days']
        scope['hr.contract'].browse(seed['contract']).wage=1200000
        env.flush_all();slip.invalidate_recordset();day.invalidate_recordset()
        assert {name:slip[name] for name in seed['amounts']}==seed['amounts']
        assert {name:day[name] for name in seed['days']}==seed['days']
        current=payroll_rows(env,slip.id)
        for table,rows in seed['original_rows'].items():
            now={row['id']:row for row in current[table]}
            assert all(all(now[row['id']].get(k)==v for k,v in row.items()) for row in rows),table
        env.cr.execute("SELECT model||'.'||name,id FROM ir_model_fields WHERE model IN ('hr.payslip','hr.payslip.line','hr.payslip.worked_days')")
        now=dict(env.cr.fetchall());assert all(now.get(k)==v for k,v in seed['field_ids'].items())
        try:slip.compute_sheet()
        except UserError:pass
        else:raise AssertionError('Closed payroll recomputed')
        (root/'verified.json').write_text(json.dumps({'real_engine':True,'normal_actor':True,'field_ids_preserved':len(seed['field_ids']),
            'original_payroll_rows_preserved':True,'historical_values_preserved':True,'closure_marked_by_upgrade':True,
            'synthetic_fixture_only':True,'full_cerro_conversion':False},indent=2),encoding='utf-8')
        env.cr.rollback()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('root','legacy','candidate','runtime','oca'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--database',required=True);a=p.parse_args()
    assert os.geteuid()==0 and str(a.root.resolve()).startswith('/opt/steps-validation/') and not a.root.exists()
    assert re.fullmatch('COMMUNITY_PAYROLL_API_HISTORY_UPGRADE_[A-Za-z0-9_]+',a.database)
    for folder,expected in ((a.legacy,'18.0.1.0.0'),(a.candidate,'18.0.1.1.0')):
        assert ast.literal_eval((folder/'step_simpledigital_oca_base/__manifest__.py').read_text())['version']==expected
    for folder,url,pin in ((a.runtime,'https://github.com/odoo/odoo.git','4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'),(a.oca,'https://github.com/OCA/payroll.git','4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e')):
        assert run('git','-C',str(folder),'remote','get-url','origin',capture_output=True,text=True).stdout.strip()==url
        assert run('git','-C',str(folder),'rev-parse','HEAD',capture_output=True,text=True).stdout.strip()==pin
        assert not run('git','-C',str(folder),'status','--porcelain',capture_output=True,text=True).stdout.strip()
    cfg=configparser.ConfigParser(interpolation=None);assert cfg.read('/etc/dev_odoo18.conf')
    owner=pwd.getpwnam('odoo');a.root.mkdir(mode=0o750);os.chown(a.root,owner.pw_uid,owner.pw_gid)
    def execute(label,folder,flags,inp=None):
        paths=','.join(map(str,(folder,a.oca,a.runtime/'addons')))
        command=['sudo','-u','odoo','/usr/bin/python3.10',str(a.runtime/'odoo-bin')]
        if inp is not None:command+=['shell']
        command+=['-c','/etc/dev_odoo18.conf','-d',a.database,'--db-filter=^'+a.database+'$',
            '--addons-path='+paths,'--data-dir='+str(a.root/'data'),'--load=base,web','--workers=0',
            '--max-cron-threads=0','--no-http','--without-demo=','--logfile='+str(a.root/(label+'.log'))]+flags
        with (a.root/(label+'-bootstrap.log')).open('w') as out:
            result=subprocess.run(command,input=inp,text=True,stdout=out,stderr=subprocess.STDOUT)
        return result.returncode,(a.root/(label+'.log')).read_text(errors='replace')
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert not sql('postgres',"SELECT 1 FROM pg_database WHERE datname='"+a.database+"'")
        run('sudo','-u','postgres','createdb','--owner='+cfg['options']['db_user'],a.database)
        status,log=execute('legacy-install',a.legacy,['-i','step_simpledigital_oca_security','--stop-after-init'])
        assert status==0 and not re.search(r' (ERROR|CRITICAL) ',log)
        seed_command="import runpy; runpy.run_path("+repr(str(Path(__file__).resolve()))+")['exercise'](env,'seed',"+repr(str(a.root))+")"
        status,log=execute('seed',a.legacy,[],seed_command);assert status==0 and not re.search(r' (ERROR|CRITICAL) ',log)
        assert sql(a.database,"SELECT latest_version FROM ir_module_module WHERE name='step_simpledigital_oca_base'")=='18.0.1.0.0'
        before=json.loads((a.root/'seed.json').read_text())
        status,log=execute('rejected-upgrade',a.candidate,['-u','step_simpledigital_oca_base','--stop-after-init'])
        assert status!=0 and 'Adopt original stored payroll snapshots' in log
        assert sql(a.database,"SELECT latest_version FROM ir_module_module WHERE name='step_simpledigital_oca_base'")=='18.0.1.0.0'
        # Import only original, independently captured values into the SAME existing columns/IDs.
        for table,row_id,values in (('hr_payslip',before['slip'],before['amounts']),('hr_payslip_worked_days',before['day'],before['days'])):
            original=before['original_rows'][table]
            actual=json.loads(sql(a.database,'SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM '+table+' t WHERE '+('id' if table=='hr_payslip' else 'payslip_id')+'='+str(before['slip'])))
            assert actual==original,'Failed upgrade changed original history'
            for name,value in values.items():
                present=sql(a.database,"SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='"+table+"' AND column_name='"+name+"'")
                if not present:sql(a.database,'ALTER TABLE '+table+' ADD COLUMN '+name+(' boolean' if name=='is_paid' else ' numeric'))
                literal=('true' if value else 'false') if isinstance(value,bool) else str(value)
                existing=sql(a.database,'SELECT '+name+' IS NOT DISTINCT FROM '+literal+' OR '+name+' IS NULL FROM '+table+' WHERE id='+str(row_id))
                assert existing=='t','Conflicting original snapshot value'
                sql(a.database,'UPDATE '+table+' SET '+name+'='+literal+' WHERE id='+str(row_id)+' AND '+name+' IS NULL')
        status,log=execute('accepted-upgrade',a.candidate,['-u','step_simpledigital_oca_base','--stop-after-init'])
        assert status==0 and not re.search(r' (ERROR|CRITICAL) ',log)
        assert sql(a.database,"SELECT latest_version FROM ir_module_module WHERE name='step_simpledigital_oca_base'")=='18.0.1.1.0'
        verify_command=seed_command.replace("'seed'","'verify'")
        status,log=execute('verify',a.candidate,[],verify_command);assert status==0 and not re.search(r' (ERROR|CRITICAL) ',log)
        assert sql(a.database,"SELECT count(*) FROM ir_module_module WHERE state='installed' AND license='OEEL-1'")=='0'
        proof=json.loads((a.root/'verified.json').read_text());proof.update(rejected_missing_snapshots=True,actual_upgrade=True,
            original_version='18.0.1.0.0',target_version='18.0.1.1.0',writes_to_source=False,
            probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        (a.root/'passed.json').write_text(json.dumps(proof,indent=2),encoding='utf-8');print(json.dumps(proof))


if __name__=='__main__':main()
