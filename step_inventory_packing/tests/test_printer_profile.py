from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError

from ..models.printer_profile import label_text


@tagged('post_install', '-at_install')
class TestPrinterProfile(TransactionCase):
    def test_label_commands_cannot_be_injected_and_profiles_are_checked(self):
        self.assertEqual(label_text('Frutá ^XZ~JA\n'), 'Fruta XZJA')
        profile = self.env['step.printer.profile'].create({'name': 'Impresora USB serie QA', 'protocol': 'serial'})
        action = profile.action_test_label()
        self.assertEqual(action['tag'], 'step_printer_job')
        self.assertTrue(action['params']['payload'].startswith('^XA'))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['step.printer.profile'].create({'name': 'BLE sin UUID QA', 'protocol': 'ble'})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['step.printer.profile'].create({'name': 'USB sin fabricante QA', 'protocol': 'usb'})
        tag = self.env['stock.quant.package'].create({'name': 'QA^XZ-INJECT', 'is_fruit_tag': True, 'step_tag_kind': 'E'})
        with self.assertRaises(UserError):
            tag._zpl_label(profile)
