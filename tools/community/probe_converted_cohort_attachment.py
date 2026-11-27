"""Exercise a restricted original payslip PDF through its ordinary attachment and company permissions."""
import hashlib

from odoo.exceptions import AccessError


def restricted_attachment(env, actor):
    companies = actor.company_ids.filtered("active")
    assert len(companies) > 1
    env.cr.execute("""
        SELECT a.id, p.id, p.company_id FROM ir_attachment a JOIN hr_payslip p
          ON a.res_model='hr.payslip' AND a.res_id=p.id
         WHERE a.type='binary' AND a.public IS NOT TRUE AND a.res_field IS NULL
           AND a.mimetype='application/pdf' AND a.file_size > 0 AND p.company_id=ANY(%s)
         ORDER BY a.id
    """, [companies.ids])
    candidates = env.cr.fetchall()
    for attachment_id, payslip_id, company_id in candidates:
        home = env(user=actor.id, su=False, context={"allowed_company_ids": [company_id], "bin_size": False})
        payslip = home["hr.payslip"].browse(payslip_id)
        if not payslip.has_access("read"):
            continue
        attachment = home["ir.attachment"].browse(attachment_id)
        try:
            attachment.check("read")
        except AccessError:
            continue
        for other_company in companies.ids:
            if other_company == company_id:
                continue
            away = env(user=actor.id, su=False, context={"allowed_company_ids": [other_company]})
            if away["hr.payslip"].browse(payslip_id).has_access("read"):
                continue
            try:
                away["ir.attachment"].browse(attachment_id).check("read")
            except AccessError:
                break
        else:
            continue
        raw = attachment.raw
        assert raw.startswith(b"%PDF-") and len(raw) == attachment.file_size
        assert hashlib.sha1(raw).hexdigest() == attachment.checksum
        public = env(user=env.ref("base.public_user").id, su=False)
        try:
            public["ir.attachment"].browse(attachment_id).check("read")
        except AccessError:
            pass
        else:
            raise AssertionError("public role admitted for a private payroll document")
        return {"restricted_pdf_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "payroll_reader": actor.id, "different_company_denied": True, "public_denied": True}
    raise AssertionError("no authorized original payslip with an excluded company context")
