"""Pruebas del puente Blueminds.

Cubren las condiciones del encargo que sólo pueden verificarse con el motor
delante: integridad de la matriz de 105 campos, estados exportables, ausencia
de anexas inventadas, redirección del menú y conciliación de importes contra
el generador vigente.
"""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.step_hr_previred.models import previred_adapter as adapters
from odoo.addons.step_hr_previred.tools import previred

from ..models.previred_engine import BluemindsAdapter
from .. import hooks


@tagged("post_install", "-at_install")
class TestBluemindsMatrix(TransactionCase):

    # -- matriz de campos ----------------------------------------------------

    def test_matrix_covers_the_105_fields_exactly_once(self):
        self.assertEqual(BluemindsAdapter.check_matrix(), [])

    def test_matrix_entries_are_traceable(self):
        """Cada campo declara de dónde sale; nada queda sin origen."""
        for entry in BluemindsAdapter.field_matrix():
            self.assertTrue(
                entry.source,
                "El campo %d no declara origen." % entry.position)
            self.assertIn(entry.kind, adapters.FieldSource.KINDS)

    def test_amount_fields_come_from_payslip_rules(self):
        """Los importes salen de reglas salariales, no de constantes.

        Es la comprobación de que no se inventó una correspondencia: si un
        campo de monto apareciera como `constant`, sería una invención.
        """
        matrix = {entry.position: entry
                  for entry in BluemindsAdapter.field_matrix()}
        # Campos de monto que el motor sí calcula desde la liquidación.
        for position in (22, 23, 28, 29, 43, 70, 71, 80, 81, 85, 98, 101, 102):
            entry = matrix[position]
            self.assertIn(
                entry.kind, ("rule", "computed"),
                "El campo %d (%s) debería venir de la liquidación y viene de "
                "«%s»." % (position, entry.field_name, entry.kind))

    def test_matrix_documents_the_known_divergences(self):
        """Las diferencias con la especificación quedan anotadas, no ocultas."""
        matrix = {entry.position: entry
                  for entry in BluemindsAdapter.field_matrix()}
        for position in (14, 93, 95, 105):
            self.assertTrue(
                matrix[position].note,
                "El campo %d tiene una diferencia conocida y debe llevar nota."
                % position)

    # -- estados exportables -------------------------------------------------

    def test_eligible_states_exclude_draft_and_cancel(self):
        for forbidden in ("draft", "cancel"):
            self.assertNotIn(forbidden, BluemindsAdapter.eligible_states)

    def test_eligible_states_are_justified(self):
        self.assertTrue(BluemindsAdapter.eligible_states_note)

    def test_profile_declares_the_same_states(self):
        profile = self.env.ref(
            "step_hr_previred_blueminds.profile_blueminds_v84")
        self.assertEqual(profile.state_list(),
                         BluemindsAdapter.eligible_states)

    # -- anexas --------------------------------------------------------------

    def test_engine_declares_no_annexes_and_says_why(self):
        self.assertFalse(BluemindsAdapter.supports_annexes)
        self.assertTrue(BluemindsAdapter.annexes_note)

    def test_vendor_has_no_multiple_movements_to_justify_annexes(self):
        """La razón de no emitir anexas es del motor, no una decisión nuestra.

        Si el proveedor añadiera un modelo de movimientos múltiples, esta
        prueba falla y obliga a revisar el adaptador: sería el momento de
        empezar a emitir líneas 01/02/03 con respaldo real.
        """
        payslip_fields = self.env["hr.payslip"]._fields
        self.assertIn(
            "movimientos_personal", payslip_fields,
            "El motor Blueminds debe seguir teniendo el campo de movimiento.")
        self.assertEqual(
            payslip_fields["movimientos_personal"].type, "selection",
            "El movimiento de personal de Blueminds es un único código; si "
            "pasara a ser una relación, habría datos para emitir anexas.")

    def test_line_type_is_documented_as_principal_only(self):
        entry = {e.position: e
                 for e in BluemindsAdapter.field_matrix()}[previred.F_LINE_TYPE]
        self.assertIn("00", "%s %s" % (entry.source, entry.note))

    # -- registro ------------------------------------------------------------

    def test_adapter_is_registered_in_the_core(self):
        self.assertIs(adapters.get_adapter("l10n_cl_hr"), BluemindsAdapter)

    def test_adapter_is_available_when_the_vendor_is_installed(self):
        self.assertTrue(BluemindsAdapter.is_available(self.env))

    # -- menú único ----------------------------------------------------------

    def test_vendor_menu_points_at_the_steps_wizard(self):
        """No quedan dos flujos Previred: el menú del motor es el nuevo."""
        menu = self.env.ref(hooks.MENU_XMLID, raise_if_not_found=False)
        action = self.env.ref(hooks.ACTION_XMLID)
        self.assertTrue(menu, "El menú del motor debe seguir existiendo.")
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
        """Una sola entrada de exportación Previred en toda la base."""
        action = self.env.ref(hooks.ACTION_XMLID)
        menus = self.env["ir.ui.menu"].with_context(
            active_test=False).search([
                ("action", "=", "ir.actions.act_window,%d" % action.id)])
        self.assertEqual(
            len(menus), 1,
            "Hay %d menús apuntando al asistente Previred: %s"
            % (len(menus), menus.mapped("complete_name")))
