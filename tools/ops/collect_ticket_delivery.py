"""Collect exact-package functional, publication and Cerro pair evidence."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('ticket',type=int,choices=(142,143,144,145,146,147,148,149,150,151,152,153));p.add_argument('output',type=Path)
    p.add_argument('--target',action='append',required=True,help='environment:run_id:/tmp/live.log')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True,mode=0o700)
    module={142:'step_purchase_holding',143:'step_payroll_attendance_correction',144:'step_packing_tag_company',145:'step_export_branch_consolidation',146:'step_bpa_master_import',147:'step_packing_holding',148:'step_producer_holding',149:'step_packing_holding',150:'step_export_receiver_profile',151:'step_packing_overweight',152:'step_inventory_packing',153:'step_packing_reception_revision'}[a.ticket]
    required={'development','cerro','qa-cerro'} | ({'sys'} if a.ticket==143 else set())
    seen=set();identities=set();count=0
    for entry in a.target:
        target,run_id,live_path=entry.split(':',2)
        assert target in required and target not in seen and re.fullmatch('[a-z0-9_]{1,24}',run_id)
        seen.add(target);stage=Path('/opt/steps-validation')/('management_'+target+'_'+run_id)
        qa_file=stage/'qa_passed.json';qa=json.loads(qa_file.read_text());test=Path(qa['log'])
        matches=re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database',test.read_text())
        assert matches and int(matches[-1])>=(20 if a.ticket>=147 else {142:4,143:5,144:3,145:5,146:5}[a.ticket])
        count+=int(matches[-1]);flow=stage/('verify-'+qa['database']+'.log')
        assert 'MANAGEMENT_REGISTRY_OK' in flow.read_text()
        if a.ticket==153:
            assert 'T153_MANUAL_SUMMARY_FORM_OK' in flow.read_text()
            if target=='cerro':
                assert 'T153_REPORTED_RECEIPT_OK' in flow.read_text()
        if a.ticket==152: assert 'T152_OPERATOR_VARIETIES_FLOW_OK' in flow.read_text()
        if a.ticket==143 and target=='sys':
            assert 'T143_REPORTED_CONFIRMED_CASE_PROTECTED no_business_changes=True' in flow.read_text()
        live=Path(live_path);text=live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in text
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in text.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(row.get('existing_profile',1)!=1 and row.get('writes') is False for row in payloads)
        backup=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',text);assert len(backup)==1
        deployment=Path(backup[0])/'deployment.json';d=json.loads(deployment.read_text())
        assert d['commit']==qa['commit'] and d['sha256']==qa['release_sha256']
        identities.add((qa['commit'],qa['release_sha256']))
        for suffix,source in [('qa.json',qa_file),('qa.log',test),('flow.log',flow),('live.log',live),('deployment.json',deployment)]:
            shutil.copyfile(source,a.output/(target+'-'+suffix))
    assert seen==required and len(identities)==1
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        result=subprocess.run(['/usr/bin/python3.10','-c','from provision_cerro_qa import verify; verify()'],
            cwd=Path(__file__).resolve().parent,capture_output=True,text=True,check=True)
        isolation=result.stdout+result.stderr
        assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
        assert 'STEPS_PRIVATE_REPORT_' not in subprocess.check_output(['/usr/sbin/iptables','-S','OUTPUT'],text=True)
        (a.output/'isolation.log').write_text(isolation)
        modules=('step_inventory_packing','step_packing_reception_revision','step_producer_fruit_flow','step_producer_fruit_reports','step_agro_analytics','step_packing_reception_report') if a.ticket==152 else ('step_packing_holding','step_producer_holding','step_export_receiver_profile','step_packing_overweight') if 147<=a.ticket<=151 else (module,)
        command=['/usr/bin/python3.10',str(Path(__file__).with_name('verify_cerro_release_pair.py'))]
        for name in modules: command+=['--module',name]
        result=subprocess.run(command+['--output',str(a.output/'pair.json')],capture_output=True,text=True,check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (a.output/'pair.log').write_text(result.stdout)
    commit,sha=identities.pop()
    reviewed={str(ticket):ident for ticket,ident in {147:9930,148:9934,149:9938,150:9942,151:9946}.items()} if a.ticket>=147 else {str(a.ticket):{142:9873,143:9877,144:9881,145:9885,146:9916}[a.ticket]}
    if a.ticket==152: reviewed={'152':9961}
    if a.ticket==153: reviewed={'153':9967}
    (a.output/'delivery.json').write_text(json.dumps({'ticket':a.ticket,'module':module,'commit':commit,'sha256':sha,
        'tests':count,'environments':sorted(required),'reviewed_messages':reviewed}))
    print('TICKET_DELIVERY_COLLECTED ticket='+str(a.ticket)+' tests='+str(count))


if __name__=='__main__':main()
