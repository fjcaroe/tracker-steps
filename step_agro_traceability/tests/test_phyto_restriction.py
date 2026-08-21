# -*- coding: utf-8 -*-
"""Pruebas de la regla de carencia y reingreso.

Se prueban las reglas de negocio nativas sin depender de los modelos Studio:
las restricciones se crean directamente, que es exactamente lo que el motor de
lectura de ``x_aplicacion_foliar`` produce.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_phyto")
class TestPhytoRestriction(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.analytic_plan = cls.env["account.analytic.plan"].create({"name": "Plan carencia test"})
        cls.fundo = cls.env["step.fundo"].create({
            "name": "Fundo prueba carencia",
            "company_id": cls.company.id,
        })
        cls.centro = cls.env["account.analytic.account"].create({
            "name": "Centro prueba carencia",
            "plan_id": cls.analytic_plan.id,
            "type_costo": "fruta",
            "etapa_costo": "ope",
            "tipo_fruta": "conven",
            "fundo_id": cls.fundo.id,
        })
        cls.cuartel = cls.env["step.cuartel.line"].create({
            "name": "Cuartel prueba carencia",
            "centro_id": cls.centro.id,
        })
        cls.product = cls.env["product.template"].create({
            "name": "Fungicida prueba",
            "grupo_labor": "manten",
            "dia_carencia": 14,
            "hrs_reingreso": 24.0,
        })
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")

    # ------------------------------------------------------------------
    def _make_restriction(self, days_ago, carencia=14, reingreso=24.0, application_id=1):
        return self.env["step.phyto.restriction"].create({
            "cuartel_id": self.cuartel.id,
            "fundo_id": self.fundo.id,
            "company_id": self.company.id,
            "application_id": application_id,
            "application_ref": "BPA-TEST-%s" % application_id,
            "date_application": fields.Datetime.now() - timedelta(days=days_ago),
            "product_ids": [(6, 0, self.product.ids)],
            "carencia_days": carencia,
            "carencia_criterion": "label",
            "reingreso_hours": reingreso,
        })

    def _make_harvest(self, date):
        return self.env["step.cosecha.registry"].create({
            "name": "Cosecha prueba carencia",
            "type_tarea": "propio",
            "date": date,
            "cuartel_id": self.cuartel.id,
            "fundo_id": self.fundo.id,
            "company_id": self.company.id,
            "product_uom_id": self.uom_unit.id,
        })

    # ------------------------------------------------------------------
    def test_ventanas_se_calculan_desde_la_aplicacion(self):
        restriction = self._make_restriction(days_ago=2)
        self.assertEqual(
            restriction.harvest_allowed_from,
            restriction.date_application + timedelta(days=14),
        )
        self.assertEqual(
            restriction.reentry_allowed_from,
            restriction.date_application + timedelta(hours=24),
        )
        self.assertEqual(restriction.status, "carencia")
        self.assertTrue(restriction.harvest_blocked)

    def test_restriccion_vencida_queda_liberada(self):
        restriction = self._make_restriction(days_ago=30)
        self.assertEqual(restriction.status, "clear")
        self.assertFalse(restriction.harvest_blocked)
        self.assertFalse(restriction.reentry_blocked)

    def test_solo_reingreso_vigente(self):
        restriction = self._make_restriction(days_ago=0, carencia=0, reingreso=48.0)
        self.assertEqual(restriction.status, "reingreso")
        self.assertFalse(restriction.harvest_blocked)
        self.assertTrue(restriction.reentry_blocked)

    def test_evaluate_reporta_carencia_para_la_fecha_de_cosecha(self):
        self._make_restriction(days_ago=1)
        result = self.env["step.phyto.restriction"].evaluate(
            self.cuartel, fields.Datetime.now(),
        )
        self.assertEqual(result["status"], "carencia")
        self.assertTrue(result["allowed_from"])

    def test_evaluate_sin_cuartel_es_desconocido(self):
        result = self.env["step.phyto.restriction"].evaluate(
            self.env["step.cuartel.line"], fields.Datetime.now(),
        )
        self.assertEqual(result["status"], "unknown")

    # ------------------------------------------------------------------
    def test_politica_bloquear_impide_aprobar_en_carencia(self):
        self.company.step_phyto_policy = "block"
        self._make_restriction(days_ago=1)
        harvest = self._make_harvest(fields.Datetime.now())
        self.assertEqual(harvest.step_phyto_status, "carencia")
        with self.assertRaises(UserError):
            harvest.action_apro()
        self.assertEqual(harvest.state, "in")

    def test_politica_advertir_deja_aprobar_y_registra_alerta(self):
        self.company.step_phyto_policy = "warn"
        self._make_restriction(days_ago=1)
        harvest = self._make_harvest(fields.Datetime.now())
        harvest.action_apro()
        self.assertEqual(harvest.state, "apro")
        bodies = harvest.message_ids.mapped("body")
        self.assertTrue(any("carencia" in (body or "").lower() for body in bodies))
        self.assertTrue(
            any("<b>" in (body or "") for body in bodies),
            "La alerta debe llegar al historial como HTML, no como texto escapado.",
        )

    def test_politica_desactivada_no_interfiere(self):
        self.company.step_phyto_policy = "off"
        self._make_restriction(days_ago=1)
        harvest = self._make_harvest(fields.Datetime.now())
        harvest.action_apro()
        self.assertEqual(harvest.state, "apro")

    def test_cosecha_fuera_de_carencia_aprueba_con_bloqueo_activo(self):
        self.company.step_phyto_policy = "block"
        self._make_restriction(days_ago=30)
        harvest = self._make_harvest(fields.Datetime.now())
        self.assertEqual(harvest.step_phyto_status, "clear")
        harvest.action_apro()
        self.assertEqual(harvest.state, "apro")

    def test_cosecha_sin_cuartel_no_se_bloquea(self):
        self.company.step_phyto_policy = "block"
        self._make_restriction(days_ago=1)
        harvest = self._make_harvest(fields.Datetime.now())
        harvest.cuartel_id = False
        harvest.action_apro()
        self.assertEqual(harvest.state, "apro")

    # ------------------------------------------------------------------
    def test_transiciones_de_cosecha_dan_mensaje_legible(self):
        """Regresión: ``step_cosecha`` usaba UserError sin importarlo.

        El resultado era un NameError y un «Ocurrió un error» genérico en
        lugar de la validación de negocio que el usuario debía leer.
        """
        self.company.step_phyto_policy = "off"
        harvest = self._make_harvest(fields.Datetime.now())
        with self.assertRaises(UserError):
            harvest.action_in()          # aún está en 'in'
        harvest.action_apro()
        with self.assertRaises(UserError):
            harvest.action_apro()        # ya está en 'apro'
        harvest.action_in()
        self.assertEqual(harvest.state, "in")

    def test_refresh_es_idempotente(self):
        model = self.env["step.phyto.restriction"]
        before = model.search_count([])
        model.refresh()
        model.refresh()
        after = model.search_count([])
        self.assertEqual(before, after, "Refrescar dos veces no debe duplicar restricciones.")

    def test_criterio_mayor_toma_el_valor_mas_restrictivo(self):
        model = self.env["step.phyto.restriction"]
        self.assertEqual(model._carencia_for_product(self.product, "label"), 14)
        self.assertEqual(model._carencia_for_product(self.product, "max"), 14)

    def test_criterio_de_destino_sin_dato_cae_a_etiqueta(self):
        """Un mercado sin días cargados no puede relajar el control legal."""
        model = self.env["step.phyto.restriction"]
        self.assertEqual(model._carencia_for_product(self.product, "eu"), 14)
