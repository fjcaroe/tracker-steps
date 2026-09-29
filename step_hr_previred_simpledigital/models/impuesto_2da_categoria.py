"""Corrige el scraping mensual del Impuesto Único de 2da Categoría (SII).

`l10n_cl_simpledigital_payroll.impuesto_2da_categoria.cron_scraping_impuesto_2da_categoria`
asume que el mes a registrar es el mes calendario de hoy
(`fields.Date.today()`). El SII a veces publica la tabla del mes siguiente
antes de que termine el mes en curso (visto el 2026-09-29: la página ya
mostraba "Octubre 2026" como primer período listado). En ese caso el
registro creado con el mes calendario ("Septiembre 2026") no coincide con
`validate_date_with_site` y el scraping aborta dejando el registro en cero
(ticket T39).

Se sobreescribe el método para que el mes a registrar sea el que el sitio
del SII está publicando realmente, no el mes calendario. `hr_payslip.py`
busca el registro por rango de fecha del período de la nómina
(`date >= date_from and date <= date_to`), así que adelantar el registro
del mes siguiente cuando el SII lo publica antes no afecta el cálculo de
nóminas de meses anteriores.
"""

import logging

import requests
from bs4 import BeautifulSoup

from odoo import fields, models

_logger = logging.getLogger(__name__)

_MESES_ES = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11,
    "Diciembre": 12,
}

SII_IMPUESTO_2DA_CATEGORIA_URL = (
    "https://www.sii.cl/valores_y_fechas/impuesto_2da_categoria/impuesto2026.htm"
)


class Impuesto2daCategoria(models.Model):
    _inherit = "impuesto_2da_categoria"

    def _step_previred_periodo_publicado_sii(self):
        """Devuelve (año, mes) que el sitio del SII está publicando ahora, o None."""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(
                SII_IMPUESTO_2DA_CATEGORIA_URL, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
        except Exception:
            _logger.exception(
                "No se pudo consultar el sitio del SII para el Impuesto 2da Categoria")
            return None

        mes_nombre, anio_str = self.get_selected_period(soup, SII_IMPUESTO_2DA_CATEGORIA_URL)
        if not mes_nombre or not anio_str or mes_nombre not in _MESES_ES:
            return None
        return int(anio_str), _MESES_ES[mes_nombre]

    def cron_scraping_impuesto_2da_categoria(self):
        """Crea/actualiza el registro del período que el SII publica hoy.

        En vez de asumir que ese período es el mes calendario actual (como
        hace el método del proveedor), se detecta primero en el sitio del
        SII y se usa ese año/mes. Si la detección falla, se cae al
        comportamiento original del proveedor como respaldo.
        """
        periodo = self._step_previred_periodo_publicado_sii()
        if not periodo:
            _logger.warning(
                "No se pudo detectar el periodo publicado por el SII; "
                "se usa el mes calendario como respaldo (comportamiento original).")
            return super().cron_scraping_impuesto_2da_categoria()

        anio, mes = periodo
        target_month = fields.Date.from_string("%04d-%02d-01" % (anio, mes))
        next_month = (
            target_month.replace(year=target_month.year + 1, month=1)
            if target_month.month == 12
            else target_month.replace(month=target_month.month + 1)
        )

        existing_record = self.search([
            ("date", ">=", target_month),
            ("date", "<", next_month),
        ], limit=1)

        if existing_record:
            _logger.info(
                "Actualizando registro existente de Impuesto 2da Categoria "
                "para %04d-%02d (detectado desde el sitio SII)", anio, mes)
            existing_record.action_scraping_impuesto_2da_categoria()
            return existing_record

        nombre_mes = [k for k, v in _MESES_ES.items() if v == mes][0]
        new_record = self.create({
            "name": "Indicadores Impuesto 2da Categoria %s %04d" % (nombre_mes, anio),
            "date": target_month,
        })
        new_record.action_scraping_impuesto_2da_categoria()
        return new_record
