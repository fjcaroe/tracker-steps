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

UF_TOPE_IAS = 90  # tope UF art. 172
ANIOS_TOPE_IAS = 11  # tope años art. 163


def _is_business_day(date, company_holidays):
    return date.weekday() < 5 and date not in company_holidays


def _months_and_fraction_days(date_from, date_to):
    """Réplica de 'Meses = días/30' del anexo: meses enteros + días de
    fracción del último mes incompleto."""
    if not date_from or not date_to or date_to <= date_from:
        return 0, 0
    total_days = (date_to - date_from).days
    months = total_days // 30
    fraction_days = total_days % 30
    return months, fraction_days


def compute_feriado_proporcional(date_from, date_to, daily_wage, company_holidays=frozenset()):
    """Feriado proporcional (vacaciones no tomadas). Devuelve un dict con
    el detalle completo para trazabilidad."""
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
    tope UF90 sobre la renta."""
    total_days = (date_to - date_from).days if (date_from and date_to and date_to > date_from) else 0
    years = total_days // 365
    remainder_days = total_days % 365
    fraction_years = 1 if remainder_days > 182 else 0  # > 6 meses
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
