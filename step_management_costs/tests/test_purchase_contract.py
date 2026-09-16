"""Ticket #30 T30 Módulo Compras/contratos, mejora — pieza autocontenida:
calendario de pago (cuotas) de un contrato de compra con anticipo a
proveedor/productor. No incluye la contabilización automática ni la
integración con Tesorería (flujo de caja) que pide el documento original:
esas piezas dependen de un módulo (step_account_treasury) que vive en otro
worktree y de un mapeo de cuentas que el documento no deja inequívoco — ver
la nota del ticket #30 en el Helpdesk."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestPurchaseContract(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create({"name": "Agrícola Los Arándanos SPA"})
        cls.product = cls.env["product.product"].create(dict({
            "name": "Anticipo fruta", "type": "consu", "is_storable": False,
            "uom_id": cls.env.ref("uom.product_uom_kgm").id,
            "uom_po_id": cls.env.ref("uom.product_uom_kgm").id,
        }, **extra_product_vals(cls.env)))

    def _contract(self, installments=None):
        installments = installments if installments is not None else [{
            "product_id": self.product.id, "quantity": 15000.0, "price_unit": 1.5,
            "date_due": "2026-06-30", "validation_criteria": "Estimación de cosecha",
        }]
        return self.env["step.management.purchase.contract"].create({
            "company_id": self.company_a.id, "partner_id": self.vendor.id,
            "operation_type": "Fruta: Recepción fruta",
            "installment_ids": [(0, 0, vals) for vals in installments],
        })

    def test_sequence_assigned_on_create(self):
        contract = self._contract()
        self.assertNotEqual(contract.name, "Nuevo")
        self.assertIn("CTR/", contract.name)

    def test_installment_amount_computed(self):
        contract = self._contract()
        line = contract.installment_ids
        self.assertAlmostEqual(line.amount, 15000.0 * 1.5)
        self.assertAlmostEqual(contract.amount_total, 22500.0)
        self.assertAlmostEqual(contract.quantity_total, 15000.0)

    def test_confirm_requires_installments(self):
        contract = self._contract(installments=[])
        with self.assertRaises(UserError):
            contract.action_confirm()

    def test_confirm_then_close(self):
        contract = self._contract()
        contract.action_confirm()
        self.assertEqual(contract.state, "confirmed")
        contract.action_close()
        self.assertEqual(contract.state, "closed")

    def test_cannot_close_from_draft(self):
        contract = self._contract()
        with self.assertRaises(UserError):
            contract.action_close()

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            self._contract(installments=[{
                "product_id": self.product.id, "quantity": -1.0, "price_unit": 1.5,
                "date_due": "2026-06-30",
            }])

    def test_frozen_header_after_confirm(self):
        contract = self._contract()
        contract.action_confirm()
        with self.assertRaises(UserError):
            contract.with_user(self.user_operator).write({"partner_id": self.vendor.id})

    def test_revise_archives_pending_and_creates_new_version(self):
        contract = self._contract(installments=[
            {"product_id": self.product.id, "quantity": 15000.0, "price_unit": 1.5,
             "date_due": "2026-06-30", "validation_criteria": "Estimación de cosecha"},
            {"product_id": self.product.id, "quantity": 10000.0, "price_unit": 1.5,
             "date_due": "2026-11-30", "validation_criteria": "Estimación de cosecha"},
        ])
        contract.action_confirm()
        contract.installment_ids[0].action_approve()
        contract.installment_ids[0].state = "posted"  # ya contabilizada, no se toca

        contract.action_revise()

        self.assertTrue(contract.is_superseded)
        pending = contract.installment_ids.filtered(lambda l: l.state != "posted")
        self.assertFalse(pending.mapped("active")[0] if pending else True,
                          "La cuota pendiente del contrato original debe archivarse")
        new_contract = contract.revision_ids
        self.assertEqual(len(new_contract), 1)
        self.assertEqual(new_contract.version, 2)
        self.assertEqual(new_contract.parent_id, contract)
        self.assertEqual(len(new_contract.installment_ids), 1,
                          "Sólo la cuota pendiente (no contabilizada) pasa a la nueva versión")
        self.assertAlmostEqual(new_contract.installment_ids.quantity, 10000.0)

        # la cuota ya contabilizada del contrato original sigue activa y sin tocar
        posted = contract.installment_ids.filtered(lambda l: l.state == "posted")
        self.assertTrue(posted.active)

    def test_cannot_revise_twice(self):
        contract = self._contract()
        contract.action_confirm()
        contract.action_revise()
        with self.assertRaises(UserError):
            contract.action_revise()

    def test_approve_installment(self):
        contract = self._contract()
        line = contract.installment_ids
        line.action_approve()
        self.assertEqual(line.state, "approved")
        with self.assertRaises(UserError):
            line.action_approve()
