"""Read the existing SyS batch payment file through its original field and actor."""
import base64
import hashlib
import re


def probe(env, uid):
    cr = env.cr
    assert re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', cr.dbname)
    cr.execute("""SELECT r.id, r.company_id, a.id, a.file_size, a.checksum
                    FROM hr_payslip_run r JOIN ir_attachment a
                      ON a.res_model='hr.payslip.run' AND a.res_id=r.id AND a.res_field='payment_report'
                   ORDER BY r.id, a.id""")
    sources = cr.fetchall()
    assert sources
    reports = []
    for batch_id, company, attachment_id, size, checksum in sources:
        batches = env['hr.payslip.run'].with_user(uid).with_context(allowed_company_ids=[company], bin_size=False)
        assert not batches.env.su and batches.env.company.id == company
        batch = batches.browse(batch_id)
        batch.check_access('read')
        data, = batch.read(['payment_report', 'payment_report_filename', 'payment_report_date'])
        assert data['payment_report_filename'] and data['payment_report_date']
        saved = batches.env['ir.attachment'].browse(attachment_id)
        saved.check_access('read')
        raw = base64.b64decode(data['payment_report'], validate=True)
        assert size == len(raw) and hashlib.sha1(raw).hexdigest() == checksum and saved.raw == raw
        reports.append(dict(batch=batch.id, company=company, attachment=saved.id, size=size,
                            sha256=hashlib.sha256(raw).hexdigest(), date=str(data['payment_report_date']),
                            filename_sha256=hashlib.sha256(data['payment_report_filename'].encode()).hexdigest()))
    return dict(uid=uid, reports=reports)
