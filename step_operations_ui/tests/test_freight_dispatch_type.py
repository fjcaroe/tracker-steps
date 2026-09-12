from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreightDispatchType(TransactionCase):

    def test_seed_data_loaded_with_expected_rules(self):
        expected = {
            "Retira cliente": "no",
            "Despacho a cliente": "opcional",
            "Despacho a tercero": "opcional",
        }
        for name, paga_flete in expected.items():
            record = self.env["x_tipo_despacho"].search([("x_name", "=", name)], limit=1)
            self.assertTrue(record, f"Falta el tipo de despacho semilla {name!r}")
            self.assertEqual(record.paga_flete, paga_flete)

    def test_default_paga_flete_is_no(self):
        record = self.env["x_tipo_despacho"].create({"x_name": "Tipo de prueba"})
        self.assertEqual(record.paga_flete, "no")
