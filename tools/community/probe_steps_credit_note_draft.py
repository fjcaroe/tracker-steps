"""Prepare Chilean customer credit notes through the original operator's invoice form in private Steps copies."""
import hashlib
import json
from pathlib import Path

from lxml import etree
from odoo import fields as odoo_fields
from odoo.tests import Form
from odoo.tools.safe_eval import safe_eval


NATIVE = "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
TRIAL = "COMMUNITY_STEPS_CRM_PAYMENTS_TEST_20261127U46D"
INTEGRATED = "COMMUNITY_STEPS_EXPENSE_20261127U50E"
REASON = "Prueba de preparación de nota de crédito"


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def financial_lines(move):
    data = []
    for line in move.line_ids.sorted(lambda row: (row.sequence, row.id)):
        data.append({
            "kind": line.display_type, "sequence": line.sequence, "account": line.account_id.id,
            "product": line.product_id.id, "unit": line.product_uom_id.id, "text": digest(line.name),
            "quantity": line.quantity, "unit_price": line.price_unit, "discount": line.discount,
            "taxes": sorted(line.tax_ids.ids), "tax_line": line.tax_line_id.id,
            "repartition": line.tax_repartition_line_id.id, "tags": sorted(line.tax_tag_ids.ids),
            "debit": line.debit, "credit": line.credit, "balance": line.balance,
            "amount_currency": line.amount_currency, "currency": line.currency_id.id,
            "subtotal": line.price_subtotal, "total": line.price_total,
        })
    return data


def draft(scope, move, *, correction=False, blank=False):
    form = etree.fromstring(move.get_view(view_id=scope.ref("account.view_move_form").id, view_type="form")["arch"])
    if not form.xpath('//button[@name="action_reverse"][@type="object"]'):
        move.web_read({"state": {}, "move_type": {}})
        return {"source": move.id, "invoice_readable": True, "credit_note_button": False}
    action = move.action_reverse()
    assert action["res_model"] == "account.move.reversal"
    context = {"active_model": move._name, "active_ids": move.ids, "active_id": move.id}
    defaults = action.get("context") or {}
    context.update(safe_eval(defaults, context) if isinstance(defaults, str) else defaults)
    wizard_model = scope[action["res_model"]].with_context(**context)
    view = etree.fromstring(wizard_model.get_view(view_type="form")["arch"])
    assert view.xpath('//button[@name="refund_moves"][@type="object"]')
    fields = sorted(k for k in wizard_model._fields if k.startswith("l10n_cl_"))
    inputs = {"reason": REASON}
    if correction:
        names = {"l10n_cl_is_text_correction", "l10n_cl_original_text", "l10n_cl_corrected_text"}
        if not names.issubset(wizard_model._fields):
            return {"unavailable": sorted(names.difference(wizard_model._fields))}
        inputs.update(l10n_cl_is_text_correction=True, l10n_cl_original_text=False if blank else "Texto de prueba anterior",
                      l10n_cl_corrected_text=False if blank else "Texto de prueba corregido")
    with Form(wizard_model) as form:
        for field, value in inputs.items():
            setattr(form, field, value)
    wiz = form.record
    assert wiz.move_ids == move and wiz.company_id == move.company_id and not scope.su
    wizard = {"model": wiz._name, "journal": wiz.journal_id.id, "companies": scope.companies.ids,
              "country": wiz.country_code, "today": wiz.date == odoo_fields.Date.context_today(wiz),
              "return_type": wiz.l10n_latam_document_type_id.code,
              "allowed_types": sorted(wiz.l10n_latam_available_document_type_ids.mapped("code")),
              "manual_number": wiz.l10n_latam_manual_document_number, "fields": fields,
              "on_form": sorted({n.get("name") for n in view.xpath('//field[starts-with(@name,"l10n_cl_")]')}),
              "reference_code": wiz["l10n_cl_edi_reference_doc_code"] if "l10n_cl_edi_reference_doc_code" in fields else None}
    target = wiz.refund_moves()
    assert target["res_model"] == "account.move" and target["view_mode"] == "form"
    note = scope["account.move"].browse(target["res_id"])
    note.web_read({k: {} for k in ("move_type","state","currency_id","reversed_entry_id","invoice_date","l10n_latam_document_type_id")})
    assert note.state == "draft" and note.move_type == "out_refund" and note.reversed_entry_id == move
    assert move.state == "posted" and not note.l10n_latam_document_number and note.name in (False, "/")
    assert not note.l10n_cl_dte_file and not note.l10n_cl_sii_barcode
    references = []
    for ref in note.l10n_cl_reference_ids:
        references.append({"type": ref.l10n_cl_reference_doc_type_id.code, "code": ref.reference_doc_code,
                           "date": str(ref.date), "number_matches_source": ref.origin_doc_number == move.l10n_latam_document_number,
                           "reason_matches_input": ref.reason == REASON, "reason_sha256": digest(ref.reason)})
    lines = financial_lines(note)
    return {"wizard": wizard, "state": note.state, "type": note.move_type, "source": move.id,
            "source_type": move.l10n_latam_document_type_id.code, "document_type": note.l10n_latam_document_type_id.code,
            "source_link": note in move.reversal_move_ids, "wizard_link": note in wiz.new_move_ids,
            "same_partner": note.partner_id == move.partner_id, "same_journal": note.journal_id == move.journal_id,
            "same_currency": note.currency_id == move.currency_id, "source_date": str(move.invoice_date),
            "lines": len(lines), "invoice_lines": len(note.invoice_line_ids), "line_values_sha256": digest(lines),
            "tax_lines": len(note.line_ids.filtered("tax_line_id")), "tax_totals_sha256": digest(note.tax_totals),
            "source_lines_sha256": digest(financial_lines(move)), "amounts_sha256": digest([note.amount_untaxed, note.amount_tax, note.amount_total]),
            "reference_text_sha256": digest(note.ref), "references": references, "folio_assigned": False}


def original_scope(env, uid):
    user = env["res.users"].browse(uid)
    assert user.active and not user.share
    return env(user=uid, su=False, context={"allowed_company_ids": [1], "lang": user.lang,
                                           "mail_notify_force_send": False, "tracking_disable": True})


def run(env):
    assert __debug__ and env.cr.dbname in (NATIVE, TRIAL, INTEGRATED)
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    domain = [("state", "=", "posted"), ("move_type", "=", "out_invoice")]
    evidence = {}
    comparisons = []
    original = original_scope(env, 10)["account.move"].search(domain, order="id").ids
    assert len(original) == 20
    try:
        for actor in (7, 10):
            scope = original_scope(env, actor)
            assert scope["account.move"].search(domain, order="id").ids == original
            for index, record_id in enumerate(original):
                move = scope["account.move"].browse(record_id)
                assert move.company_id.account_fiscal_country_id.code == "CL" and move.l10n_latam_document_type_id.code == "33"
                for correction in ((False, True) if actor == 10 else (False,)):
                    result = draft(scope, move, correction=correction)
                    comparisons.append([actor, record_id, correction, digest(result)])
                    if not index and actor == 10:
                        evidence["text_correction" if correction else "default"] = result
                    env.cr.rollback()
        evidence["blank_text"] = draft(original_scope(env, 10), original_scope(env, 10)["account.move"].browse(original[0]),
                                       correction=True, blank=True)
    finally:
        env.cr.rollback()
    evidence["operator_invoices"] = comparisons
    return evidence
