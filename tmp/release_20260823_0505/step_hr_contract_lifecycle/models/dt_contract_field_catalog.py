# -*- coding: utf-8 -*-
"""Catálogo de columnas del CSV de registro masivo de contratos DT
(Anexo A5). El orden y nombre de columnas es el exigido por el
instructivo. Los getters son best-effort: donde el dato todavía no está
modelado en hr.contract se deja vacío y se marca en REQUIRED_COLUMNS para
que la prevalidación lo reporte como fila con error, en vez de subir un
archivo con datos inventados.

NOTA: la matriz completa de obligatorio/opcional/condicional de las 91
columnas debe terminar de contrastarse con el instructivo completo
(36 páginas) antes de un envío real a producción; aquí sólo se marcan
como obligatorias las columnas cuya obligatoriedad es inequívoca.
"""


def _fmt_date(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _rut_parts(rut):
    """Separa RUT/DV si vienen juntos con guión (12.345.678-9)."""
    if not rut:
        return "", ""
    clean = rut.replace(".", "").strip()
    if "-" in clean:
        num, dv = clean.rsplit("-", 1)
        return num.strip(), dv.strip()
    return clean, ""


DT_CONTRACT_COLUMNS = [
    ("CATEGORIA_CONTRATO", lambda c: dict([
        ("temporada", "1"), ("trato", "2"), ("plazo_fijo", "3"), ("permanente", "4"),
    ]).get(c.labor_modality, "")),
    ("COMUNA_CELEBRACION", lambda c: c.commune_signature_id.code or c.commune_signature_id.name or ""),
    ("FECHA_SUSCRPCION", lambda c: _fmt_date(c.date_signature)),
    ("RUT_TRABAJADOR", lambda c: _rut_parts(c.employee_id.identification_id)[0] if not c.is_foreign_worker else ""),
    ("DNI_TRABAJADOR", lambda c: c.passport_number or ""),
    ("FECHA_NACIMIENTO", lambda c: _fmt_date(c.employee_id.birthday)),
    ("NOMBRES", lambda c: c.employee_id.name.split(" ")[0] if c.employee_id.name else ""),
    ("APELLIDOS", lambda c: " ".join(c.employee_id.name.split(" ")[1:]) if c.employee_id.name else ""),
    ("SEXO", lambda c: {"male": "M", "female": "F"}.get(c.employee_id.gender, "")),
    ("NACIONALIDAD", lambda c: c.employee_id.country_id.name or ""),
    ("EMAIL", lambda c: c.employee_id.work_email or c.employee_id.private_email or ""),
    ("TELEFONO", lambda c: c.employee_id.mobile_phone or c.employee_id.work_phone or ""),
    ("COMUNA", lambda c: c.employee_id.private_city or ""),
    ("CALLE", lambda c: c.employee_id.private_street or ""),
    ("NUMERO", lambda c: ""),
    ("DPTO", lambda c: ""),
    ("DECLARACION_DISCAPACIDAD", lambda c: "1" if c.has_disability else "0"),
    ("DECLARACION_INVALIDEZ", lambda c: "0"),
    ("FUNCIONES", lambda c: c.job_id.name or ""),
    ("SUBCONTRATACION", lambda c: "1" if c.is_subcontracted else "0"),
    ("RUT_EMPRESA_PRINCIPAL", lambda c: _rut_parts(c.main_company_partner_id.vat)[0]),
    ("EST", lambda c: "1" if c.is_temporary_work else "0"),
    ("RUT_EMPRESA_USUARIA", lambda c: _rut_parts(c.user_company_partner_id.vat)[0]),
    ("FAENA_COMUNA", lambda c: c.work_commune_id.name or ""),
    ("FAENA_CALLE", lambda c: c.work_street or ""),
    ("FAENA_NUMERO", lambda c: c.work_number or ""),
    ("FAENA_DPTO", lambda c: c.work_complement or ""),
    ("ZONA_GEOGRAFICA_1", lambda c: ""),
    ("ZONA_GEOGRAFICA_2", lambda c: ""),
    ("ZONA_GEOGRAFICA_3", lambda c: ""),
    ("ZONA_GEOGRAFICA_4", lambda c: ""),
    ("ZONA_GEOGRAFICA_5", lambda c: ""),
    ("SUELDO_BASE", lambda c: "%d" % (c.wage or 0)),
    ("MONTO_IMPONIBLE", lambda c: "%d" % (c.wage or 0)),
    ("HABER_1", lambda c: ""), ("MONTO_1", lambda c: ""), ("PER_DEVENGAMIENTO_1", lambda c: ""),
    ("HABER_2", lambda c: ""), ("MONTO_2", lambda c: ""), ("PER_DEVENGAMIENTO_2", lambda c: ""),
    ("HABER_3", lambda c: ""), ("MONTO_3", lambda c: ""), ("PER_DEVENGAMIENTO_3", lambda c: ""),
    ("HABER_4", lambda c: ""), ("MONTO_4", lambda c: ""), ("PER_DEVENGAMIENTO_4", lambda c: ""),
    ("HABER_5", lambda c: ""), ("MONTO_5", lambda c: ""), ("PER_DEVENGAMIENTO_5", lambda c: ""),
    ("GRAT_FORMA_PAGO", lambda c: ""),
    ("GRAT_MODALIDAD", lambda c: ""),
    ("GRAT_PERIODO_PAGO", lambda c: ""),
    ("REM_PERIODO_PAGO", lambda c: "MENSUAL"),
    ("REM_FECHA_PAGO", lambda c: ""),
    ("REM_FORMA_PAGO", lambda c: ""),
    ("REM_ANTICIPO", lambda c: "0"),
    ("REM_AFP", lambda c: c.afp_id.name or ""),
    ("REM_SALUD", lambda c: c.isapre_id.name or "FONASA"),
    ("REM_OTROS_PACTOS", lambda c: ""),
    ("TIPO_JORNADA", lambda c: c.tipo_de_jornada or ""),
    ("NRO_RESOLUCION", lambda c: c.excepcion_jornada_resolution or ""),
    ("FECHA_RESOLUCION", lambda c: _fmt_date(c.excepcion_jornada_date)),
    ("DURACION_JORNADA", lambda c: str(c.resource_calendar_id.hours_per_week or "")),
    ("TURNOS", lambda c: ""),
    ("TIEMPO_COLACION", lambda c: str(c.colacion_minutes or "")),
    ("T_COLACION_IMP", lambda c: "1" if c.colacion_imputable else "0"),
    ("T_COLACION_NO_IMP", lambda c: "0" if c.colacion_imputable else "1"),
    ("ROTACION", lambda c: "0"),
    ("NRO_DIAS_DIST_JOR", lambda c: ""),
    ("LUNES_HORA_INICIO", lambda c: ""), ("LUNES_HORA_TERMINO", lambda c: ""),
    ("MARTES_HORA_INICIO", lambda c: ""), ("MARTES_HORA_TERMINO", lambda c: ""),
    ("MIERCOLES_HORA_INICIO", lambda c: ""), ("MIERCOLES_HORA_TERMINO", lambda c: ""),
    ("JUEVES_HORA_INICIO", lambda c: ""), ("JUEVES_HORA_TERMINO", lambda c: ""),
    ("VIERNES_HORA_INICIO", lambda c: ""), ("VIERNES_HORA_TERMINO", lambda c: ""),
    ("SABADO_HORA_INICIO", lambda c: ""), ("SABADO_HORA_TERMINO", lambda c: ""),
    ("DOMINGO_HORA_INICIO", lambda c: ""), ("DOMINGO_HORA_TERMINO", lambda c: ""),
    ("TIPO_CONTRATO", lambda c: dict([
        ("temporada", "1"), ("trato", "2"), ("plazo_fijo", "3"), ("permanente", "4"),
    ]).get(c.labor_modality, "")),
    ("FECHA_INI_RELABORAL", lambda c: _fmt_date(c.date_start)),
    ("FECHA_FIN_RELABORAL", lambda c: _fmt_date(c.date_end)),
    ("OTROS_INDEMNIZACIONES", lambda c: ""),
    ("OTROS_FERIADOS", lambda c: ""),
    ("OTROS_NEGOCIACIONES", lambda c: ""),
    ("OTROS_PROPINTELECTUAL", lambda c: ""),
    ("OTROS_LICMEDICA", lambda c: ""),
    ("OTROS_SALACUNA", lambda c: ""),
    ("OTROS_PERMISOS", lambda c: ""),
    ("OTROS_CONESPECIALES", lambda c: ""),
    ("OTROS_SEGUROS", lambda c: ""),
    ("OTROS_STOCK", lambda c: ""),
    ("OTROS_INSTCOLECTIVO", lambda c: ""),
    ("AFECTO_A", lambda c: ""),
    ("FECHA_INI_INSTCOLECTIVO", lambda c: ""),
    ("FECHA_FIN_INSTCOLECTIVO", lambda c: ""),
]

REQUIRED_COLUMNS = {
    "CATEGORIA_CONTRATO", "COMUNA_CELEBRACION", "FECHA_SUSCRPCION",
    "NOMBRES", "APELLIDOS", "SEXO", "FUNCIONES", "SUELDO_BASE",
    "MONTO_IMPONIBLE", "REM_AFP", "REM_SALUD", "TIPO_JORNADA",
    "DURACION_JORNADA", "TIPO_CONTRATO", "FECHA_INI_RELABORAL",
}


def build_row(contract):
    return {name: getter(contract) for name, getter in DT_CONTRACT_COLUMNS}


def validate_row(contract):
    row = build_row(contract)
    missing = [col for col in REQUIRED_COLUMNS if not row.get(col)]
    if not contract.is_foreign_worker and not row.get("RUT_TRABAJADOR"):
        missing.append("RUT_TRABAJADOR")
    if contract.is_foreign_worker and not row.get("DNI_TRABAJADOR"):
        missing.append("DNI_TRABAJADOR")
    return missing
