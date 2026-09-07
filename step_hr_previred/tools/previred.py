"""Especificación del archivo Previred y estructuras de datos del lote.

Este módulo es **puro**: no importa el ORM, no consulta la base y no depende
de `request`. Es la única definición del formato oficial, de modo que el TXT,
el Excel y las validaciones no puedan divergir entre sí.

Fuente de la especificación
---------------------------
Formato estándar largo variable, por separador — Previred.
https://www.previred.com/documents/FormatosArchivos/FormatoLargoVariablePorSeparador.pdf
Versión 98, agosto 2026; rige a partir de la remuneración de agosto 2026.

Reglas que la especificación fija y que aquí se codifican:

* 105 campos por registro, separados por «;». **Ninguno puede omitirse**: los
  numéricos van con ceros y los alfanuméricos en blanco, o Previred rechaza el
  archivo completo.
* Extensión TXT, CSV o ZIP. El XLSX que genera este módulo es un archivo de
  revisión para personas y **no** es cargable en Previred.
* Los campos numéricos son enteros sin decimales, sin ceros ni espacios entre
  el monto y el separador.
* Una línea anexa debe ir **inmediatamente después** de su línea principal; en
  caso contrario Previred no la contabiliza al generar planillas.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# --- identidad del formato --------------------------------------------------

SPEC_NAME = "Formato estándar largo variable, por separador"
SPEC_VERSION = "98"
SPEC_DATE = "2026-08"
SPEC_EFFECTIVE_FROM = "2026-08"
SPEC_URL = (
    "https://www.previred.com/documents/FormatosArchivos/"
    "FormatoLargoVariablePorSeparador.pdf"
)

# Las versiones se conservan para poder regenerar períodos históricos con la
# especificación que efectivamente regía. Nunca se elige una versión sólo por
# su secuencia: el perfil debe cubrir el período solicitado.
SPECIFICATIONS = {
    "84": {
        "date": "2025-07", "effective_from": "2025-08",
        "effective_to": "2026-07",
        "url": ("https://www.previred.com/wp-content/uploads/2025/07/"
                "FormatoLargoVariablePorSeparador-Reforma-5.pdf"),
    },
    "98": {
        "date": SPEC_DATE, "effective_from": SPEC_EFFECTIVE_FROM,
        "effective_to": "", "url": SPEC_URL,
    },
}

#: Número de campos del registro. La especificación prohíbe omitir cualquiera.
FIELD_COUNT = 105

#: Separador de campos.
SEPARATOR = ";"

#: Fin de línea. Previred consume archivos de texto plano estilo Windows y es
#: lo que el generador vigente de Demo-SyS ya emite; no se cambia.
LINE_ENDING = "\r\n"

#: Codificación de salida. Los nombres se transliteran a ASCII antes de
#: escribir (ver `strip_accents`), así que latin-1 y utf-8 coinciden byte a
#: byte; se declara utf-8 sin BOM, que es lo que emiten ambos motores hoy.
ENCODING = "utf-8"

#: Previred **no** admite BOM: es un archivo de texto plano por posición de
#: separador y un BOM desplazaría el primer campo.
USE_BOM = False

# --- tipos de línea (Tabla N°6 de la especificación) ------------------------

LINE_PRINCIPAL = "00"
LINE_ADDITIONAL = "01"
LINE_SECOND_CONTRACT = "02"
LINE_VOLUNTARY = "03"

LINE_TYPE_LABELS = {
    LINE_PRINCIPAL: "Línea principal o base",
    LINE_ADDITIONAL: "Línea adicional",
    LINE_SECOND_CONTRACT: "Segundo contrato o pagos adicionales",
    LINE_VOLUNTARY: "Movimiento de personal de afiliado voluntario",
}

#: Orden en que Previred exige las líneas de un mismo trabajador: la principal
#: primero y las anexas después, contiguas.
LINE_TYPE_ORDER = {
    LINE_PRINCIPAL: 0,
    LINE_ADDITIONAL: 1,
    LINE_SECOND_CONTRACT: 2,
    LINE_VOLUNTARY: 3,
}

#: Campo 13 «Días Trabajados». La fuente oficial es la línea de asistencia de
#: la liquidación. `WORK100` es el código técnico estable del tipo de entrada
#: de trabajo «Asistencia» de Odoo (xmlid `hr_work_entry.work_entry_type_attendance`)
#: y es lo que usa la base SimpleDigital de Demo-SyS. Se prefiere el código; el
#: respaldo por rótulo (ver `is_attendance_label`) sólo aplica en instalaciones
#: sin un código estable. **Nunca** se suman genéricamente las demás líneas:
#: «Fuera de contrato», licencias, permisos, ausencias y vacaciones quedan
#: excluidos siempre.
ATTENDANCE_CODES = ("WORK100",)

#: Rótulos que, normalizados, identifican una línea de asistencia cuando no hay
#: código técnico. Se acepta el término en español de la especificación y el
#: nombre en inglés del tipo estándar de Odoo.
ATTENDANCE_LABELS = ("asistencia", "attendance")


def is_attendance_label(*values):
    """`True` si **todos** los textos dados designan «Asistencia».

    Respaldo acotado para instalaciones sin un código técnico estable: la
    especificación pide que Tipo y Descripción sean ambos «Asistencia». Se
    normaliza quitando tildes, colapsando espacios y pasando a minúsculas.
    """
    normalized = [
        re.sub(r"\s+", " ", strip_accents(str(value or "")).strip().lower())
        for value in values
    ]
    return bool(normalized) and all(
        text in ATTENDANCE_LABELS for text in normalized)

def normalize_line_type(value):
    """Normaliza el tipo de línea a los dos dígitos de la tabla N°6.

    La especificación declara el campo 14 como `X(2)` con valores `00`..`03`,
    pero el generador de SimpleDigital emite un solo dígito (`0`, `1`). Se
    comparan siempre normalizados para que un archivo con `0` y otro con `00`
    no se traten como tipos distintos; lo que se escribe en el TXT es el valor
    original del motor, que Previred ya acepta hoy.
    """
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) == 1 and text.isdigit():
        return "0" + text
    return text


def life_expectancy_rate(period):
    """Tasa CEV de respaldo por período; la liquidación tiene precedencia."""
    value = str(period or "").replace("-", "")[:6]
    if value >= "202608":
        return "1.00"
    if value >= "202508":
        return "0.90"
    return "0"


def protected_return_rate(period):
    """Gradualidad legal de la cotización con rentabilidad protegida."""
    value = str(period or "").replace("-", "")[:6]
    if "202608" <= value <= "202707":
        return "0.90"
    if "202708" <= value <= "204508":
        return "1.50"
    if value >= "204509":
        year, month = int(value[:4]), int(value[4:6])
        elapsed = (year - 2045) * 12 + month - 9
        reductions = elapsed // 12 + 1
        return str(max(Decimal("0"), Decimal("1.50")
                       - Decimal("0.15") * reductions))
    return "0"


# --- posiciones de campo relevantes (1-based, como la especificación) -------

F_RUT = 1
F_DV = 2
F_LAST_NAME = 3
F_MOTHER_NAME = 4
F_NAMES = 5
F_SEX = 6
F_NATIONALITY = 7
F_PAYMENT_TYPE = 8
F_PERIOD_FROM = 9
F_PERIOD_TO = 10
F_PENSION_REGIME = 11
F_WORKER_TYPE = 12
F_WORKED_DAYS = 13
F_LINE_TYPE = 14
F_MOVEMENT_CODE = 15
F_MOVEMENT_FROM = 16
F_MOVEMENT_TO = 17
F_FAMILY_BRACKET = 18
F_VOLUNTARY_RUT = 50
F_AFP_CODE = 26
F_AFP_TAXABLE = 27
F_AFP_CONTRIBUTION = 28
F_SIS_CONTRIBUTION = 29
F_HEALTH_CODE = 75
F_CCAF_CODE = 83
F_WORKDAY_TYPE = 93
F_LIFE_EXPECTANCY = 94
F_PROTECTED_RETURN = 95
F_MUTUAL_CODE = 96
F_UNEMPLOYMENT_TAXABLE = 100
F_COST_CENTER = 105

#: Campos obligatorios en TODA línea según la columna «Condición» de la
#: especificación. Se validan siempre; el resto son condicionales y se validan
#: por regla propia.
MANDATORY_FIELDS = (
    F_RUT, F_DV, F_LAST_NAME, F_NAMES, F_SEX, F_NATIONALITY,
    F_PAYMENT_TYPE, F_PERIOD_FROM, F_PENSION_REGIME, F_WORKER_TYPE,
    F_WORKED_DAYS, F_LINE_TYPE, F_MOVEMENT_CODE, F_FAMILY_BRACKET,
    F_WORKDAY_TYPE,
)

#: Campos numéricos: enteros sin decimales, sin signo y sin separador de miles.
NUMERIC_FIELDS = frozenset(
    [F_RUT, F_NATIONALITY, F_PAYMENT_TYPE, F_WORKER_TYPE, F_WORKED_DAYS]
    + list(range(19, 25))
    + [F_AFP_CODE, F_AFP_TAXABLE, F_AFP_CONTRIBUTION, 29, 30, 31, 33, 34]
    + [39, 43, 44, 48, 49, 50, 59, 60, 61, 65, 66, 69, 70, 71, 72, 73, 74]
    + [77, F_CCAF_CODE, 84, 85, 86, 87, 88, 89, 90, 91, 92,
       F_LIFE_EXPECTANCY]
    + [97, 98, 99, F_UNEMPLOYMENT_TAXABLE, 101, 102, 103]
)

#: Movimientos de personal (tabla N°7) que **obligan** a informar fecha desde
#: y fecha hasta, según la columna «Condición» de los campos 16 y 17.
MOVEMENT_CODES_REQUIRING_DATES = ("1", "3", "4", "5", "6", "7", "8", "11",
                                  "01", "03", "04", "05", "06", "07", "08")

#: Código de movimiento que indica «sin movimiento en el mes».
MOVEMENT_NONE = ("0", "00", "")

#: Fecha nula que ambos generadores usan cuando no hay movimiento.
NULL_DATE_TOKENS = ("", "0", "00/00/0000", "00-00-0000")

#: Tabla N°13 — único movimiento admitido en una línea de afiliado voluntario.
VOLUNTARY_MOVEMENT_CODE = "10"

#: Tabla N°1 — Sexo.
SEX_CODES = ("M", "F")
#: Tabla N°6 — Tipo de línea.
LINE_TYPE_CODES = tuple(LINE_TYPE_LABELS)
#: Tabla N°8 — Tramo de asignación familiar.
FAMILY_BRACKET_CODES = ("A", "B", "C", "D")
#: Tabla N°4 — Régimen previsional.
PENSION_REGIME_CODES = ("AFP", "INP", "SIP")

#: Etiqueta de la carpeta/hoja para trabajadores sin departamento. Se comparte
#: con el Libro de Remuneraciones para que ambos informes agrupen igual.
NO_DEPARTMENT_LABEL = "Sin departamento"
NO_DEPARTMENT_CODE = "SIN_DEPTO"

#: Rótulo obligatorio del Excel: es un archivo de control, no de carga.
REVIEW_WARNING = "Archivo de revisión; no cargar en Previred"

#: Nombres de los 105 campos, para la fila técnica del Excel y los mensajes de
#: error. El índice de la tupla es la posición menos uno.
FIELD_NAMES = (
    "RUT Trabajador", "DV Trabajador", "Apellido Paterno", "Apellido Materno",
    "Nombres", "Sexo", "Nacionalidad", "Tipo Pago", "Período Desde",
    "Período Hasta", "Régimen Previsional", "Tipo Trabajador",
    "Días Trabajados", "Tipo de Línea", "Código Movimiento de Personal",
    "Fecha Desde", "Fecha Hasta", "Tramo Asignación Familiar",
    "N° Cargas Simples", "N° Cargas Maternales", "N° Cargas Inválidas",
    "Asignación Familiar", "Asignación Familiar Retroactiva",
    "Reintegro Cargas Familiares", "Solicitud Trabajador Joven",
    "Código de la AFP", "Renta Imponible AFP", "Cotización Obligatoria AFP",
    "Cotización SIS", "Cuenta de Ahorro Voluntario AFP",
    "Renta Imp. Sustitutiva AFP", "Tasa Pactada (Sustitutiva)",
    "Aporte Indemnización (Sustitutiva)", "N° Períodos (Sustitutiva)",
    "Período Desde (Sustitutiva)", "Período Hasta (Sustitutiva)",
    "Puesto de Trabajo Pesado", "% Cotización Trabajo Pesado",
    "Cotización Trabajo Pesado", "Código Institución APVI",
    "Número de Contrato APVI", "Forma de Pago APVI", "Cotización APVI",
    "Cotización Depósitos Convenidos", "Código Institución APVC",
    "Número de Contrato APVC", "Forma de Pago APVC",
    "Cotización Trabajador APVC", "Cotización Empleador APVC",
    "RUT Afiliado Voluntario", "DV Afiliado Voluntario",
    "Apellido Paterno Afiliado Voluntario",
    "Apellido Materno Afiliado Voluntario", "Nombres Afiliado Voluntario",
    "Código Movimiento de Personal (Afiliado Voluntario)",
    "Fecha Desde (Afiliado Voluntario)", "Fecha Hasta (Afiliado Voluntario)",
    "Código de la AFP (Afiliado Voluntario)",
    "Monto Capitalización Voluntaria", "Monto Ahorro Voluntario",
    "Número de Períodos de Cotización", "Código Ex-Caja Régimen",
    "Tasa Cotización Ex-Caja Previsión", "Renta Imponible IPS / ISL / Fonasa",
    "Cotización Obligatoria IPS", "Renta Imponible Desahucio",
    "Código Ex-Caja Régimen Desahucio", "Tasa Cotización Desahucio Ex-Cajas",
    "Cotización Desahucio", "Cotización Fonasa",
    "Cotización Acc. Trabajo (ISL)", "Bonificación Ley 15.386",
    "Descuento por Cargas Familiares IPS", "Bonos Gobierno",
    "Código Institución de Salud", "Número del FUN",
    "Renta Imponible Isapre", "Moneda del Plan Pactado Isapre",
    "Cotización Pactada", "Cotización Obligatoria Isapre",
    "Cotización Adicional Isapre", "Monto Garantía Explícita de Salud (GES)",
    "Código CCAF", "Renta Imponible CCAF", "Créditos Personales CCAF",
    "Descuento Dental CCAF", "Descuentos por Leasing",
    "Descuentos por Seguro de Vida", "Otros Descuentos CCAF",
    "Cotización a CCAF de no afiliados a Isapres",
    "Descuento Cargas Familiares CCAF",
    "Renta Imponible Mes Anterior a la Licencia (RIMA)", "Tipo de Jornada",
    "Cotización Expectativa de Vida", "Cotización Rentabilidad Protegida",
    "Código Mutualidad", "Renta Imponible Mutual",
    "Cotización Accidente del Trabajo (Mutual)", "Sucursal para pago Mutual",
    "Renta Imponible Seguro Cesantía", "Aporte Trabajador Seguro Cesantía",
    "Aporte Empleador Seguro Cesantía", "RUT Pagadora Subsidio",
    "DV Pagadora Subsidio", "Centro de Costos, Sucursal, Agencia",
)

assert len(FIELD_NAMES) == FIELD_COUNT, "La tabla de nombres debe tener 105 campos"


def field_label(position):
    """Etiqueta oficial del campo en posición `position` (1-based)."""
    if 1 <= position <= FIELD_COUNT:
        return "%d %s" % (position, FIELD_NAMES[position - 1])
    return str(position)


# --- utilidades de normalización -------------------------------------------

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def strip_accents(text):
    """Translitera a ASCII sin acentos, conservando el resto tal cual.

    Previred es un archivo de texto plano para sistemas previsionales antiguos:
    los dos generadores vigentes ya envían los nombres sin tildes y no se
    cambia ese comportamiento.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def rut_key(value):
    """Clave de comparación y orden de un RUT. **Sólo para ordenar y cruzar.**

    Nunca se escribe en el archivo: el TXT conserva el RUT tal como lo emitió
    el motor de nómina.
    """
    digits = _NON_ALNUM.sub("", str(value or "")).upper()
    if not digits:
        return (1, "", "")
    body, dv = digits[:-1], digits[-1]
    if not body.isdigit():
        return (1, digits, "")
    # Se ordena por el número, no por el texto: «9.999.999-K» va antes que
    # «10.000.000-1».
    return (0, body.zfill(12), dv)


def slugify_code(text, fallback=NO_DEPARTMENT_CODE, max_length=40):
    """Código seguro y determinístico para nombres de archivo.

    No se usan nombres libres: se translitera, se pasa a mayúsculas y se deja
    sólo `A-Z0-9_`, para que el nombre no pueda salirse del directorio ni
    arrastrar datos personales.
    """
    ascii_text = strip_accents(text or "").upper()
    cleaned = re.sub(r"[^A-Z0-9]+", "_", ascii_text).strip("_")
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    return (cleaned[:max_length] or fallback)


def vat_code(value, fallback="EMPRESA", max_length=20):
    """RUT de empresa como componente de nombre de archivo.

    A diferencia de `slugify_code`, los separadores del RUT (`.` y `-`) se
    **eliminan** en vez de convertirse en `_`: «76.123.456-7» debe quedar como
    «761234567» y no como «76_123_456_7».
    """
    ascii_text = strip_accents(value or "").upper()
    return (_NON_ALNUM.sub("", ascii_text)[:max_length] or fallback)


def sha256_hex(data):
    """SHA-256 en hexadecimal de `bytes` o `str`."""
    if isinstance(data, str):
        data = data.encode(ENCODING)
    return hashlib.sha256(data).hexdigest()


# --- hallazgos --------------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    """Un hallazgo de validación.

    `code` es un identificador estable y **sin datos personales**: es lo único
    que se guarda en la auditoría. `message` puede nombrar a un trabajador y
    sólo se muestra a quien tiene permiso para verlo.
    """

    severity: str
    code: str
    message: str
    #: Departamento al que pertenece el hallazgo, si aplica.
    department: str = ""

    @property
    def is_error(self):
        return self.severity == SEVERITY_ERROR


# --- registros --------------------------------------------------------------

@dataclass
class PreviredRecord:
    """Un trabajador dentro del lote: su línea principal y sus anexas.

    La unidad de agrupación **no** es la línea sino el trabajador: es lo que
    garantiza que una línea anexa nunca quede separada de su principal al
    partir el archivo por departamento.
    """

    rut: str
    dv: str
    #: Línea principal (tipo 00) como lista de 105 campos ya formateados.
    principal: List[str]
    #: Líneas anexas, en el orden en que las emitió el motor.
    annexes: List[List[str]] = field(default_factory=list)
    department: str = ""
    department_id: Optional[int] = None
    department_code: str = ""
    employee_id: Optional[int] = None
    payslip_id: Optional[int] = None
    company_id: Optional[int] = None
    #: Identidad técnica del contrato al que pertenece esta línea principal.
    #: **No se exporta**: no ocupa ninguna de las 105 posiciones del TXT. Sólo
    #: sirve para que la unicidad distinga dos contratos elegibles del mismo
    #: trabajador en la misma compañía y período (ver `validate_dataset`).
    contract_id: Optional[int] = None

    @property
    def rows(self):
        """Todas las filas del trabajador, principal primero."""
        return [self.principal] + list(self.annexes)

    @property
    def department_label(self):
        return self.department or NO_DEPARTMENT_LABEL

    @property
    def sort_key(self):
        return rut_key("%s%s" % (self.rut, self.dv))


@dataclass
class Dataset:
    """El dataset canónico del lote. **Se construye una sola vez.**

    El TXT consolidado, cada TXT por departamento y todos los Excel se derivan
    de este mismo objeto por partición; ninguna salida recalcula un importe.
    """

    records: List[PreviredRecord] = field(default_factory=list)
    issues: List[Issue] = field(default_factory=list)
    company_name: str = ""
    company_vat: str = ""
    period: str = ""
    profile_name: str = ""
    spec_version: str = SPEC_VERSION
    spec_url: str = SPEC_URL
    spec_effective_from: str = SPEC_EFFECTIVE_FROM
    engine: str = ""
    #: Estados de liquidación que el motor considera validados.
    eligible_states: Tuple[str, ...] = ()
    #: Liquidaciones elegibles encontradas por el core.
    eligible_payslip_count: int = 0
    #: Trabajadores que el motor entregó y el core descartó por no elegibles.
    dropped_count: int = 0

    # -- conteos ------------------------------------------------------------

    @property
    def errors(self):
        return [issue for issue in self.issues if issue.is_error]

    @property
    def warnings(self):
        return [issue for issue in self.issues if not issue.is_error]

    @property
    def row_count(self):
        return sum(len(record.rows) for record in self.records)

    @property
    def annex_count(self):
        return sum(len(record.annexes) for record in self.records)

    @property
    def without_department(self):
        return [record for record in self.records if not record.department]

    def departments(self):
        """Departamentos presentes, en orden estable.

        Se ordena por etiqueta transliterada para que el orden no dependa de
        la configuración regional de la base.
        """
        seen = {}
        for record in self.records:
            key = record.department_id or 0
            seen.setdefault(key, (record.department_label,
                                  record.department_code))
        return sorted(
            ((key, label, code) for key, (label, code) in seen.items()),
            key=lambda item: (strip_accents(item[1]).upper(), item[0]))

    def by_department(self):
        """`{etiqueta: [registros]}` con los registros ya ordenados."""
        grouped: Dict[int, List[PreviredRecord]] = {}
        for record in self.records:
            grouped.setdefault(record.department_id or 0, []).append(record)
        for records in grouped.values():
            records.sort(key=lambda record: record.sort_key)
        return grouped

    def sorted_records(self):
        """Orden determinístico global: departamento y luego RUT.

        El consolidado usa este mismo orden, de modo que la unión de los
        archivos por departamento es una permutación exacta de sus filas.
        """
        return sorted(
            self.records,
            key=lambda record: (
                strip_accents(record.department_label).upper(),
                record.sort_key,
            ),
        )

    @property
    def counters(self):
        return {
            "workers": len(self.records),
            "rows": self.row_count,
            "principal": len(self.records),
            "annexes": self.annex_count,
            "departments": len(self.departments()),
            "without_department": len(self.without_department),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
        }


# --- validación -------------------------------------------------------------

def validate_row(row, position_label=""):
    """Valida una fila de 105 campos contra las reglas del formato.

    Devuelve una lista de `Issue`. La validación es **campo por campo** y se
    ejecuta antes de permitir cualquier descarga.
    """
    issues = []
    prefix = ("%s: " % position_label) if position_label else ""

    if len(row) != FIELD_COUNT:
        issues.append(Issue(
            SEVERITY_ERROR, "field_count",
            "%sEl registro tiene %d campos y la especificación exige %d. "
            "Previred rechaza el archivo completo si falta alguno."
            % (prefix, len(row), FIELD_COUNT),
        ))
        return issues

    for position in MANDATORY_FIELDS:
        value = (row[position - 1] or "").strip()
        if not value:
            issues.append(Issue(
                SEVERITY_ERROR, "missing_mandatory",
                "%sFalta el campo obligatorio «%s»."
                % (prefix, field_label(position)),
            ))

    for position in NUMERIC_FIELDS:
        value = (row[position - 1] or "").strip()
        if value and not re.fullmatch(r"\d+", value):
            issues.append(Issue(
                SEVERITY_ERROR, "not_numeric",
                "%sEl campo «%s» debe ser un entero sin decimales ni signos "
                "y contiene «%s»." % (prefix, field_label(position), value),
            ))

    if SEPARATOR in "".join(str(cell or "") for cell in row):
        issues.append(Issue(
            SEVERITY_ERROR, "separator_in_value",
            "%sUn valor contiene el separador «%s», lo que desplazaría todos "
            "los campos siguientes." % (prefix, SEPARATOR),
        ))

    # Se compara normalizado: SimpleDigital emite «0» donde la tabla N°6 dice
    # «00», y ambos designan la misma línea principal.
    line_type = normalize_line_type(row[F_LINE_TYPE - 1])
    if line_type and line_type not in LINE_TYPE_CODES:
        issues.append(Issue(
            SEVERITY_ERROR, "bad_line_type",
            "%sTipo de línea «%s» no está en la tabla N°6 de la "
            "especificación." % (prefix, line_type),
        ))

    workday_type = (row[F_WORKDAY_TYPE - 1] or "").strip()
    if workday_type and workday_type not in ("1", "2"):
        issues.append(Issue(
            SEVERITY_ERROR, "bad_workday_type",
            "%sTipo de jornada «%s» no está en la tabla N°22 (1 completa, "
            "2 parcial)." % (prefix, workday_type),
        ))

    protected = (row[F_PROTECTED_RETURN - 1] or "").strip()
    if protected and not re.fullmatch(r"\d+", protected):
        issues.append(Issue(
            SEVERITY_ERROR, "bad_protected_return",
            "%sEl campo «%s» debe contener un monto entero y contiene «%s»."
            % (prefix, field_label(F_PROTECTED_RETURN), protected),
        ))

    sex = (row[F_SEX - 1] or "").strip()
    if sex and sex not in SEX_CODES:
        issues.append(Issue(
            SEVERITY_ERROR, "bad_sex",
            "%sSexo «%s» no está en la tabla N°1 (M o F)." % (prefix, sex),
        ))

    bracket = (row[F_FAMILY_BRACKET - 1] or "").strip()
    if bracket and bracket not in FAMILY_BRACKET_CODES:
        issues.append(Issue(
            SEVERITY_ERROR, "bad_family_bracket",
            "%sTramo de asignación familiar «%s» no está en la tabla N°8."
            % (prefix, bracket),
        ))

    regime = (row[F_PENSION_REGIME - 1] or "").strip().upper()
    if regime and regime not in PENSION_REGIME_CODES:
        issues.append(Issue(
            SEVERITY_ERROR, "bad_pension_regime",
            "%sRégimen previsional «%s» no está en la tabla N°4."
            % (prefix, regime),
        ))

    days = (row[F_WORKED_DAYS - 1] or "").strip()
    if days.isdigit() and int(days) > 30:
        issues.append(Issue(
            SEVERITY_ERROR, "worked_days_range",
            "%sDías trabajados = %s; la especificación exige 0 =< días =< 30."
            % (prefix, days),
        ))

    period = (row[F_PERIOD_FROM - 1] or "").strip()
    if period and not re.fullmatch(r"(0[1-9]|1[0-2])\d{4}", period):
        issues.append(Issue(
            SEVERITY_ERROR, "bad_period",
            "%sEl período «%s» no tiene el formato mmaaaa." % (prefix, period),
        ))

    cost_center = row[F_COST_CENTER - 1] or ""
    if len(cost_center) > 20:
        issues.append(Issue(
            SEVERITY_ERROR, "cost_center_length",
            "%sEl campo «%s» admite 20 caracteres y tiene %d."
            % (prefix, field_label(F_COST_CENTER), len(cost_center)),
        ))

    return issues


def validate_record(record, spec_version=SPEC_VERSION):
    """Valida un trabajador completo: sus filas y el orden de sus líneas."""
    issues = []
    label = "RUT %s-%s" % (record.rut, record.dv)

    principal_type = normalize_line_type(record.principal[F_LINE_TYPE - 1]) \
        if len(record.principal) == FIELD_COUNT else ""
    if principal_type != LINE_PRINCIPAL:
        issues.append(Issue(
            SEVERITY_ERROR, "principal_line_type",
            "%s: la primera línea del trabajador debe ser de tipo «%s» y es "
            "«%s»." % (label, LINE_PRINCIPAL, principal_type or "-"),
            record.department_label,
        ))

    for index, row in enumerate(record.rows):
        for issue in validate_row(row, label):
            issues.append(Issue(
                issue.severity, issue.code, issue.message,
                record.department_label,
            ))
        if index == 0 or len(row) != FIELD_COUNT:
            continue
        annex_type = normalize_line_type(row[F_LINE_TYPE - 1])
        if annex_type == LINE_PRINCIPAL:
            issues.append(Issue(
                SEVERITY_ERROR, "annex_line_type",
                "%s: una línea anexa no puede declararse de tipo «%s»."
                % (label, LINE_PRINCIPAL), record.department_label,
            ))
        issues.extend(
            validate_annex_conditions(row, label, record.department_label))

    if len(record.principal) == FIELD_COUNT:
        principal_workday_type = (
            record.principal[F_WORKDAY_TYPE - 1] or "").strip()
        for row in record.annexes:
            if (len(row) == FIELD_COUNT
                    and (row[F_WORKDAY_TYPE - 1] or "").strip()
                    != principal_workday_type):
                issues.append(Issue(
                    SEVERITY_ERROR, "annex_workday_type_mismatch",
                    "%s: el Tipo de Jornada de cada línea anexa debe ser "
                    "igual al de la línea 00 (%s)." % (
                        label, principal_workday_type or "-"),
                    record.department_label,
                ))

    # En v98 los campos 94 y 95 son obligatorios para una línea principal de
    # una persona afiliada a AFP. El enriquecimiento del core los calcula a
    # partir de la renta imponible y la vigencia legal; cero sigue siendo un
    # valor explícito válido cuando no corresponde AFP.
    if spec_version == "98" and len(record.principal) == FIELD_COUNT:
        afp_code = (record.principal[F_AFP_CODE - 1] or "").strip()
        regime = (record.principal[F_PENSION_REGIME - 1] or "").strip().upper()
        worker_type = (record.principal[F_WORKER_TYPE - 1] or "").strip()
        if (regime == "AFP" and worker_type == "0" and afp_code
                and afp_code not in ("0", "00")):
            for position in (F_LIFE_EXPECTANCY, F_PROTECTED_RETURN):
                if not (record.principal[position - 1] or "").strip():
                    issues.append(Issue(
                        SEVERITY_ERROR, "missing_reform_contribution",
                        "%s: falta el campo obligatorio «%s» para afiliado "
                        "AFP." % (label, field_label(position)),
                        record.department_label,
                    ))
        if worker_type == "3":
            for position in (
                    F_SIS_CONTRIBUTION,
                    F_LIFE_EXPECTANCY,
                    F_PROTECTED_RETURN):
                value = (record.principal[position - 1] or "").strip()
                if value and value != "0":
                    issues.append(Issue(
                        SEVERITY_ERROR,
                        "active_over_65_employer_contribution",
                        "%s: el tipo de trabajador 3 debe informar cero en "
                        "«%s»; se recibió %s." % (
                            label, field_label(position), value
                        ),
                        record.department_label,
                    ))
    return issues


def validate_annex_conditions(row, label="", department=""):
    """Condicionales que la especificación exige en una línea anexa.

    Una anexa mal formada no invalida el archivo completo, pero Previred **no
    la contabiliza** al generar planillas: el trabajador queda declarado de
    menos sin que nadie lo note. Por eso se trata como error y no como aviso.
    """
    issues = []
    prefix = ("%s: " % label) if label else ""
    line_type = normalize_line_type(row[F_LINE_TYPE - 1])
    movement = (row[F_MOVEMENT_CODE - 1] or "").strip()
    date_from = (row[F_MOVEMENT_FROM - 1] or "").strip()
    date_to = (row[F_MOVEMENT_TO - 1] or "").strip()

    if line_type == LINE_VOLUNTARY:
        # Tabla N°13: en la línea 03 sólo cabe el cese de cotizaciones del
        # afiliado voluntario, y sus datos identificatorios son obligatorios.
        if movement and movement.lstrip("0") not in ("10", ""):
            issues.append(Issue(
                SEVERITY_ERROR, "voluntary_movement_code",
                "%sUna línea de tipo 03 sólo admite el movimiento %s de la "
                "tabla N°13 y declara «%s»."
                % (prefix, VOLUNTARY_MOVEMENT_CODE, movement), department))
        if not (row[F_VOLUNTARY_RUT - 1] or "").strip().strip("0"):
            issues.append(Issue(
                SEVERITY_ERROR, "voluntary_rut_missing",
                "%sUna línea de tipo 03 debe informar el RUT del afiliado "
                "voluntario." % prefix, department))
        return issues

    if line_type == LINE_ADDITIONAL and movement in MOVEMENT_NONE:
        issues.append(Issue(
            SEVERITY_ERROR, "annex_without_movement",
            "%sUna línea de tipo 01 existe para informar un movimiento de "
            "personal y no declara ninguno." % prefix, department))

    if movement and movement not in MOVEMENT_NONE \
            and movement.lstrip("0") in MOVEMENT_CODES_REQUIRING_DATES:
        if date_from in NULL_DATE_TOKENS:
            issues.append(Issue(
                SEVERITY_ERROR, "movement_date_from_required",
                "%sEl movimiento de personal %s exige «%s»."
                % (prefix, movement, field_label(F_MOVEMENT_FROM)),
                department))
        if date_to in NULL_DATE_TOKENS:
            issues.append(Issue(
                SEVERITY_ERROR, "movement_date_to_required",
                "%sEl movimiento de personal %s exige «%s»."
                % (prefix, movement, field_label(F_MOVEMENT_TO)),
                department))
    return issues


def validate_dataset(dataset):
    """Valida todo el lote y devuelve los hallazgos nuevos.

    Unicidad **consciente del contrato**: un trabajador puede tener tantas
    líneas principales (código `00`) como contratos elegibles tenga en la
    misma compañía y período. Sigue siendo error repetir la línea principal
    de un mismo contrato. Cuando el motor no entrega la identidad del
    contrato (`contract_id is None`), se conserva el criterio anterior
    —compañía + período + RUT— para no relajar la validación.
    """
    issues = []
    seen = {}
    for record in dataset.records:
        issues.extend(validate_record(record, dataset.spec_version))
        rk = rut_key("%s%s" % (record.rut, record.dv))
        key = (record.company_id, rk, record.contract_id)
        if key in seen:
            if record.contract_id is not None:
                message = (
                    "RUT %s-%s tiene más de una línea principal para el mismo "
                    "contrato en la misma compañía y período."
                    % (record.rut, record.dv))
            else:
                message = (
                    "RUT %s-%s aparece más de una vez con línea principal en "
                    "la misma compañía y período." % (record.rut, record.dv))
            issues.append(Issue(
                SEVERITY_ERROR, "duplicate_worker", message,
                record.department_label,
            ))
        seen[key] = record
    return issues


# --- render TXT -------------------------------------------------------------

def render_rows(rows):
    """Serializa filas al texto oficial.

    Cada fila se une con «;» y las líneas con CRLF. **No** se añade separador
    final ni línea en blanco al final: son caracteres que Previred cuenta.
    """
    normalized = []
    for source in rows:
        row = list(source)
        if len(row) == FIELD_COUNT:
            row[F_LINE_TYPE - 1] = normalize_line_type(
                row[F_LINE_TYPE - 1])
        normalized.append(row)
    return LINE_ENDING.join(SEPARATOR.join(str(cell or "") for cell in row)
                            for row in normalized)


def render_records(records):
    """Serializa trabajadores conservando principal + anexas contiguas."""
    rows = []
    for record in records:
        rows.extend(record.rows)
    return render_rows(rows)


def txt_bytes(text):
    """Codifica el TXT listo para escribir en disco o enviar al navegador."""
    return text.encode(ENCODING)


# --- nombres de archivo -----------------------------------------------------

def txt_filename(company_vat, period, department_code=None):
    """`PREVIRED_<RUT_EMPRESA>_<AAAAMM>[_<CODIGO_DEPTO>].txt`.

    Todos los componentes pasan por `slugify_code`, así que el nombre no puede
    contener separadores de ruta, espacios ni datos personales.
    """
    parts = ["PREVIRED", vat_code(company_vat),
             slugify_code(period, "PERIODO")]
    if department_code:
        parts.append(slugify_code(department_code))
    return "%s.txt" % "_".join(parts)


def xlsx_filename(company_vat, period, department_code=None):
    parts = ["PREVIRED_REVISION", vat_code(company_vat),
             slugify_code(period, "PERIODO")]
    if department_code:
        parts.append(slugify_code(department_code))
    return "%s.xlsx" % "_".join(parts)


def zip_filename(company_vat, period):
    return "PREVIRED_%s_%s.zip" % (
        vat_code(company_vat), slugify_code(period, "PERIODO"))


# --- manifiesto del ZIP -----------------------------------------------------

MANIFEST_NAME = "MANIFIESTO.csv"

MANIFEST_HEADER = (
    "archivo", "departamento", "trabajadores", "lineas", "sha256",
)


def build_manifest(entries, dataset):
    """Manifiesto de control del ZIP.

    Lleva conteos y hashes por archivo y **no** lleva nombres ni RUT: sirve
    para verificar que se cargó lo que se generó, no para revisar personas.
    """
    lines = [
        "# Previred - manifiesto de control",
        "# Empresa: %s" % dataset.company_name,
        "# Periodo: %s" % dataset.period,
        "# Formato: %s, version %s (%s)"
        % (SPEC_NAME, dataset.spec_version, dataset.spec_effective_from),
        "# Fuente: %s" % dataset.spec_url,
        "# Solo los archivos .txt son cargables en Previred.",
        SEPARATOR.join(MANIFEST_HEADER),
    ]
    for entry in entries:
        lines.append(SEPARATOR.join([
            entry["filename"],
            strip_accents(entry["department"]),
            str(entry["workers"]),
            str(entry["rows"]),
            entry["sha256"],
        ]))
    return LINE_ENDING.join(lines)
