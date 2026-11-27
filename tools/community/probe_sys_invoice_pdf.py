"""Render real posted Chilean invoices through the original report action on the isolated final cohort."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from unittest.mock import patch

from lxml import html
from odoo.tools import config
from PyPDF2 import PdfFileReader


def run(shell):
    steps = shell.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F','COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A')
    assert steps or shell.cr.dbname in ("COMMUNITY_SYS_FINAL_RESTORED_20261127U46R", "COMMUNITY_SYS_FISCAL_PRINT_20261127U45P", "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MW",
                               "COMMUNITY_SYS_PREVIRED_MODULES_20261127U43MF",
                               "MANAGEMENT_QA_SYS_PREVIRED_20261126U40N", "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FD", "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FG")
    url = os.environ["STEPS_PRIVATE_REPORT_URL"]
    assert re.fullmatch(r"http://127[.]0[.]0[.]1:[0-9]+", url)
    shell.cr.rollback()
    shell.cr.execute("SET TRANSACTION READ ONLY")
    service = shell["ir.actions.report"]
    parameters = type(shell["ir.config_parameter"])
    original_param = parameters.get_param

    def get_param(records, key, default=False):
        if key in ("report.url", "web.base.url"):
            return url
        return original_param(records, key, default)

    directory = Path(tempfile.mkdtemp(prefix="historical-invoice-pdf-", dir=config["data_dir"]))
    actors = shell["res.users"].search([("active", "=", True), ("share", "=", False), ("id", ">", 1)])
    if steps:
        actors = actors.filtered(lambda user: user.id in (7, 10))
        assert set(actors.ids) == {7, 10}
    assert len(actors) == 2
    result = []
    extractor = Path(shutil.which("gs")).resolve(strict=True)
    renderer = type(service)._run_wkhtmltopdf
    calls = []

    def physical(instance, *args, **kwargs):
        pdf = renderer(instance, *args, **kwargs)
        calls.append(hashlib.sha256(pdf).hexdigest())
        return pdf

    with patch.object(parameters, "get_param", get_param), patch.object(type(service), "_run_wkhtmltopdf", physical):
        for actor in actors:
            for move_type in ("out_invoice", "out_refund"):
                found = False
                for company in actor.company_ids.filtered("active"):
                    scope = shell(user=actor.id, su=False, context={"allowed_company_ids": [company.id], "lang": actor.lang if steps else "es_CL"})
                    domain = [("company_id", "=", company.id), ("move_type", "=", move_type), ("state", "=", "posted"),
                              ("l10n_latam_document_type_id", "!=", False)]
                    if move_type == "out_refund":
                        domain.append(("l10n_cl_reference_ids", "!=", False))
                    move = scope["account.move"].search(domain, order="id", limit=1)
                    if not move:
                        continue
                    move.check_access("read")
                    billing = scope.user.has_group("account.group_account_invoice")
                    rights = {mode: bool(scope["ir.model.access"].check("l10n_cl.account.invoice.reference", mode,
                                                                        raise_exception=False))
                              for mode in ("read", "write", "create", "unlink")}
                    assert rights == {"read": True, "write": billing, "create": billing, "unlink": billing}
                    report = scope["ir.actions.report"].with_context(force_report_rendering=True, report_pdf_no_attachment=True)
                    rendered, fmt = report._render_qweb_html("account.account_invoices", move.ids)
                    article, = html.fromstring(rendered).xpath('//*[contains(concat(" ",normalize-space(@class)," ")," article ")]')
                    assert fmt == "html" and article.get("data-oe-id") == str(move.id) and article.get("data-oe-model") == "account.move"
                    article_text = " ".join(article.text_content().split())
                    article_words = set(re.findall(r"\w+", article_text.casefold()))
                    count_before = len(calls)
                    pdf, kind = report._render_qweb_pdf("account.account_invoices", res_ids=move.ids)
                    assert kind == "pdf" and pdf.startswith(b"%PDF-") and len(calls) == count_before + 1
                    text = subprocess.run([str(extractor), "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=txtwrite",
                                           "-dTextFormat=3", "-sOutputFile=-", "-"],
                                          input=pdf, check=True, capture_output=True).stdout.decode()
                    printed_words = set(re.findall(r"\w+", text.casefold()))
                    assert len(article_words) > 15 and len(article_words & printed_words) >= 0.8 * len(article_words)
                    assert all(ref.origin_doc_number in text for ref in move.l10n_cl_reference_ids)
                    pages = PdfFileReader(io.BytesIO(pdf)).getNumPages()
                    assert pages > 0
                    output = directory / ("%s-%s.pdf" % (actor.id, move_type))
                    with output.open("xb") as handle:
                        handle.write(pdf)
                    output.chmod(0o600)
                    result.append({"actor": actor.id, "kind": move_type, "pages": pages, "reference_permissions": rights,
                                   "references": len(move.l10n_cl_reference_ids), "bytes": len(pdf),
                                   "document": move.id, "company": company.id,
                                   "article_text_sha256": hashlib.sha256(article_text.encode()).hexdigest(),
                                   "pdf_text_sha256": hashlib.sha256(" ".join(text.split()).encode()).hexdigest(),
                                   "article_words": len(article_words), "printed_article_words": len(article_words & printed_words),
                                   "sha256": hashlib.sha256(pdf).hexdigest(), "private_file": str(output)})
                    found = True
                    break
                assert found
    assert len(result) == len(calls) == 4
    binary = Path(shutil.which("wkhtmltopdf")).resolve()
    shell.cr.rollback()
    return {"original_report": "account.account_invoices", "authenticated_operator_count": len(actors),
            "renderer_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
            "text_extractor_sha256": hashlib.sha256(extractor.read_bytes()).hexdigest(), "printed": result}
