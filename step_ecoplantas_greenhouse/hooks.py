from odoo import Command

DEMO = "steps_ecoplantas_greenhouse"


def post_init_hook(env):
    batch = env.ref(f"{DEMO}.batch", raise_if_not_found=False)
    if not batch or env.ref(f"{DEMO}.dispatch", raise_if_not_found=False):
        return
    company = batch.company_id
    warehouse = batch.picking_type_id.warehouse_id
    operation = warehouse.out_type_id
    source = batch.location_dest_id
    destination = operation.default_location_dest_id
    partner = env["res.partner"].create({
        "name": "Vivero comprador [DEMO]",
        "is_company": True,
        "company_id": company.id,
    })
    picking = env["stock.picking"].with_company(company).create({
        "origin": "[DEMO] Despacho de plantines",
        "partner_id": partner.id,
        "company_id": company.id,
        "picking_type_id": operation.id,
        "location_id": source.id,
        "location_dest_id": destination.id,
        "move_ids": [Command.create({
            "name": batch.product_id.display_name,
            "product_id": batch.product_id.id,
            "product_uom": batch.product_uom_id.id,
            "product_uom_qty": 60,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "company_id": company.id,
        })],
    })
    env["ir.model.data"].create({
        "module": DEMO, "name": "dispatch", "model": picking._name,
        "res_id": picking.id, "noupdate": True,
    })
