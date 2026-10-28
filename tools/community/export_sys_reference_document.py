"""Export one existing closed-slip PDF, without generating a report or reading ORM.

Output contains private payroll/identity data. Never commit it or a text/image
derivative. Attachment dates and a checksum alone do not prove historical wage.
"""
import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capsule',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    assert os.geteuid()==0
    assert str(a.capsule.resolve()).startswith('/opt/steps-validation/')
    assert str(a.output.resolve()).startswith('/opt/steps-validation/') and not a.output.exists()
    cfg=configparser.ConfigParser(interpolation=None)
    assert cfg.read('/etc/odoo18-sys.conf') and cfg['options']['db_name']=='SyS'
    capsule=json.loads(a.capsule.read_text());assert capsule['reference']=='sys_user_approved'
    ident=int(capsule['selected_case']['id'])
    def query(sql):
        return subprocess.check_output(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
            'psql','-XAt','-v','ON_ERROR_STOP=1','-d','SyS','-c',sql],text=True).strip()
    assert query('SHOW default_transaction_read_only')=='on'
    assert query('SELECT state FROM hr_payslip WHERE id='+str(ident)) in ('done','paid')
    rows=json.loads(query("SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'checksum',checksum,'store_fname',store_fname,'create_date',create_date,'write_date',write_date,'file_size',file_size) ORDER BY id),'[]'::jsonb) FROM ir_attachment WHERE res_model='hr.payslip' AND res_id="+str(ident)+" AND mimetype='application/pdf'"))
    assert len(rows)==1,'Require one unambiguous existing PDF'
    row=rows[0];store=(Path(cfg['options']['data_dir'])/'filestore/SyS').resolve()
    source=(store/row['store_fname']).resolve()
    assert source.is_relative_to(store) and source.is_file()
    raw=source.read_bytes()
    assert raw.startswith(b'%PDF-') and len(raw)==row['file_size']
    assert hashlib.sha1(raw).hexdigest()==row['checksum']
    a.output.mkdir(mode=0o700)
    (a.output/'reference.pdf').write_bytes(raw);os.chmod(a.output/'reference.pdf',0o600)
    proof={'read_only':True,'orm_reads':False,'report_generated':False,'payroll_computed':False,
        'financial_certified':False,'historical_wage_proven':False,'contains_private_identity_and_payroll_data':True,
        'capsule_sha256':hashlib.sha256(a.capsule.read_bytes()).hexdigest(),
        'exporter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'attachment':row,'pdf_sha256':hashlib.sha256(raw).hexdigest()}
    (a.output/'document-proof.json').write_text(json.dumps(proof,indent=2))
    print('EXISTING_PRIVATE_SYS_PDF_EXPORTED checksum_verified=True historical_wage_proven=False')


if __name__=='__main__':main()
