"""Pruebas del puente SimpleDigital.

Cubren la integridad de la matriz, los estados exportables con su
justificación, las líneas anexas reales, la redirección del menú y —lo más
importante— el **cierre de la ruta insegura del proveedor**, con los cinco
casos que el encargo exige.
"""

from odoo.tests.common import HttpCase, TransactionCase, new_test_user, tagged

from odoo.addons.step_hr_previred.models import previred_adapter as adapters

from ..controllers.previred_secure import SecuredPreviredExportController
from ..models.previred_engine import SimpleDigitalAdapter
from .. import hooks


@tagged("post_install", "-at_install")
class TestSimpleDigitalMatrix(TransactionCase):

    def test_matrix_covers_the_105_fields_exactly_once(self):
        self.assertEqual(SimpleDigitalAdapter.check_matrix(), [])

    def test_matrix_entries_are_traceable(self):
        for entry in SimpleDigitalAdapter.field_matrix():
            self.assertTrue(
                entry.source,
                "El campo %d no declara origen." % entry.position)
            self.assertIn(entry.kind, adapters.FieldSource.KINDS)

    def test_amount_fields_come_from_payslip_rules(self):
        matrix = {entry.position: entry
                  for entry in SimpleDigitalAdapter.field_matrix()}
        for position in (22, 28, 29, 70, 80, 81, 85, 98, 101, 102):
            entry = matrix[position]
            self.assertIn(
                entry.kind, ("rule", "computed"),
                "El campo %d (%s) debería venir de la liquidación y viene de "
                "«%s»." % (position, entry.field_name, entry.kind))

    def test_mislabelled_vendor_variables_are_documented(self):
        """Las variables del proveedor cuyo nombre no coincide con el campo."""
        matrix = {entry.position: entry
                  for entry in SimpleDigitalAdapter.field_matrix()}
        for position in (86, 88, 90):
            self.assertTrue(
                matrix[position].note,
                "El campo %d tiene un nombre de variable engañoso en el "
                "generador y debe llevar nota." % position)

    # -- estados exportables -------------------------------------------------

    def test_eligible_states_exclude_draft_and_cancel(self):
        for forbidden in ("draft", "cancel"):
            self.assertNotIn(forbidden, SimpleDigitalAdapter.eligible_states)

    def test_verify_is_admitted_and_justified(self):
        """`verify` se admite en este motor, y consta por qué."""
        self.assertIn("verify", SimpleDigitalAdapter.eligible_states)
        self.assertIn("verify", SimpleDigitalAdapter.eligible_states_note)

    def test_profile_declares_the_same_states(self):
        profile = self.env.ref(
            "step_hr_previred_simpledigital.profile_simpledigital_v84")
        self.assertEqual(profile.state_list(),
                         SimpleDigitalAdapter.eligible_states)

    def test_profile_rejects_draft(self):
        profile = self.env.ref(
            "step_hr_previred_simpledigital.profile_simpledigital_v84")
        with self.assertRaises(Exception):
            profile.write({"eligible_states": "draft,done"})

    # -- anexas reales -------------------------------------------------------

    def test_engine_supports_annexes_from_real_movements(self):
        self.assertTrue(SimpleDigitalAdapter.supports_annexes)
        self.assertIn("previred_movement_ids",
                      SimpleDigitalAdapter.annexes_note)

    def test_vendor_movement_model_exists(self):
        """Las anexas se apoyan en datos reales del proveedor."""
        self.assertIn("previred_movement_ids",
                      self.env["hr.payslip"]._fields,
                      "Sin movimientos del proveedor no habría anexas que "
                      "emitir y el adaptador debería dejar de declararlas.")

    # -- registro y menú -----------------------------------------------------

    def test_adapter_is_registered_in_the_core(self):
        self.assertIs(adapters.get_adapter("simpledigital"),
                      SimpleDigitalAdapter)

    def test_vendor_menu_points_at_the_steps_wizard(self):
        menu = self.env.ref(hooks.MENU_XMLID, raise_if_not_found=False)
        action = self.env.ref(hooks.ACTION_XMLID)
        self.assertTrue(menu)
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(menu.action._name, "ir.actions.act_window")

    def test_menu_redirection_is_idempotent(self):
        hooks.redirect_previred_menu(self.env)
        hooks.redirect_previred_menu(self.env)
        menu = self.env.ref(hooks.MENU_XMLID)
        action = self.env.ref(hooks.ACTION_XMLID)
        self.assertEqual(menu.action.id, action.id)
        self.assertEqual(menu.action._name, "ir.actions.act_window")

    def test_no_duplicate_previred_export_menus(self):
        action = self.env.ref(hooks.ACTION_XMLID)
        menus = self.env["ir.ui.menu"].with_context(
            active_test=False).search([
                ("action", "=", "ir.actions.act_window,%d" % action.id)])
        self.assertEqual(
            len(menus), 1,
            "Hay %d menús apuntando al asistente Previred: %s"
            % (len(menus), menus.mapped("complete_name")))

    # -- herencia real del controlador ---------------------------------------

    def test_controller_really_inherits_the_vendor_one(self):
        """No es una ruta suelta con la misma URL: es herencia."""
        from odoo.addons.l10n_cl_simpledigital_payroll.controllers import (
            previred_txt as vendor,
        )
        self.assertTrue(issubclass(SecuredPreviredExportController,
                                   vendor.PreviredExportController))
        # El método del descendiente es el que Odoo resuelve.
        self.assertIsNot(
            SecuredPreviredExportController.download_previred_txt,
            vendor.PreviredExportController.download_previred_txt)


@tagged("post_install", "-at_install")
class TestSimpleDigitalRouteSecurity(HttpCase):
    """Los cinco casos de seguridad de ruta que exige el encargo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].sudo().search(
            [("id", "!=", cls.company.id)], limit=1)
        cls.plain = new_test_user(
            cls.env, login="sd_plain", groups="base.group_user",
            password="sd_plain")
        cls.exporter = new_test_user(
            cls.env, login="sd_exporter", password="sd_exporter",
            groups="step_hr_previred.group_previred_generate,"
                   "hr_payroll.group_hr_payroll_manager")

    # 1) usuario sin grupo
    def test_user_without_group_is_rejected(self):
        self.authenticate("sd_plain", "sd_plain")
        response = self.url_open(
            "/hr_payroll/previred/txt?period=082026&company_id=%d"
            % self.company.id)
        body = response.text or ""
        self.assertNotIn(";", body.split("\n")[0] if body else "",
                         "Un usuario sin permiso no debe recibir el archivo.")
        self.assertTrue(
            response.status_code >= 400 or "permiso" in body.lower()
            or "AccessError" in body,
            "Se esperaba un rechazo y llegó %s" % response.status_code)

    # 2) compañía manipulada en la URL
    def test_company_manipulated_in_url_is_rejected(self):
        if not self.other_company:
            self.skipTest("La base sólo tiene una compañía.")
        self.authenticate("sd_exporter", "sd_exporter")
        response = self.url_open(
            "/hr_payroll/previred/txt?period=082026&company_id=%d"
            % self.other_company.id)
        body = response.text or ""
        self.assertTrue(
            response.status_code >= 400 or "compañía" in body.lower()
            or "AccessError" in body,
            "Se esperaba rechazo al pedir una compañía no habilitada.")

    # 3) período manipulado
    def test_manipulated_period_is_rejected(self):
        self.authenticate("sd_exporter", "sd_exporter")
        for period in ("2026-08", "132026", "abc", "089999"):
            response = self.url_open(
                "/hr_payroll/previred/txt?period=%s&company_id=%d"
                % (period, self.company.id))
            body = response.text or ""
            self.assertTrue(
                response.status_code >= 400 or "período" in body.lower()
                or "formato" in body.lower() or "UserError" in body,
                "El período «%s» debió rechazarse y devolvió %s"
                % (period, response.status_code))

    # 4) llamada directa a la ruta antigua, sin pasar por el asistente
    def test_direct_call_to_the_old_route_is_guarded(self):
        self.authenticate("sd_plain", "sd_plain")
        for url in ("/hr_payroll/previred/txt", "/hr_payroll/previred/csv"):
            response = self.url_open("%s?period=082026&company_id=%d"
                                     % (url, self.company.id))
            body = response.text or ""
            self.assertTrue(
                response.status_code >= 400 or "permiso" in body.lower()
                or "AccessError" in body,
                "La ruta %s quedó abierta." % url)

    # 5) sin compañía: no se adivina
    def test_missing_company_is_rejected(self):
        self.authenticate("sd_exporter", "sd_exporter")
        response = self.url_open("/hr_payroll/previred/txt?period=082026")
        body = response.text or ""
        self.assertTrue(
            response.status_code >= 400 or "compañía" in body.lower()
            or "UserError" in body,
            "Sin compañía explícita la ruta no debe generar nada.")
