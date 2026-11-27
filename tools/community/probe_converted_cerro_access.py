"""Read an original Cerro contract form and a private purchase PDF with ordinary company permissions."""
import hashlib

from lxml import etree
from odoo.exceptions import AccessError


def cerro_restore_access(env):
    payroll = env.ref("hr_payroll.group_hr_payroll_manager")
    purchase = env.ref("purchase.group_purchase_user")
    public = env(user=env.ref("base.public_user").id, su=False)
    contracts = env["hr.contract"]
    people = env["res.users"].search([("active", "=", True), ("share", "=", False)], order="id")
    def ordinary_first(user):
        return user.has_group("base.group_system"), user.id

    reviewers = (people & payroll.users).filtered(lambda u: u.id != 1).sorted(ordinary_first)
    readers = (people & purchase.users).filtered(
        lambda u: u.id != 1 and len(u.company_ids.filtered("active")) > 1
    ).sorted(ordinary_first)
    assert reviewers and readers
    review = None
    for actor in reviewers:
        scope = env(user=actor.id, su=False, context={"allowed_company_ids": actor.company_ids.filtered("active").ids})
        model = scope[contracts._name]
        if not model.has_access("read"):
            continue
        contract = model.search([], order="id", limit=1)
        view = model.get_view(view_id=scope.ref("hr_contract.hr_contract_view_form").id, view_type="form")
        tree = etree.fromstring(view["arch"].encode())
        assert tree.xpath("//field[@name='step_payroll_migration_review']")
        assert tree.xpath("//button[@name='action_confirm_payroll_migration']")
        if contract:
            assert contract.read(["step_payroll_migration_review"])[0]["id"] == contract.id
        else:
            assert model.search_count([]) == 0
            model.default_get(["step_payroll_migration_review"])
        assert not public[contracts._name].has_access("read")
        review = {"actor": actor.id, "ordinary_role": not scope.su, "original_contract_form": True,
                  "review_action_in_form": True, "stored_contract_read": bool(contract), "contract_public_denied": True}
        break
    assert review
    env.cr.execute("""
        SELECT a.id,p.id,p.company_id FROM ir_attachment a JOIN purchase_order p ON a.res_id=p.id
         WHERE a.res_model='purchase.order' AND a.type='binary' AND a.public IS NOT TRUE AND a.res_field IS NULL
           AND a.mimetype='application/pdf' AND a.store_fname IS NOT NULL AND a.file_size>0 ORDER BY a.id
    """)
    documents = env.cr.fetchall()
    for actor in readers:
        companies = actor.company_ids.filtered("active")
        for attachment_id, order_id, company_id in documents:
            if company_id not in companies.ids:
                continue
            home = env(user=actor.id, su=False, context={"allowed_company_ids": [company_id], "bin_size": False})
            order = home["purchase.order"].browse(order_id)
            if not order.has_access("read"):
                continue
            original = home["ir.attachment"].browse(attachment_id)
            try:
                original.check("read")
            except AccessError:
                continue
            for company in companies.filtered(lambda c: c.id != company_id):
                away = env(user=actor.id, su=False, context={"allowed_company_ids": [company.id]})
                if away["purchase.order"].browse(order_id).has_access("read"):
                    continue
                try:
                    away["ir.attachment"].browse(attachment_id).check("read")
                except AccessError:
                    break
            else:
                continue
            try:
                public["ir.attachment"].browse(attachment_id).check("read")
            except AccessError:
                pass
            else:
                raise AssertionError("Public role accessed a private purchase document")
            payload = original.raw
            assert payload.startswith(b"%PDF-") and len(payload) == original.file_size
            assert hashlib.sha1(payload).hexdigest() == original.checksum
            return actor, {"contract_review": review, "purchase_document": {
                "actor": actor.id, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                "ordinary_role": not home.su, "different_company_denied": True, "public_denied": True,
            }}
    raise AssertionError("No genuine purchase actor read an original restricted PDF with company separation")
