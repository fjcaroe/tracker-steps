# -*- coding: utf-8 -*-
"""Fusión de las apps duplicadas entre Studio y su módulo."""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.step_agricultural_access.models import ir_ui_menu
from odoo.addons.step_agricultural_access.models.ir_ui_menu import (
    STUDIO_MODULE,
    STUDIO_SUFFIX,
)

FULL_LIST = {"ir.ui.menu.full_list": True}


@tagged("post_install", "-at_install")
class TestMenuConsolidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Menu = cls.env["ir.ui.menu"].with_context(**FULL_LIST)
        cls.Data = cls.env["ir.model.data"]

    def _menu(self, name, module, parent=None, action=None):
        menu = self.Menu.create({
            "name": name,
            "parent_id": parent.id if parent else False,
            "action": action,
        })
        self.Data.create({
            "module": module,
            "name": "qa_%s_%s" % (module, menu.id),
            "model": "ir.ui.menu",
            "res_id": menu.id,
        })
        return menu

    def _act(self, model, domain=False, view_mode=False):
        values = {"name": "QA %s" % model, "res_model": model}
        if domain:
            values["domain"] = domain
        if view_mode:
            values["view_mode"] = view_mode
        return "ir.actions.act_window,%s" % self.env["ir.actions.act_window"].create(values).id

    def _url(self, url):
        return "ir.actions.act_url,%s" % self.env["ir.actions.act_url"].create(
            {"name": "QA url", "url": url}).id

    def _children(self, menu):
        return self.Menu.search([("parent_id", "=", menu.id)])

    def _build_pair(self):
        """Reproduce el estado real: app de Studio + app del módulo homónima."""
        studio = self._menu("QA App Duplicada", STUDIO_MODULE)
        module = self._menu("QA App Duplicada", "step_qa")
        # Rama que existe en los dos: se debe fundir.
        s_masters = self._menu("Maestros", STUDIO_MODULE, studio, self._url("/web"))
        m_masters = self._menu("Maestros", "step_qa", module)
        # Hoja idéntica en ambos -> sobra la de Studio.
        self._menu("Equipos", STUDIO_MODULE, s_masters, self._act("res.partner"))
        self._menu("Equipos", "step_qa", m_masters, self._act("res.partner"))
        # Hoja que sólo existe en Studio -> se debe conservar.
        self._menu("Sustancia activa", STUDIO_MODULE, s_masters, self._act("res.country"))
        # Rama completa que sólo existe en Studio -> se debe mover entera.
        s_reports = self._menu("Informes", STUDIO_MODULE, studio)
        self._menu("Informe EPP", STUDIO_MODULE, s_reports, self._act("res.currency"))
        return studio, module, m_masters

    def test_studio_root_is_merged_and_archived(self):
        studio, module, m_masters = self._build_pair()
        report = self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        studio.invalidate_recordset()
        self.assertFalse(studio.active, "La raíz de Studio queda archivada.")
        self.assertIn("QA App Duplicada (#%s)" % studio.id,
                      " ".join(report["raices_archivadas"]))

        nombres = self._children(module).mapped("name")
        self.assertIn("Maestros", nombres)
        self.assertIn("Informes", nombres, "La rama exclusiva de Studio se conserva.")
        self.assertEqual(nombres.count("Maestros"), 1, "No debe quedar duplicado.")

        maestros = self._children(m_masters).mapped("name")
        self.assertIn("Sustancia activa", maestros,
                      "La hoja que sólo existía en Studio no se pierde.")
        self.assertEqual(maestros.count("Equipos"), 1,
                         "La hoja repetida hacia el mismo modelo se archiva.")

    def test_nothing_reachable_is_lost(self):
        studio, module, _m = self._build_pair()
        antes = self.Menu.search([("id", "child_of", studio.id)])
        modelos_antes = set()
        for menu in antes:
            model = menu._action_target_model()
            if model:
                modelos_antes.add(model)

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        despues = self.Menu.search([("id", "child_of", module.id), ("active", "=", True)])
        modelos_despues = set()
        for menu in despues:
            model = menu._action_target_model()
            if model:
                modelos_despues.add(model)
        self.assertTrue(modelos_antes <= modelos_despues,
                        "Todo modelo alcanzable desde Studio sigue alcanzable: %s"
                        % (modelos_antes - modelos_despues))

    def test_is_idempotent(self):
        self._build_pair()
        first = self.env["ir.ui.menu"]._consolidate_duplicated_apps()
        self.assertTrue(first["raices_archivadas"])
        second = self.env["ir.ui.menu"]._consolidate_duplicated_apps()
        self.assertFalse(second["raices_archivadas"], "La segunda pasada no hace nada.")
        self.assertFalse(second["movidos"])
        self.assertFalse(second["archivados_redundantes"])

    def test_leaf_with_a_different_target_is_kept_and_renamed(self):
        studio = self._menu("QA App Distinta", STUDIO_MODULE)
        module = self._menu("QA App Distinta", "step_qa")
        self._menu("Fichas", STUDIO_MODULE, studio, self._act("res.country"))
        self._menu("Fichas", "step_qa", module, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        nombres = self._children(module).mapped("name")
        self.assertIn("Fichas", nombres)
        self.assertIn("Fichas" + STUDIO_SUFFIX, nombres,
                      "Si apunta a otro modelo se conserva, renombrada.")

    def test_app_without_studio_twin_is_untouched(self):
        solo = self._menu("QA App Sin Gemela", "step_qa")
        hijo = self._menu("Algo", "step_qa", solo, self._act("res.partner"))
        self.env["ir.ui.menu"]._consolidate_duplicated_apps()
        solo.invalidate_recordset()
        hijo.invalidate_recordset()
        self.assertTrue(solo.active)
        self.assertTrue(hijo.active)
        self.assertEqual(hijo.parent_id, solo)

    def test_no_duplicated_root_names_remain(self):
        self._build_pair()
        self.env["ir.ui.menu"]._consolidate_duplicated_apps()
        roots = self.Menu.search([("parent_id", "=", False), ("active", "=", True)])
        nombres = [menu.name for menu in roots]
        repetidos = {n for n in nombres if nombres.count(n) > 1}
        self.assertNotIn("QA App Duplicada", repetidos)

    def test_leaf_repeated_at_another_level_is_deduped(self):
        """Una rama de Studio no debe reintroducir entradas que ya existen."""
        studio = self._menu("QA App Niveles", STUDIO_MODULE)
        module = self._menu("QA App Niveles", "step_qa")
        rama = self._menu("Calidad", STUDIO_MODULE, studio)
        repetida = self._menu("Puntos de control", STUDIO_MODULE, rama, self._act("res.partner"))
        propia = self._menu("Puntos de control", "step_qa", module, self._act("res.partner"))
        distinta = self._menu("Otro informe", STUDIO_MODULE, rama, self._act("res.country"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        for menu in (repetida, propia, distinta):
            menu.invalidate_recordset()
        self.assertFalse(repetida.active, "La entrada repetida de Studio se archiva.")
        self.assertTrue(propia.active, "La entrada del módulo se conserva.")
        self.assertTrue(distinta.active, "Lo que no está repetido no se toca.")

    def test_identical_action_with_another_name_is_retired(self):
        """Caso Fletes: 'Orden de flete' y 'Órdenes de flete' abren lo mismo."""
        studio = self._menu("QA App Nombres", STUDIO_MODULE)
        module = self._menu("QA App Nombres", "step_qa")
        rama = self._menu("Listados", STUDIO_MODULE, studio)
        vieja = self._menu("Orden de flete", STUDIO_MODULE, rama, self._act("res.partner"))
        nueva = self._menu("Órdenes de flete", "step_qa", module, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        vieja.invalidate_recordset()
        nueva.invalidate_recordset()
        self.assertFalse(vieja.active, "La entrada heredada con el mismo destino se retira.")
        self.assertTrue(nueva.active, "La entrada del módulo se conserva.")

    def test_same_model_with_a_different_domain_is_kept(self):
        """Un informe filtrado no es la misma cosa que la lista completa."""
        studio = self._menu("QA App Dominios", STUDIO_MODULE)
        module = self._menu("QA App Dominios", "step_qa")
        rama = self._menu("Listados", STUDIO_MODULE, studio)
        filtrada = self._menu("Proveedores", STUDIO_MODULE, rama,
                              self._act("res.partner", domain="[('supplier_rank','>',0)]"))
        completa = self._menu("Contactos", "step_qa", module, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        filtrada.invalidate_recordset()
        completa.invalidate_recordset()
        self.assertTrue(filtrada.active, "Dominios distintos: no se archiva.")
        self.assertTrue(completa.active)

    def test_report_view_is_not_confused_with_a_list(self):
        """Mismo modelo y dominio pero otra vista: son cosas distintas."""
        studio = self._menu("QA App Vistas", STUDIO_MODULE)
        module = self._menu("QA App Vistas", "step_qa")
        rama = self._menu("Listados", STUDIO_MODULE, studio)
        informe = self._menu("Informe", STUDIO_MODULE, rama,
                             self._act("res.partner", view_mode="pivot,graph"))
        lista = self._menu("Listado", "step_qa", module, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        informe.invalidate_recordset()
        lista.invalidate_recordset()
        self.assertTrue(informe.active, "Un informe no se archiva contra una lista.")
        self.assertTrue(lista.active)

    def test_two_studio_entries_are_left_alone(self):
        """Si ninguna pertenece al módulo, la rutina no decide por la casa."""
        studio = self._menu("QA App SoloStudio", STUDIO_MODULE)
        module = self._menu("QA App SoloStudio", "step_qa")
        rama = self._menu("Listados", STUDIO_MODULE, studio)
        una = self._menu("Uno", STUDIO_MODULE, rama, self._act("res.partner"))
        otra = self._menu("Dos", STUDIO_MODULE, rama, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        una.invalidate_recordset()
        otra.invalidate_recordset()
        self.assertTrue(una.active and otra.active)

    def test_explicit_legacy_pair_is_absorbed(self):
        """Caso 'Gestión y Costos borrador': se absorbe aunque cambie el nombre.

        Se usa un par propio de la prueba para no depender de los menús reales
        de la base y no chocar con homónimos.
        """
        studio = self._menu("QA Heredada Borrador", STUDIO_MODULE)
        module = self._menu("QA Heredada", "step_qa")
        exclusivo = self._menu("Plantilla exclusiva", STUDIO_MODULE, studio,
                               self._act("res.country"))

        with patch.dict(ir_ui_menu.EXPLICIT_LEGACY_PAIRS,
                        {"qa heredada borrador": "qa heredada"}):
            self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        studio.invalidate_recordset()
        exclusivo.invalidate_recordset()
        self.assertFalse(studio.active, "La app heredada queda archivada.")
        self.assertTrue(exclusivo.active, "Su contenido exclusivo se conserva.")
        self.assertEqual(exclusivo.parent_id, module)

    def test_ambiguous_pair_is_left_untouched(self):
        """Con dos candidatos del mismo nombre no se adivina: no se toca nada."""
        studio = self._menu("QA Ambigua", STUDIO_MODULE)
        first = self._menu("QA Ambigua", "step_qa")
        second = self._menu("QA Ambigua", "step_hr")
        hijo = self._menu("Algo exclusivo", STUDIO_MODULE, studio, self._act("res.country"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        studio.invalidate_recordset()
        hijo.invalidate_recordset()
        self.assertTrue(studio.active, "Con ambigüedad la rutina se abstiene.")
        self.assertEqual(hijo.parent_id, studio)
        self.assertTrue(first.active and second.active)

    def test_matching_uses_every_translation(self):
        """El emparejamiento no puede depender del idioma de la sesión."""
        spanish = self.env["res.lang"]._activate_lang("es_ES")
        if not spanish:
            self.skipTest("es_ES no disponible en esta base")
        studio = self._menu("Duplicated App", STUDIO_MODULE)
        module = self._menu("Duplicated App", "step_qa")
        studio.with_context(lang="es_ES").name = "App Duplicada"
        module.with_context(lang="es_ES").name = "App Duplicada"
        # Nombres distintos en inglés: sólo coinciden en español.
        studio.with_context(lang="en_US").name = "Legacy App"
        module.with_context(lang="en_US").name = "Modern App"
        hijo = self._menu("Sólo en Studio", STUDIO_MODULE, studio, self._act("res.partner"))

        self.env["ir.ui.menu"]._consolidate_duplicated_apps()

        studio.invalidate_recordset()
        hijo.invalidate_recordset()
        self.assertFalse(studio.active, "Debe emparejar por la traducción que coincide.")
        self.assertEqual(hijo.parent_id, module)
