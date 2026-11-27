"""Collect original Chilean invoice reference output without returning document text or signature bytes."""
import hashlib

from probe_sys_retained_provider_release import invoice_text


def run(shell):
    assert shell.cr.dbname == "MANAGEMENT_QA_SYS_PREVIRED_20261126U40N"
    shell.cr.rollback()
    shell.cr.execute("SET TRANSACTION READ ONLY")
    shell.cr.execute("""SELECT r.id,r.move_id,m.company_id FROM l10n_cl_account_invoice_reference r
                        JOIN account_move m ON m.id=r.move_id WHERE m.state='posted' ORDER BY r.id""")
    rows = shell.cr.fetchall()
    actors = shell["res.users"].search([("active", "=", True), ("share", "=", False), ("id", ">", 1)])
    assert len(actors) == 2 and len(rows) == 6
    result = []
    for user in actors:
        for ref_id, move_id, company in rows:
            if company not in user.company_ids.ids:
                continue
            scope = shell(user=user.id, su=False, context={"allowed_company_ids": [company], "lang": "es_CL"})
            move = scope["account.move"].browse(move_id)
            ref = scope["l10n_cl.account.invoice.reference"].browse(ref_id)
            move.check_access("read")
            ref.check_access("read")
            assert ref in move.l10n_cl_reference_ids
            visible, size = invoice_text(scope, move)
            result.append({"actor": user.id, "ref": ref.id, "html_bytes": size, "text_length": len(visible),
                           "text_sha256": hashlib.sha256(visible.encode()).hexdigest(),
                           "original_ref_printed": ref.origin_doc_number in visible,
                           "original_reason_printed": not ref.reason or " ".join(ref.reason.split()) in visible})
    assert len(result) == 12 and all(v["original_ref_printed"] and v["original_reason_printed"] for v in result)
    shell.cr.rollback()
    return result
