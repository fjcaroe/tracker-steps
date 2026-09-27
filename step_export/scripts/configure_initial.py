"""Idempotent T35 defaults. Run through ``odoo-bin shell`` with T35_COMPANIES.

This script does not create contractual producer rates or issue fiscal documents.
Account and tax defaults stay editable in Exportaciones > Configuración.
"""

import json
import os


names = [name.strip() for name in os.environ.get("T35_COMPANIES", "").split("|") if name.strip()]
if not names:
    raise RuntimeError("Set T35_COMPANIES to exact company names separated by |")

account_model = env["account.account"].sudo()
journal_model = env["account.journal"].sudo()
tax_model = env["account.tax"].sudo()
company_model = env["res.company"].sudo()


def company_account(company, code, title, account_type):
    model = account_model.with_company(company)
    domain = [("company_ids", "in", company.id)] if "company_ids" in model._fields else [("company_id", "=", company.id)]
    account = model.search(domain + [("code", "=", code)], limit=1)
    if not account:
        vals = {"name": title, "code": code, "account_type": account_type}
        vals["company_ids" if "company_ids" in model._fields else "company_id"] = (
            [(6, 0, company.ids)] if "company_ids" in model._fields else company.id)
        account = model.create(vals)
    if account.account_type != account_type:
        raise RuntimeError("Unexpected account type for %s in %s" % (code, company.name))
    return account


def journal(company, code, title, journal_type, account=None):
    existing = journal_model.with_company(company).search([
        ("company_id", "=", company.id), ("code", "=", code)], limit=1)
    if existing:
        if existing.type != journal_type:
            raise RuntimeError("Journal code %s has another type in %s" % (code, company.name))
        return existing
    vals = {"name": title, "code": code, "type": journal_type,
            "company_id": company.id}
    if account:
        vals["default_account_id"] = account.id
    if journal_type in ("sale", "purchase") and "l10n_latam_use_documents" in journal_model._fields:
        vals["l10n_latam_use_documents"] = True
    return journal_model.with_company(company).create(vals)


results = []
for name in names:
    company = company_model.search([("name", "=", name)], limit=1)
    if not company:
        raise RuntimeError("Company not found: %s" % name)
    if (company.account_fiscal_country_id or company.country_id).code != "CL":
        raise RuntimeError("Expected Chilean company: %s" % name)
    income = company_account(company, "310125", "Ventas de Exportación", "income")
    purchase_code = os.environ.get("T35_PURCHASE_ACCOUNT_CODE", "410230")
    purchase = company_account(company, purchase_code, "Compra de fruta para exportación", "expense")
    purchase_tax = tax_model.with_company(company).search([
        ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
        ("amount", "=", 19), ("active", "=", True)], order="id", limit=1)
    if not purchase_tax:
        raise RuntimeError("No active standard 19% purchase tax for %s" % name)
    sale_journal = journal(company, "EXPT", "Exportaciones T35", "sale", income)
    purchase_journal = journal(company, "PRDT", "Productores T35", "purchase", purchase)
    adjustment_journal = journal(company, "IVVT", "Ajustes IVV T35", "general")
    defaults = {
        "step_export_sale_journal_id": sale_journal.id,
        "step_export_purchase_journal_id": purchase_journal.id,
        "step_export_adjustment_journal_id": adjustment_journal.id,
        "step_export_income_account_id": income.id,
        "step_export_purchase_account_id": purchase.id,
        "step_export_purchase_tax_id": purchase_tax.id,
    }
    # Empty sale tax is intentional: DTE 110 export invoices carry no Chilean VAT.
    # Preserve a tax explicitly chosen by the customer on a later rerun.
    updates = {field: value for field, value in defaults.items() if not company[field]}
    if updates:
        company.with_company(company).write(updates)
    results.append({"company": company.name, "journals": [sale_journal.code,
                    purchase_journal.code, adjustment_journal.code],
                    "income_account": income.code, "purchase_account": purchase.code,
                    "purchase_tax": purchase_tax.name,
                    "sale_tax": company.step_export_sale_tax_id.name or "sin impuesto"})

env.cr.commit()
for result in results:
    print("T35_CONFIG " + json.dumps(result, ensure_ascii=False, default=str))
