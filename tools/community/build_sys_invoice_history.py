"""Bind the original SyS Chilean invoice reference contract to its free accounting provider."""
import json
from itertools import product
from pathlib import Path
from pprint import pformat
import shutil

from custody_sys_previred_filestore import digest
from restore_native_product_backup import query
from restore_sys_previred_pair import require


REFERENCE = "l10n_cl.account.invoice.reference"
NATIVE = "MANAGEMENT_QA_SYS_PREVIRED_20261126U40N"
FIELDS = {
    8286: ("account.move", "l10n_cl_sii_barcode", "char", None),
    8296: ("account.move", "l10n_cl_reference_ids", "one2many", REFERENCE),
    8305: (REFERENCE, "origin_doc_number", "char", None),
    8306: (REFERENCE, "reference_doc_code", "selection", None),
    8307: (REFERENCE, "l10n_cl_reference_doc_type_id", "many2one", "l10n_latam.document.type"),
    8308: (REFERENCE, "l10n_cl_reference_doc_internal_type", "selection", None),
    8309: (REFERENCE, "reason", "char", None),
    8310: (REFERENCE, "move_id", "many2one", "account.move"),
    8311: (REFERENCE, "date", "date", None),
    8347: ("res.company", "l10n_cl_dte_resolution_number", "char", None),
    8348: ("res.company", "l10n_cl_dte_resolution_date", "date", None),
}


def build_invoice_provider(db, output):
    def original(sql):
        native = query(NATIVE, sql)
        require(query(db, sql) == native, "native-invoice-reference-contract-differs")
        return json.loads(native)

    ids = ",".join(str(pk) for pk in FIELDS)
    rows = original(f"""SELECT json_agg(json_build_array(f.id,f.model,f.name,f.ttype,f.relation,
        f.related,f.relation_field,f.required,f.store,f.on_delete,f.field_description->>'en_US',f.help->>'en_US') ORDER BY f.id)
        FROM ir_model_fields f JOIN ir_model_data d ON d.res_id=f.id AND d.model='ir.model.fields'
        WHERE d.module='l10n_cl_edi' AND f.id IN ({ids})""")
    require({row[0]: tuple(row[1:5]) for row in rows} == FIELDS, "unexpected-native-reference-fields")
    inverse = next(r for r in rows if r[0] == 8296)
    require(inverse[6] == "move_id" and next(r for r in rows if r[0] == 8310)[9] == "cascade",
            "unexpected-native-invoice-reference-inverse")
    model = original("""SELECT json_build_array(id,name->>'en_US') FROM ir_model WHERE
                     model='l10n_cl.account.invoice.reference'""")
    require(model[0] == 639, "unexpected-reference-model")
    access = original("""SELECT json_agg(json_build_array(a.id,g.module||'.'||g.name,a.active,a.perm_read,
               a.perm_write,a.perm_create,a.perm_unlink) ORDER BY a.id) FROM ir_model_access a
               JOIN ir_model_data g ON g.model='res.groups' AND g.res_id=a.group_id WHERE model_id=639""")
    require({tuple(row[1:]) for row in access} == {("base.group_user", True, True, False, False, False),
            ("account.group_account_invoice", True, True, True, True, True)}, "unexpected-reference-access")
    require(original("SELECT to_json(count(*)) FROM ir_rule WHERE model_id=639") == 0, "unexpected-reference-rules")
    record_hash = original("""SELECT json_build_array(count(*),count(DISTINCT move_id),
            md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY id))) FROM l10n_cl_account_invoice_reference t""")
    require(record_hash[:2] == [6, 6], "unexpected-original-reference-rows")
    fields = original("""SELECT json_agg(json_build_array(id,model,name,ttype,relation,relation_table,column1,column2)
                 ORDER BY id) FROM ir_model_fields WHERE id IN (5963,6077)""")
    require(fields == [[5963, "account.reconcile.model.line", "tax_ids", "many2many", "account.tax",
                       "account_reconcile_model_line_account_tax_rel", "account_reconcile_model_line_id", "account_tax_id"],
                       [6077, "account.move.line", "account_id", "many2one", "account.account", None, None, None]],
            "original-financial-relation-fields-differ")
    original_fk = query(NATIVE, """SELECT string_agg(confdeltype::text,',' ORDER BY conname) FROM pg_constraint
                  WHERE conname IN ('account_move_line_account_id_fkey','account_reconcile_model_line_account_tax_re_account_tax_id_fkey')""")
    require(original_fk == "c,r" and query(NATIVE, "SELECT on_delete FROM ir_model_fields WHERE id=6077") == "cascade",
            "original-posted-account-deletion-contract-differs")
    choices = original("""SELECT json_agg(json_build_array(value,name->>'en_US') ORDER BY sequence)
                       FROM ir_model_fields_selection WHERE field_id=8306""")
    require([k for k, text in choices] == ["1", "2", "3"], "unexpected-historical-reference-codes")
    labels = {"model": model[1], "codes": [tuple(c) for c in choices]}
    for row in rows:
        labels[row[2]] = {"string": row[10]}
        if row[11]:
            labels[row[2]]["help"] = row[11]
    signing_ids = {
        7115: ("account.move", "signing_user", "many2one", "res.users", True),
        7116: ("account.move", "show_signature_area", "boolean", None, False),
        7117: ("account.move", "signature", "binary", None, False),
        7144: ("res.company", "sign_invoice", "boolean", None, True),
        7145: ("res.company", "signing_user", "many2one", "res.users", True),
        18010: ("res.users", "sign_signature", "binary", None, True),
    }
    names = ",".join(map(str, signing_ids))
    sign_fields = original(f"""SELECT json_agg(json_build_array(f.id,f.model,f.name,f.ttype,f.relation,f.store,
        f.field_description->>'en_US') ORDER BY f.id) FROM ir_model_fields f JOIN ir_model_data d
        ON d.model='ir.model.fields' AND d.res_id=f.id AND d.module IN ('account_accountant','sign') WHERE f.id IN ({names})""")
    require({r[0]: tuple(r[1:6]) for r in sign_fields} == signing_ids, "unexpected-stored-invoice-signatory-model")
    for pk, model, name, ttype, relation, stored, label in sign_fields:
        labels[model + "." + name] = {"string": label}
    sign_rules = original(f"SELECT to_json(count(*)) FROM ir_model_fields_group_rel WHERE field_id IN ({names})")
    require(sign_rules == 0, "unexpected-signing-field-group-policy")
    flags = original("""SELECT json_build_array(count(*),count(*) FILTER (WHERE sign_invoice),count(signing_user))
                     FROM res_company""")
    signers = original("""SELECT json_build_array(count(*),count(signing_user),
                      md5(string_agg(id::text || ':' || coalesce(signing_user::text,''),',' ORDER BY id))) FROM account_move""")
    assets = original("""SELECT json_build_array(count(*),md5(string_agg(md5(to_jsonb(a)::text),'' ORDER BY id)))
                      FROM ir_attachment a WHERE res_model='res.users' AND res_field='sign_signature'""")
    require(flags == [29, 0, 0] and signers[:2] == [8129,124] and assets[0] == 1, "unexpected-original-signature-census")
    receipt = Path("/opt/steps-validation/community-sys-six-invoice-signing-20261127U41MSR/receipt.json")
    require(digest(receipt) == "e04cb5c178508dc28b12571e2e4e58f1bf1aceb692589e12f99a3637bc6af42e",
            "unexpected-native-print-signing-receipt")
    receipt_cases, = json.loads(receipt.read_bytes())
    types = ("out_receipt", "in_receipt")
    expected_cases = list(product((False, True), (False, True), ("no", "blank", "sample"), types, ("draft", "posted", "cancel")))
    require([tuple(sample[:5]) for sample in receipt_cases] == expected_cases, "native-receipt-signing-coverage")
    enabled_types = {sample[3] for sample in receipt_cases if sample[5]}
    for enabled, configured, image, kind, state, shown, present, identical in receipt_cases:
        visible = enabled and kind in enabled_types and state == "posted"
        require(shown == visible and present == identical == (visible and image == "sample"), "native-receipt-signing-rule")
    labels["signature_document_types"] = ["out_invoice", "out_refund", *sorted(enabled_types)]
    models = output / "models"
    implementation = models / "sys_chilean_invoice_history.py"
    metadata = models / "sys_invoice_reference_labels.py"
    init = models / "__init__.py"
    require(not implementation.exists() and not metadata.exists() and "sys_chilean_invoice_history" not in init.read_text(),
            "historical-invoice-provider-already-present")
    shutil.copyfile(Path(__file__).with_name(implementation.name), implementation)
    metadata.write_text("METADATA = " + pformat(labels, sort_dicts=True) + "\n")
    init.write_text(init.read_text().rstrip() + "\nfrom . import sys_chilean_invoice_history\n")
    return {"model": model[0], "field_ids": sorted(FIELDS), "permissions": access, "references": record_hash,
            "financial_relation_ids": [5963, 6077], "original_financial_delete_actions": original_fk,
            "signature_fields": sorted(signing_ids), "original_company_signatures": flags, "original_move_signers": signers,
            "original_signature_attachment": assets,
            "native_receipt_signing": digest(receipt),
            "code": digest(implementation), "metadata": digest(metadata), "init": digest(init)}
