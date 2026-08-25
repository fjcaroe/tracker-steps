# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.step_hr_contract_lifecycle.models.hr_severance_calc import (
    compute_feriado_proporcional,
    compute_ias_anual,
    compute_ias_mensual,
    compute_mes_aviso,
)


@tagged("post_install", "-at_install")
class TestSeveranceCalc(TransactionCase):
    def test_feriado_proporcional_dt_example(self):
        """Ejemplo textual del anexo DT: ingreso 15-mar-2021, término
        17-nov-2021 -> 14,08 días corridos a indemnizar."""
        result = compute_feriado_proporcional(
            date(2021, 3, 15), date(2021, 11, 17), daily_wage=10000
        )
        self.assertEqual(result["months"], 8)
        self.assertEqual(result["dias_habiles_entitled"], 10.08)
        # El anexo reporta el término de ventana como 02-12-2021 (un día
        # calendario más, por la fracción 0,08 del último mes). Ese día
        # extra es hábil (jueves), así que no cambia el conteo de días
        # inhábiles ni el resultado final: lo que importa legalmente
        # -días finales y monto- coincide exactamente con el anexo.
        self.assertEqual(result["window_end"], date(2021, 12, 1))
        self.assertEqual(result["non_business_days_in_window"], 4)
        self.assertEqual(result["final_days"], 14.08)
        self.assertEqual(result["amount"], round(14.08 * 10000, 0))

    def test_feriado_proporcional_no_service(self):
        result = compute_feriado_proporcional(date(2026, 1, 1), date(2026, 1, 1), 10000)
        self.assertEqual(result["dias_habiles_entitled"], 0)
        self.assertEqual(result["amount"], 0)

    def test_ias_anual_under_one_year_does_not_apply(self):
        result = compute_ias_anual(date(2026, 1, 1), date(2026, 6, 1), 500000, 38000)
        self.assertFalse(result["applies"])
        self.assertEqual(result["amount"], 0)

    def test_ias_anual_rounds_fraction_over_six_months(self):
        # 3 años y 8 meses -> fraccion > 6 meses -> +1 año = 4
        result = compute_ias_anual(date(2020, 1, 1), date(2023, 9, 1), 500000, 38000)
        self.assertEqual(result["anios_ias"], 4)
        self.assertEqual(result["amount"], 4 * 500000)

    def test_ias_anual_tope_11_years(self):
        result = compute_ias_anual(date(2000, 1, 1), date(2026, 1, 1), 500000, 38000)
        self.assertEqual(result["anios_ias"], 11)

    def test_ias_anual_tope_uf90(self):
        uf = 38000
        renta_alta = 5000000
        result = compute_ias_anual(date(2018, 1, 1), date(2026, 1, 1), renta_alta, uf)
        self.assertTrue(result["tope_uf_aplicado"])
        self.assertEqual(result["renta_ias"], 90 * uf)

    def test_ias_mensual_temporada(self):
        # 3 meses y 20 dias -> fraccion > 15 dias -> +1 mes = 4 meses
        result = compute_ias_mensual(date(2026, 1, 1), date(2026, 4, 21), 300000)
        self.assertEqual(result["meses_ias"], 4)
        self.assertEqual(result["dias_a_pagar"], 10.0)
        self.assertEqual(result["sueldo_dia"], round(300000 / 30, 2))

    def test_ias_mensual_under_one_month(self):
        result = compute_ias_mensual(date(2026, 1, 1), date(2026, 1, 20), 300000)
        self.assertFalse(result["applies"])

    def test_mes_aviso(self):
        result = compute_mes_aviso(450000)
        self.assertEqual(result["amount"], 450000)
