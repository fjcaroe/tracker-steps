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


def original_library_payslip(env, actor, expected):
    slip_id, document_id, attachment_id, size, checksum = expected
    env.cr.execute("SELECT company_id FROM hr_payslip WHERE id=%s", [slip_id])
    company, = env.cr.fetchone()
    scope = env(user=actor.id, su=False, context={"allowed_company_ids":[company], "bin_size":False})
    slip = scope["hr.payslip"].browse(slip_id)
    doc = scope["documents.document"].browse(document_id)
    attachment = scope["ir.attachment"].browse(attachment_id)
    slip.check_access("read")
    doc.check_access("read")
    attachment.check("read")
    assert not scope.su and doc.folder_id and doc.attachment_id == attachment and attachment.res_id == slip.id
    assert attachment.res_model == doc.res_model == "hr.payslip" and doc.res_id == slip.id
    assert doc.action_open()["url"] == "/web/content/%d?download=true" % attachment.id
    raw = attachment.raw
    assert raw.startswith(b"%PDF-") and len(raw) == size and hashlib.sha256(raw).hexdigest() == checksum
    return {"bytes":size, "sha256":checksum, "same_document_and_payslip":True, "ordinary_manager":actor.id}
