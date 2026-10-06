"""Lee la tabla mensual oficial del SII sin depender del scraper del proveedor."""

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_MESES = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
    "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)
_PERIODO = re.compile(r"^({})\s+(\d{{4}})$".format("|".join(_MESES)))
_URL = "https://www.sii.cl/valores_y_fechas/impuesto_2da_categoria/impuesto{}.htm"
_LINEAS = ("second", "third", "fourth", "fifth", "sixth", "seventh", "eighth")


def _numero(texto):
    """Convierte montos y factores chilenos; un dato ausente es un error."""
    limpio = texto.replace("$", "").replace(" ", "").replace("\xa0", "")
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(limpio)
    except InvalidOperation as exc:
        raise UserError("Valor inválido en la tabla de impuestos del SII: %s" % texto) from exc
    if not valor.is_finite() or valor < 0:
        raise UserError("Valor inválido en la tabla de impuestos del SII: %s" % texto)
    return valor


def _tablas_publicadas(soup):
    tablas = {}
    for bloque in soup.select("div.meses"):
        titulo = bloque.find("h3")
        match = _PERIODO.match(titulo.get_text(" ", strip=True)) if titulo else None
        tabla = bloque.find("table")
        if match and tabla:
            periodo = (int(match.group(2)), _MESES.index(match.group(1)) + 1)
            tablas[periodo] = tabla
    if not tablas:
        raise UserError("El SII no entregó tablas mensuales de Impuesto Único.")
    return tablas


def _valores_mensuales(tabla):
    """Exige ocho tramos mensuales coherentes antes de escribir en Odoo."""
    filas = []
    en_mensual = False
    for fila in tabla.find_all("tr"):
        celdas = [celda.get_text(" ", strip=True) for celda in fila.find_all("td")]
        if not celdas:
            continue
        etiqueta = celdas[0].upper()
        if etiqueta == "MENSUAL":
            en_mensual = True
        elif etiqueta in ("QUINCENAL", "SEMANAL", "DIARIO") and en_mensual:
            break
        if en_mensual:
            if len(celdas) != 6:
                raise UserError("El SII cambió el formato de los tramos mensuales.")
            filas.append(celdas)
    if len(filas) != 8 or filas[0][3].lower() != "exento":
        raise UserError("El SII no entregó los ocho tramos mensuales esperados.")

    exento_hasta = _numero(filas[0][2])
    if exento_hasta <= 0:
        raise UserError("El tramo exento del SII está vacío.")
    valores = {"first_line_to": float(exento_hasta)}
    anterior = exento_hasta
    factores = (Decimal("0.04"), Decimal("0.08"), Decimal("0.135"),
                Decimal("0.23"), Decimal("0.304"), Decimal("0.35"), Decimal("0.4"))
    for indice, (prefijo, factor_esperado) in enumerate(zip(_LINEAS, factores), start=1):
        celdas = filas[indice]
        desde = _numero(celdas[1])
        factor = _numero(celdas[3])
        rebaja = _numero(celdas[4])
        if desde != anterior + Decimal("0.01") or factor != factor_esperado or rebaja <= 0:
            raise UserError("Los tramos mensuales del SII están incompletos o no son coherentes.")
        valores[prefijo + "_line_from"] = float(desde)
        valores[prefijo + "_line_factor"] = float(factor)
        valores[prefijo + "_line_tasa_rebaja"] = float(rebaja)
        if indice < 7:
            hasta = _numero(celdas[2])
            if hasta <= desde:
                raise UserError("Los límites de renta del SII no son coherentes.")
            valores[prefijo + "_line_to"] = float(hasta)
            anterior = hasta
        elif celdas[2].upper().replace("Á", "A") != "Y MAS":
            raise UserError("El último tramo del SII no indica 'Y MÁS'.")
    return valores


class Impuesto2daCategoria(models.Model):
    _inherit = "impuesto_2da_categoria"

    def _step_sii_tablas(self, anio):
        try:
            respuesta = requests.get(_URL.format(anio), headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            respuesta.raise_for_status()
        except requests.RequestException as exc:
            raise UserError("No fue posible consultar la tabla del SII para %s: %s" % (anio, exc)) from exc
        # El SII cierra dos <th> con </td>; html.parser trunca la tabla.
        # lxml recupera el tbody real igual que un navegador.
        return _tablas_publicadas(BeautifulSoup(respuesta.content, "lxml"))

    def action_scraping_impuesto_2da_categoria(self):
        self.ensure_one()
        if not self.date:
            raise UserError("Defina la fecha del período que desea actualizar.")
        fecha = fields.Date.to_date(self.date)
        periodo = (fecha.year, fecha.month)
        tabla = self._step_sii_tablas(fecha.year).get(periodo)
        if tabla is None:
            raise UserError("El SII aún no publicó la tabla de %s %s." % (_MESES[fecha.month - 1], fecha.year))
        valores = _valores_mensuales(tabla)
        self.write(valores)
        _logger.info("Actualizada tabla SII de %s %s (%s campos)", _MESES[fecha.month - 1], fecha.year, len(valores))
        return True

    def cron_scraping_impuesto_2da_categoria(self):
        anio_actual = fields.Date.today().year
        tablas = self._step_sii_tablas(anio_actual)
        periodo = max(tablas)
        anio, mes = periodo
        # Analizar antes de crear el registro: una tabla vacía nunca se guarda como cero.
        valores = _valores_mensuales(tablas[periodo])
        inicio = date(anio, mes, 1)
        fin = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
        registro = self.search([("date", ">=", inicio), ("date", "<", fin)], limit=1)
        if registro:
            registro.write(valores)
        else:
            registro = self.create({
                "name": "Indicadores Impuesto 2da Categoria %s %s" % (_MESES[mes - 1], anio),
                "date": inicio,
                **valores,
            })
        return registro
