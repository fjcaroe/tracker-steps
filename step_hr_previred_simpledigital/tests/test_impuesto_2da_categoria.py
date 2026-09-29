"""Regresión T39: el registro de Impuesto 2da Categoria debe crearse/
actualizarse para el mes que el SII publica realmente, no para el mes
calendario de hoy (el SII a veces publica el mes siguiente antes de que
termine el mes en curso)."""

from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImpuesto2daCategoria(TransactionCase):

    def _model(self):
        return self.env["impuesto_2da_categoria"]

    def test_usa_el_periodo_publicado_por_el_sii_no_el_mes_de_hoy(self):
        """Caso del ticket: hoy es septiembre pero el SII ya publicó octubre."""
        model = self._model()
        with patch.object(
            type(model), "_step_previred_periodo_publicado_sii",
            return_value=(2026, 10),
        ), patch.object(
            type(model), "action_scraping_impuesto_2da_categoria",
            lambda self: self,
        ):
            record = model.cron_scraping_impuesto_2da_categoria()

        self.assertEqual(record.date.month, 10)
        self.assertEqual(record.date.year, 2026)
        self.assertIn("Octubre", record.name)

    def test_actualiza_el_registro_existente_del_periodo_detectado(self):
        model = self._model()
        existing = model.create({"name": "Octubre 2026", "date": "2026-10-05"})

        with patch.object(
            type(model), "_step_previred_periodo_publicado_sii",
            return_value=(2026, 10),
        ), patch.object(
            type(model), "action_scraping_impuesto_2da_categoria",
            lambda self: self,
        ):
            record = model.cron_scraping_impuesto_2da_categoria()

        self.assertEqual(record.id, existing.id)
        self.assertEqual(model.search_count([
            ("date", ">=", "2026-10-01"), ("date", "<", "2026-11-01"),
        ]), 1)

    def test_si_no_se_detecta_el_periodo_cae_al_comportamiento_original(self):
        """Si no se puede determinar el período del SII, se delega en el
        método original del proveedor (mismo comportamiento que antes del
        fix, incluido su manejo de errores) en vez de fallar en silencio
        o quedar en un estado indefinido."""
        model = self._model()
        with patch.object(
            type(model), "_step_previred_periodo_publicado_sii",
            return_value=None,
        ), patch("requests.get", side_effect=ConnectionError("sin red (test)")):
            with self.assertRaises(ConnectionError):
                model.cron_scraping_impuesto_2da_categoria()

        # El proveedor deja constancia del fallo con un registro "ERROR: ...".
        self.assertTrue(model.search([("name", "like", "ERROR:")]))
