"""T39: importar tramos mensuales publicados, sin crear tablas vacías."""

from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.impuesto_2da_categoria import _tablas_publicadas, _valores_mensuales


def _tabla_octubre():
    # Valores oficiales de octubre de 2026; solo la sección mensual relevante.
    filas = [
        ("MENSUAL", "-.-", "$ 974.038,50", "Exento", "-.-", "Exento"),
        ("", "$ 974.038,51", "$ 2.164.530,00", "0,04", "$ 38.961,54", "2,20%"),
        ("", "$ 2.164.530,01", "$ 3.607.550,00", "0,08", "$ 125.542,74", "4,52%"),
        ("", "$ 3.607.550,01", "$ 5.050.570,00", "0,135", "$ 323.957,99", "7,09%"),
        ("", "$ 5.050.570,01", "$ 6.493.590,00", "0,23", "$ 803.762,14", "10,62%"),
        ("", "$ 6.493.590,01", "$ 8.658.120,00", "0,304", "$ 1.284.287,80", "15,57%"),
        ("", "$ 8.658.120,01", "$ 22.366.810,00", "0,35", "$ 1.682.561,32", "27,48%"),
        ("", "$ 22.366.810,01", "Y MÁS", "0,4", "$ 2.800.901,82", "MÁS DE 27,48%"),
        ("QUINCENAL", "-.-", "$ 487.019,25", "Exento", "-.-", "Exento"),
    ]
    html = "<div class='meses'><h3>Octubre 2026</h3><table>"
    html += "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in fila) for fila in filas)
    return BeautifulSoup(html + "</table></div>", "html.parser")


@tagged("post_install", "-at_install")
class TestImpuesto2daCategoria(TransactionCase):

    def test_cron_importa_montos_oficiales_en_octubre(self):
        model = self.env["impuesto_2da_categoria"]
        tablas = _tablas_publicadas(_tabla_octubre())
        with patch.object(type(model), "_step_sii_tablas", return_value=tablas):
            registro = model.cron_scraping_impuesto_2da_categoria()
        self.assertEqual(registro.date.month, 10)
        self.assertEqual(registro.first_line_to, 974038.5)
        self.assertEqual(registro.second_line_factor, 0.04)
        self.assertEqual(registro.eighth_line_tasa_rebaja, 2800901.82)

    def test_tabla_incompleta_no_crea_registro(self):
        model = self.env["impuesto_2da_categoria"]
        anteriores = model.search_count([("date", "=", "2026-10-01")])
        tabla = _tabla_octubre().find("table")
        tabla.find_all("tr")[3].decompose()
        with patch.object(type(model), "_step_sii_tablas", return_value={(2026, 10): tabla}):
            with self.assertRaises(UserError):
                model.cron_scraping_impuesto_2da_categoria()
        self.assertEqual(model.search_count([("date", "=", "2026-10-01")]), anteriores)

    def test_accion_manual_respeta_periodo_del_registro(self):
        model = self.env["impuesto_2da_categoria"]
        registro = model.create({"name": "Octubre 2026", "date": "2026-10-05"})
        tablas = _tablas_publicadas(_tabla_octubre())
        with patch.object(type(model), "_step_sii_tablas", return_value=tablas):
            registro.action_scraping_impuesto_2da_categoria()
        self.assertEqual(registro.second_line_to, 2164530)
        self.assertEqual(registro.seventh_line_factor, 0.35)

    def test_html_sii_con_cierre_incorrecto_de_cabecera(self):
        # El SII usa </td> para cerrar dos <th>; html.parser pierde el tbody.
        html = str(_tabla_octubre()).replace(
            "<table>", "<table><thead><tr><th>Períodos</th><th>Desde</th>"
            "<th>Hasta</th><th>Factor</th><th>Rebaja</td><th>Tasa</td>"
            "</tr></thead>")
        with patch("requests.get", return_value=Mock(content=html.encode())):
            tablas = self.env["impuesto_2da_categoria"]._step_sii_tablas(2026)
        self.assertEqual(_valores_mensuales(tablas[(2026, 10)])["first_line_to"], 974038.5)
