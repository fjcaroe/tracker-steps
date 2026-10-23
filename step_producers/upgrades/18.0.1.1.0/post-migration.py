"""Move the earlier T30 calendar from Gestión y Costos into Productores."""

import logging

from odoo import SUPERUSER_ID, api


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    legacy_menu = env.ref("step_management_costs.menu_purchase_contract", raise_if_not_found=False)
    if legacy_menu:
        legacy_menu.active = False

    legacy_model = "step.management.purchase.contract"
    if legacy_model not in env.registry.models:
        return
    old_contracts = env[legacy_model].sudo().search([], order="version asc, id asc")
    New = env["step.producer.purchase.contract"].sudo()
    migrated = {record.legacy_contract_id: record for record in New.search([
        ("legacy_contract_id", "in", old_contracts.ids)])}
    count = 0
    for old in old_contracts:
        if old.id in migrated:
            continue
        parent = migrated.get(old.parent_id.id)
        new = New.with_company(old.company_id).create({
            "name": old.name,
            "company_id": old.company_id.id,
            "partner_id": old.partner_id.id,
            "currency_id": old.currency_id.id,
            "date_start": old.date_start,
            "date_end": old.date_end,
            "operation_type": old.operation_type,
            "reference": old.reference,
            "notes": old.notes,
            "version": old.version,
            "parent_id": parent.id if parent else False,
            "legacy_contract_id": old.id,
        })
        products = {}
        old_lines = old.with_context(active_test=False).installment_ids.sorted(
            lambda line: (line.sequence, line.id))
        for line in old_lines:
            key = (line.product_id.id, line.uom_id.id, line.price_unit)
            if key not in products:
                product = line.product_id.with_company(old.company_id)
                account = (product.property_account_expense_id or
                           product.categ_id.property_account_expense_categ_id)
                products[key] = env["step.producer.purchase.contract.product"].sudo().create({
                    "contract_id": new.id,
                    "product_id": line.product_id.id,
                    "description": line.product_id.display_name,
                    "quantity": line.quantity,
                    "uom_id": line.uom_id.id or product.uom_po_id.id,
                    "price_unit": line.price_unit,
                    "debit_account_id": account.id,
                })
            else:
                products[key].quantity += line.quantity
            env["step.producer.purchase.contract.installment"].sudo().create({
                "contract_id": new.id,
                "product_line_id": products[key].id,
                "sequence": line.sequence,
                "quantity": line.quantity,
                "date_due": line.date_due,
                "validation_criteria": line.validation_criteria,
                "state": "accounted" if line.state == "posted" else line.state,
                "active": line.active,
            })
        new.state = old.state
        migrated[old.id] = new
        count += 1
    _logger.info("T30: migrated %s producer contracts from Gestión y Costos", count)
