# -*- coding: utf-8 -*-
"""Motor de cálculo de finiquito. Fórmulas transcritas del anexo
"ERP agrícola, Mejora Nómina, finiquitos.docx" (feriado proporcional,
IAS anual art.163, IAS mensual art.159 N°5, mes de aviso), y del anexo
DT sobre feriado proporcional (art. 73 Código del Trabajo).

Este módulo es lógica pura (sin ORM) para poder testearse de forma
aislada y para que hr.severance simplemente registre sus resultados.
"""
import math
from datetime import timedelta

from dateutil.relativedelta import relativedelta

UF_TOPE_IAS = 90  # tope UF art. 172
ANIOS_TOPE_IAS = 11  # tope años art. 163


def _is_business_day(date, company_holidays):
    return date.weekday() < 5 and date not in company_holidays


def _months_and_fraction_days(date_from, date_to):
    """Meses calendario completos entre dos fechas + días de fracción del
    mes incompleto (diferencia calendario, NO días totales/30).

    Verificado contra el ejemplo textual del anexo DT: 15-mar-2021 a
    17-nov-2021 = 8 meses y 2 días (no 8 meses y 7 días, que es lo que
    daría días-totales // 30).
    """
    if not date_from or not date_to or date_to <= date_from:
        return 0, 0
    rd = relativedelta(date_to, date_from)
    months = rd.years * 12 + rd.months
    fraction_days = rd.days
    return months, fraction_days


def compute_feriado_proporcional(date_from, date_to, daily_wage, company_holidays=frozenset()):
    """Feriado proporcional (vacaciones no tomadas). Devuelve un dict con
    el detalle completo para trazabilidad.

    NOTA sobre window_end: se camina floor(días hábiles entitled) días
    hábiles desde el día siguiente al término. El anexo DT reporta en su
    ejemplo textual un día calendario adicional (por la fracción, ej.
    0,08) que puede o no ser hábil; como esa fracción ya está incluida en
    'dias_habiles_entitled' y por ende en 'final_days', el monto a pagar
    no cambia — sólo podría variar en 1 el conteo de días inhábiles si
    ese día extra cae en fin de semana/festivo. Validar contra un caso
    real antes de producción si se requiere paridad exacta de fecha de
    ventana con el sistema de la DT.
    """
    months, fraction_days = _months_and_fraction_days(date_from, date_to)
    dias_habiles_entitled = round(months * 1.25 + fraction_days * 0.04167, 2)
    walk_days = int(math.floor(dias_habiles_entitled))
    start = date_to + timedelta(days=1)
    non_business_in_window = 0
    end_date = start
    counted = 0
    cursor = start
    if walk_days > 0:
        while counted < walk_days:
            if _is_business_day(cursor, company_holidays):
                counted += 1
                end_date = cursor
            else:
                non_business_in_window += 1
            if counted < walk_days:
                cursor += timedelta(days=1)
    else:
        end_date = start - timedelta(days=1)
    final_days = round(dias_habiles_entitled + non_business_in_window, 2)
    amount = round(final_days * (daily_wage or 0), 0)
    return {
        "months": months,
        "fraction_days": fraction_days,
        "dias_habiles_entitled": dias_habiles_entitled,
        "window_start": start,
        "window_end": end_date,
        "non_business_days_in_window": non_business_in_window,
        "final_days": final_days,
        "daily_wage": daily_wage,
        "amount": amount,
    }


def compute_ias_anual(date_from, date_to, renta_ias, uf_value):
    """Indemnización por años de servicio (art. 163), tope 11 años y
    tope UF90 sobre la renta. Redondeo de fracción superior a seis meses
    paga un año adicional (diferencia calendario, no días/365)."""
    if not date_from or not date_to or date_to <= date_from:
        years, remainder_months, remainder_days = 0, 0, 0
    else:
        rd = relativedelta(date_to, date_from)
        years, remainder_months, remainder_days = rd.years, rd.months, rd.days
    fraction_years = 1 if (remainder_months * 30 + remainder_days) > 180 else 0
    anios_ias = years + fraction_years
    if anios_ias < 1:
        return {"anios_ias": 0, "renta_ias": 0, "amount": 0, "applies": False, "tope_uf_aplicado": False}
    anios_ias = min(anios_ias, ANIOS_TOPE_IAS)
    tope_monto = UF_TOPE_IAS * uf_value if uf_value else None
    tope_aplicado = bool(tope_monto and renta_ias > tope_monto)
    renta_aplicada = min(renta_ias, tope_monto) if tope_monto else renta_ias
    amount = round(anios_ias * renta_aplicada, 0)
    return {
        "anios_ias": anios_ias,
        "renta_ias": renta_aplicada,
        "amount": amount,
        "applies": True,
        "tope_uf_aplicado": tope_aplicado,
    }


def compute_ias_mensual(date_from, date_to, renta_ias):
    """Indemnización por meses de servicio (art. 159 N°5, temporada):
    2,5 días hábiles por mes trabajado."""
    months, fraction_days = _months_and_fraction_days(date_from, date_to)
    if months < 1:
        return {"meses_ias": 0, "dias_a_pagar": 0, "amount": 0, "applies": False}
    fraction_month = 1 if fraction_days > 15 else 0
    meses_ias = months + fraction_month
    dias_a_pagar = round(meses_ias * 2.5, 2)
    sueldo_dia = round((renta_ias or 0) / 30, 2)
    amount = round(dias_a_pagar * sueldo_dia, 0)
    return {
        "meses_ias": meses_ias,
        "dias_a_pagar": dias_a_pagar,
        "sueldo_dia": sueldo_dia,
        "amount": amount,
        "applies": True,
    }


def compute_mes_aviso(ultima_remuneracion):
    """Indemnización sustitutiva de aviso previo: 1 sueldo, causal
    necesidades de la empresa."""
    return {"amount": round(ultima_remuneracion or 0, 0)}
