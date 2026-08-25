"""Núcleo del libro consolidado de remuneraciones (Python puro).

Este módulo no importa Odoo a propósito: define las columnas por código DT, el
dataset tipado que consumen Excel, PDF y previsualización, y las conciliaciones.
Así la lógica de negocio se puede probar sin base de datos y sin `request`.
"""

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Códigos DT
# --------------------------------------------------------------------------

#: Extrae el código DT de un encabezado del proveedor, p. ej. "Sueldo(2101)".
#: Se busca el ÚLTIMO paréntesis con dígitos para tolerar textos como
#: "Cotización obligatoria previsional (AFP o IPS)(3141)".
DT_CODE_RE = re.compile(r"\((\d{3,4})\)")

CODE_RUT = "1101"
CODE_DAYS = "1115"
CODE_WAGE = "2101"
CODE_GRATIFICATION = "2106"
CODE_BONUS = "2113"
CODE_MEAL = "2301"
CODE_TRANSPORT = "2302"
CODE_FAMILY = "2311"
CODE_PENSION = "3141"
CODE_HEALTH = "3143"
CODE_HEALTH_EXTRA = "3144"
CODE_UNEMPLOYMENT = "3151"
CODE_APVI = "3155"
CODE_INCOME_TAX = "3161"
CODE_CCAF = "3110"
CODE_OTHER_DEDUCTIONS = "3183"
CODE_ADVANCES = "3188"
CODE_TOTAL_INCOME = "5201"
CODE_TOTAL_TAXABLE = "5210"
CODE_TOTAL_DEDUCTIONS = "5301"
CODE_NET = "5501"

#: Totales que SIEMPRE se toman del valor oficial de la fuente. Nunca se
#: reemplazan por la suma de las columnas visibles del libro abreviado.
OFFICIAL_TOTAL_CODES = (
    CODE_TOTAL_TAXABLE,
    CODE_TOTAL_INCOME,
    CODE_TOTAL_DEDUCTIONS,
    CODE_NET,
)


def extract_dt_code(header):
    """Devuelve el código DT contenido en un encabezado, o ``None``.

    Se mapea por código y no por posición ni por texto completo, de modo que el
    proveedor pueda cambiar la descripción sin romper el informe.
    """
    if not header:
        return None
    found = DT_CODE_RE.findall(header)
    return found[-1] if found else None


# --------------------------------------------------------------------------
# Definición de las 24 columnas del libro consolidado
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSpec:
    order: int
    key: str
    label: str
    dt_code: str = None
    kind: str = "money"  # group | text | rut | count | days | money
    width: float = 12.0

    @property
    def header(self):
        """Etiqueta con código DT, como en el libro de referencia."""
        if self.dt_code:
            return "%s (%s)" % (self.label, self.dt_code)
        return self.label

    @property
    def is_numeric(self):
        return self.kind in ("count", "days", "money")


BOOK_COLUMNS = (
    ColumnSpec(1, "department", "Departamento", None, "group", 22.0),
    ColumnSpec(2, "rut", "Rut trabajador", CODE_RUT, "rut", 13.0),
    ColumnSpec(3, "employee", "Nombre Trabajador", None, "text", 30.0),
    ColumnSpec(4, "quantity", "Cantidad", None, "count", 8.0),
    ColumnSpec(5, "days", "Días", CODE_DAYS, "days", 7.0),
    ColumnSpec(6, "wage", "Sueldo", CODE_WAGE, "money", 12.0),
    ColumnSpec(7, "bonus", "Bonos", CODE_BONUS, "money", 12.0),
    ColumnSpec(8, "gratification", "Gratificación", CODE_GRATIFICATION, "money", 12.0),
    ColumnSpec(9, "total_taxable", "Total haberes imponibles", CODE_TOTAL_TAXABLE, "money", 14.0),
    ColumnSpec(10, "transport", "Movilización", CODE_TRANSPORT, "money", 12.0),
    ColumnSpec(11, "meal", "Colación", CODE_MEAL, "money", 12.0),
    ColumnSpec(12, "family", "Asignación familiar", CODE_FAMILY, "money", 12.0),
    ColumnSpec(13, "total_income", "Total haberes", CODE_TOTAL_INCOME, "money", 14.0),
    ColumnSpec(14, "pension", "Cotización AFP o IPS", CODE_PENSION, "money", 13.0),
    ColumnSpec(15, "health", "Cotización salud 7 %", CODE_HEALTH, "money", 13.0),
    ColumnSpec(16, "health_extra", "Cotización voluntaria salud", CODE_HEALTH_EXTRA, "money", 13.0),
    ColumnSpec(17, "unemployment", "Cotización AFC trabajador", CODE_UNEMPLOYMENT, "money", 13.0),
    ColumnSpec(18, "income_tax", "Impuesto remuneraciones", CODE_INCOME_TAX, "money", 13.0),
    ColumnSpec(19, "ccaf", "Crédito social CCAF", CODE_CCAF, "money", 13.0),
    ColumnSpec(20, "advances", "Anticipos", CODE_ADVANCES, "money", 12.0),
    ColumnSpec(21, "other_deductions", "Otros descuentos", CODE_OTHER_DEDUCTIONS, "money", 13.0),
    ColumnSpec(22, "apvi", "Cotización APVi ahorro", CODE_APVI, "money", 13.0),
    ColumnSpec(23, "total_deductions", "Total descuentos", CODE_TOTAL_DEDUCTIONS, "money", 14.0),
    ColumnSpec(24, "net", "Total líquido", CODE_NET, "money", 14.0),
)

#: Columnas que llevan importe o cantidad y por tanto se suman en subtotales.
NUMERIC_COLUMNS = tuple(column for column in BOOK_COLUMNS if column.is_numeric)

#: Códigos DT que el extractor debe poder resolver para armar el libro.
REQUIRED_DT_CODES = tuple(
    column.dt_code for column in BOOK_COLUMNS if column.dt_code
)

# Conciliaciones informativas: (total oficial, componentes visibles)
VISIBLE_TAXABLE_COMPONENTS = (CODE_WAGE, CODE_BONUS, CODE_GRATIFICATION)
VISIBLE_INCOME_COMPONENTS = (
    CODE_TOTAL_TAXABLE,
    CODE_TRANSPORT,
    CODE_MEAL,
    CODE_FAMILY,
)
VISIBLE_DEDUCTION_COMPONENTS = (
    CODE_PENSION,
    CODE_HEALTH,
    CODE_HEALTH_EXTRA,
    CODE_UNEMPLOYMENT,
    CODE_INCOME_TAX,
    CODE_CCAF,
    CODE_ADVANCES,
    CODE_OTHER_DEDUCTIONS,
    CODE_APVI,
)

NO_DEPARTMENT_LABEL = "Sin departamento"

#: Alcance del informe. Determina si la salida puede considerarse el libro
#: corporativo o sólo un extracto del universo visible para el usuario.
SCOPE_FULL = "full"
SCOPE_PARTIAL = "partial"
SCOPE_LABELS = {
    SCOPE_FULL: "Alcance: empresa completa",
    SCOPE_PARTIAL: "Alcance parcial",
}

#: Origen de la resolución del perfil, mostrado en la síntesis.
PROFILE_ORIGIN_LABELS = {
    "assigned": "Asignado",
    "detected": "Detectado",
    "unconfirmed": "Sin confirmar",
}

#: Tolerancia inicial sugerida para la conciliación, en pesos. Es un valor de
#: revisión operativa, no una regla legal.
DEFAULT_TOLERANCE = 1


# --------------------------------------------------------------------------
# RUT
# --------------------------------------------------------------------------


def rut_key(value):
    """Clave CANÓNICA de comparación. No sirve para mostrar.

    Quita puntos, guiones y espacios, pasa la K a mayúscula y elimina ceros a
    la izquierda para que `0012345678-5` y `12345678-5` sean el mismo
    trabajador. Devuelve cadena vacía si no hay nada utilizable.

    Política de RUT del módulo (documentada en `docs/ENTREGA_...`):

    * `rut_key`      -> comparar/agrupar (sin ceros iniciales).
    * `is_valid_rut` -> validar el dígito verificador (módulo 11).
    * `rut_display`  -> mostrar en Excel/PDF (conserva los ceros iniciales).
    * el CSV oficial DT NO pasa por ninguna de estas funciones: se entrega tal
      cual lo genera la fuente oficial.
    """
    cleaned = re.sub(r"[^0-9kK]", "", value or "").upper()
    return cleaned.lstrip("0")


def rut_digits(value):
    """Identificador limpio SIN alterarlo: sólo se quitan separadores.

    Conserva los ceros iniciales porque forman parte del identificador tal
    como está registrado en la ficha del trabajador.
    """
    return re.sub(r"[^0-9kK]", "", value or "").upper()


def rut_display(value):
    """RUT chileno para lectura humana: `12.345.678-5`.

    Se devuelve SIEMPRE como texto y nunca como número, para que Excel no lo
    convierta a notación científica ni pierda ceros iniciales o la K. Si el
    valor no tiene cuerpo y dígito verificador se devuelve tal cual quedó tras
    limpiar separadores, sin inventar formato.
    """
    cleaned = rut_digits(value)
    if not cleaned:
        return ""
    if len(cleaned) < 2:
        return cleaned
    body, verifier = cleaned[:-1], cleaned[-1]
    if not body.isdigit():
        return cleaned
    groups = []
    while len(body) > 3:
        groups.insert(0, body[-3:])
        body = body[:-3]
    groups.insert(0, body)
    return "%s-%s" % (".".join(groups), verifier)


def is_valid_rut(value):
    """Validación módulo 11 del RUT chileno sobre la clave canónica."""
    cleaned = rut_key(value)
    if len(cleaned) < 2:
        return False
    body, verifier = cleaned[:-1], cleaned[-1]
    if not body.isdigit():
        return False
    total = 0
    factor = 2
    for digit in reversed(body):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    remainder = 11 - (total % 11)
    expected = {11: "0", 10: "K"}.get(remainder, str(remainder))
    return expected == verifier


# --------------------------------------------------------------------------
# Estructuras del dataset
# --------------------------------------------------------------------------


@dataclass
class Issue:
    """Hallazgo de validación. Nunca transporta montos ni nombres."""

    level: str  # 'error' | 'warning' | 'info'
    code: str
    message: str

    @property
    def is_blocking(self):
        return self.level == "error"


@dataclass
class BookLine:
    """Una línea de detalle del libro: exactamente una liquidación."""

    payslip_id: int
    employee_id: int = 0
    employee_name: str = ""
    rut: str = ""
    department: str = ""
    values: dict = field(default_factory=dict)  # código DT -> int
    issues: list = field(default_factory=list)

    @property
    def department_label(self):
        return self.department or NO_DEPARTMENT_LABEL

    def value(self, dt_code):
        return int(self.values.get(dt_code) or 0)

    def cell(self, column):
        """Valor de una columna del libro para esta línea de detalle."""
        if column.kind == "group":
            return self.department_label
        if column.kind == "text":
            return self.employee_name
        if column.kind == "rut":
            return rut_display(self.rut)
        if column.kind == "count":
            # La muestra deja Cantidad vacía en el detalle: sólo se usa en los
            # subtotales y en el total general.
            return None
        return self.value(column.dt_code)


@dataclass
class BookGroup:
    """Departamento con sus líneas y su subtotal."""

    name: str
    lines: list = field(default_factory=list)
    totals: dict = field(default_factory=dict)

    @property
    def quantity(self):
        return len(self.lines)

    @property
    def label(self):
        return "Total %s" % self.name

    def cell(self, column):
        if column.kind == "group":
            return self.label
        if column.kind in ("text", "rut"):
            return None
        if column.kind == "count":
            return self.quantity
        return int(self.totals.get(column.dt_code) or 0)


@dataclass
class BookDataset:
    """Fuente única de verdad para Excel, PDF consolidado y previsualización."""

    company_name: str = ""
    company_vat: str = ""
    period_label: str = ""
    date_from: object = None
    date_to: object = None
    source: str = ""
    generated_at: str = ""
    #: `full` = todas las liquidaciones de la compañía; `partial` = sólo las que
    #: las reglas de registro dejan ver al usuario. El alcance parcial nunca es
    #: un libro oficial.
    scope: str = SCOPE_FULL
    #: `assigned` | `detected` | `unconfirmed`
    profile_origin: str = "unconfirmed"
    tolerance: int = DEFAULT_TOLERANCE
    groups: list = field(default_factory=list)
    totals: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)

    # -- accesos de conveniencia -------------------------------------------

    @property
    def columns(self):
        return BOOK_COLUMNS

    @property
    def lines(self):
        return [line for group in self.groups for line in group.lines]

    @property
    def quantity(self):
        return len(self.lines)

    @property
    def title(self):
        return "Libro de Remuneraciones - %s" % self.period_label

    @property
    def scope_label(self):
        return SCOPE_LABELS.get(self.scope, SCOPE_LABELS[SCOPE_PARTIAL])

    @property
    def is_full_scope(self):
        return self.scope == SCOPE_FULL

    @property
    def profile_origin_label(self):
        return PROFILE_ORIGIN_LABELS.get(self.profile_origin, "Sin confirmar")

    @property
    def errors(self):
        return [issue for issue in self.issues if issue.level == "error"]

    @property
    def warnings(self):
        return [issue for issue in self.issues if issue.level == "warning"]

    def total_cell(self, column):
        if column.kind == "group":
            return "Total general"
        if column.kind in ("text", "rut"):
            return None
        if column.kind == "count":
            return self.quantity
        return int(self.totals.get(column.dt_code) or 0)


# --------------------------------------------------------------------------
# Construcción y conciliación
# --------------------------------------------------------------------------


def _sum_codes(values, codes):
    return sum(int(values.get(code) or 0) for code in codes)


def reconcile_line(line, tolerance=DEFAULT_TOLERANCE):
    """Compara los totales oficiales con las columnas visibles.

    Devuelve una lista de :class:`Issue`. Nunca modifica los valores oficiales:
    las sumas visibles sirven para alertar, no para sustituir la fuente.
    """
    issues = []
    values = line.values
    checks = (
        ("recon_5210", CODE_TOTAL_TAXABLE, VISIBLE_TAXABLE_COMPONENTS,
         "Total haberes imponibles (5210)"),
        ("recon_5201", CODE_TOTAL_INCOME, VISIBLE_INCOME_COMPONENTS,
         "Total haberes (5201)"),
        ("recon_5301", CODE_TOTAL_DEDUCTIONS, VISIBLE_DEDUCTION_COMPONENTS,
         "Total descuentos (5301)"),
    )
    for code, official_code, components, label in checks:
        official = int(values.get(official_code) or 0)
        visible = _sum_codes(values, components)
        difference = visible - official
        if abs(difference) > tolerance:
            issues.append(Issue(
                "warning", code,
                "Liquidación %s: %s difiere en %s de la suma de las columnas "
                "visibles. Se mantiene el valor oficial." % (
                    line.payslip_id, label, difference),
            ))

    # Identidad legal: 5201 - 5301 = 5501
    expected_net = (int(values.get(CODE_TOTAL_INCOME) or 0)
                    - int(values.get(CODE_TOTAL_DEDUCTIONS) or 0))
    net = int(values.get(CODE_NET) or 0)
    if expected_net != net:
        issues.append(Issue(
            "warning", "recon_5501",
            "Liquidación %s: 5201 - 5301 = %s pero 5501 informa %s." % (
                line.payslip_id, expected_net, net),
        ))
    return issues


def _department_sort_key(name):
    """«Sin departamento» siempre al final; el resto alfabético estable."""
    return (1, "") if name == NO_DEPARTMENT_LABEL else (0, name.casefold())


def build_dataset(lines, tolerance=DEFAULT_TOLERANCE, issues=None, **metadata):
    """Agrupa las líneas por departamento y calcula subtotales y total general.

    ``lines`` son :class:`BookLine` ya resueltas por el extractor. La cantidad
    cuenta LÍNEAS de detalle, igual que el libro de referencia: un trabajador
    con dos liquidaciones en el mes aparece dos veces y cuenta dos.
    """
    dataset = BookDataset(tolerance=tolerance, **metadata)
    dataset.issues = list(issues or [])

    grouped = {}
    for line in lines:
        grouped.setdefault(line.department_label, []).append(line)

    for name in sorted(grouped, key=_department_sort_key):
        group_lines = sorted(
            grouped[name],
            key=lambda line: (
                (line.employee_name or "").casefold(),
                rut_key(line.rut),
                line.payslip_id,
            ),
        )
        group = BookGroup(name=name, lines=group_lines)
        for column in NUMERIC_COLUMNS:
            if not column.dt_code:
                continue
            group.totals[column.dt_code] = sum(
                line.value(column.dt_code) for line in group_lines
            )
        dataset.groups.append(group)

    for column in NUMERIC_COLUMNS:
        if not column.dt_code:
            continue
        dataset.totals[column.dt_code] = sum(
            group.totals.get(column.dt_code, 0) for group in dataset.groups
        )

    for line in dataset.lines:
        dataset.issues.extend(line.issues)
        dataset.issues.extend(reconcile_line(line, tolerance))

    dataset.counters = build_counters(dataset)
    dataset.issues.extend(_structural_issues(dataset))
    # Se recuentan tras las comprobaciones estructurales para que el resumen
    # incluya también las advertencias que éstas generan.
    dataset.counters = build_counters(dataset)
    return dataset


def build_counters(dataset):
    """Síntesis de control que se muestra antes de descargar.

    Los conteos se calculan en una sola pasada O(n): con 5.000 liquidaciones el
    recuento de duplicados con `list.count()` era cuadrático.
    """
    all_lines = dataset.lines
    occurrences = {}
    without_rut = 0
    invalid_rut = 0
    without_department = 0
    payslip_ids = set()
    for line in all_lines:
        key = rut_key(line.rut)
        if not key:
            without_rut += 1
            key = "emp-%s" % line.employee_id
        elif not is_valid_rut(line.rut):
            invalid_rut += 1
        occurrences[key] = occurrences.get(key, 0) + 1
        if line.department_label == NO_DEPARTMENT_LABEL:
            without_department += 1
        payslip_ids.add(line.payslip_id)

    repeated = sum(1 for count in occurrences.values() if count > 1)
    reconciliation_warnings = 0
    for issue in dataset.issues:
        if issue.code.startswith("recon_"):
            reconciliation_warnings += 1
    return {
        "payslips": len(payslip_ids),
        "lines": len(all_lines),
        "unique_employees": len(occurrences),
        "departments": len(dataset.groups),
        "without_department": without_department,
        "without_rut": without_rut,
        "invalid_rut": invalid_rut,
        "multiple_payslips": repeated,
        "reconciliation_warnings": reconciliation_warnings,
        "errors": len(dataset.errors),
        "warnings": len(dataset.warnings),
    }


def _structural_issues(dataset):
    """Comprueba que subtotales y total general cuadren con el detalle."""
    issues = []
    for group in dataset.groups:
        for column in NUMERIC_COLUMNS:
            if not column.dt_code:
                continue
            expected = sum(line.value(column.dt_code) for line in group.lines)
            if expected != group.totals.get(column.dt_code, 0):
                issues.append(Issue(
                    "error", "subtotal_mismatch",
                    "El subtotal de %s no coincide con sus líneas en la columna "
                    "%s." % (group.name, column.header),
                ))
    for column in NUMERIC_COLUMNS:
        if not column.dt_code:
            continue
        expected = sum(group.totals.get(column.dt_code, 0)
                       for group in dataset.groups)
        if expected != dataset.totals.get(column.dt_code, 0):
            issues.append(Issue(
                "error", "total_mismatch",
                "El total general no coincide con la suma de subtotales en la "
                "columna %s." % column.header,
            ))
    counters = dataset.counters
    if counters.get("without_department"):
        issues.append(Issue(
            "warning", "missing_department",
            "%s línea(s) sin departamento quedaron agrupadas en «%s»." % (
                counters["without_department"], NO_DEPARTMENT_LABEL),
        ))
    if counters.get("without_rut"):
        issues.append(Issue(
            "warning", "missing_rut",
            "%s línea(s) sin RUT utilizable." % counters["without_rut"],
        ))
    if counters.get("invalid_rut"):
        issues.append(Issue(
            "warning", "invalid_rut_total",
            "%s línea(s) con RUT de dígito verificador inválido." % (
                counters["invalid_rut"],),
        ))
    if counters.get("multiple_payslips"):
        issues.append(Issue(
            "info", "multiple_payslips",
            "%s trabajador(es) con más de una liquidación en el período: se "
            "muestran en líneas separadas y cuentan por separado." % (
                counters["multiple_payslips"],),
        ))
    return issues
