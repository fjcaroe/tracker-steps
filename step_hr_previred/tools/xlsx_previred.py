"""Excel de revisión del archivo Previred.

El libro refleja **exactamente** el dataset del TXT: cada celda es el valor
que va al archivo oficial, sin recalcular nada y sin fórmulas que puedan
alterarlo. Es un archivo de control para personas y lleva el rótulo
correspondiente en todas las hojas.

Estilo visual alineado con `step_hr_remuneration_book` para que Nómina vea un
solo sistema.
"""

import xlsxwriter

from . import previred

SUMMARY_SHEET = "Resumen"
CONSOLIDATED_SHEET = "Consolidado"

#: Excel no admite nombres de hoja de más de 31 caracteres ni repetidos.
MAX_SHEET_NAME = 31

#: Límite de filas de una hoja de cálculo (1.048.576) menos el encabezado.
MAX_ROWS = 1048576 - 8

GREEN_DARK = "#174A35"
GREEN_MID = "#2E6B4C"
GREEN_SOFT = "#EAF4EE"
GREEN_LINE = "#D4E3DA"
GREY_LINE = "#DCE7E0"
AMBER = "#8A5A00"
AMBER_SOFT = "#FFF4DC"

#: Columnas de contexto que se anteponen a los 105 campos oficiales.
CONTEXT_COLUMNS = ("Departamento", "Tipo de línea")


def _formats(workbook):
    return {
        "title": workbook.add_format({
            "bold": True, "font_size": 16, "font_color": "#FFFFFF",
            "bg_color": GREEN_DARK, "align": "left", "valign": "vcenter",
            "indent": 1,
        }),
        "subtitle": workbook.add_format({
            "font_color": "#365B4A", "bg_color": GREEN_SOFT,
            "valign": "vcenter", "indent": 1,
        }),
        "warning": workbook.add_format({
            "bold": True, "font_color": AMBER, "bg_color": AMBER_SOFT,
            "align": "left", "valign": "vcenter", "indent": 1, "border": 1,
            "border_color": "#E0C68A",
        }),
        "header": workbook.add_format({
            "bold": True, "font_size": 9, "font_color": "#FFFFFF",
            "bg_color": GREEN_MID, "border": 1, "border_color": GREEN_LINE,
            "text_wrap": True, "align": "center", "valign": "vcenter",
        }),
        "header_tech": workbook.add_format({
            "font_size": 8, "font_color": "#F0F6F2", "bg_color": "#3E7C5B",
            "border": 1, "border_color": GREEN_LINE, "text_wrap": True,
            "align": "center", "valign": "vcenter",
        }),
        # Todo el cuerpo se escribe como TEXTO: un RUT, un código de AFP o un
        # período «082026» perderían sus ceros si Excel los tomara por número.
        "cell": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "valign": "vcenter", "num_format": "@",
        }),
        "cell_alt": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "bg_color": "#F5F9F6", "valign": "vcenter", "num_format": "@",
        }),
        "cell_annex": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "bg_color": "#FFFBEF", "valign": "vcenter", "num_format": "@",
            "italic": True,
        }),
        "key": workbook.add_format({"bold": True, "valign": "top"}),
        "value": workbook.add_format({"valign": "top", "num_format": "@"}),
        "value_wrap": workbook.add_format({"text_wrap": True, "valign": "top"}),
        "issue_error": workbook.add_format({
            "font_size": 9, "font_color": "#8C1D18", "text_wrap": True,
            "valign": "top",
        }),
        "issue_warning": workbook.add_format({
            "font_size": 9, "font_color": AMBER, "text_wrap": True,
            "valign": "top",
        }),
    }


class _SheetNamer:
    """Nombres de hoja únicos y de 31 caracteres como máximo.

    Excel rechaza el archivo entero si dos hojas se llaman igual, y los
    departamentos pueden compartir prefijo. Se recorta y se desambigua con un
    sufijo numérico.
    """

    def __init__(self):
        self._used = set()

    def take(self, name):
        base = (name or "-").strip()[:MAX_SHEET_NAME]
        for char in "[]:*?/\\":
            base = base.replace(char, "-")
        base = base or "-"
        candidate = base
        counter = 2
        while candidate.lower() in self._used:
            suffix = " (%d)" % counter
            candidate = base[:MAX_SHEET_NAME - len(suffix)] + suffix
            counter += 1
        self._used.add(candidate.lower())
        return candidate


def _write_masthead(sheet, styles, dataset, last_column, subtitle):
    sheet.merge_range(0, 0, 0, last_column, "Previred — archivo de revisión",
                      styles["title"])
    sheet.merge_range(1, 0, 1, last_column, subtitle, styles["subtitle"])
    sheet.merge_range(2, 0, 2, last_column, previred.REVIEW_WARNING,
                      styles["warning"])
    sheet.set_row(0, 26)
    sheet.set_row(1, 18)
    sheet.set_row(2, 18)


def _write_headers(sheet, styles, technical_row=True):
    """Encabezado legible y, debajo, la fila técnica con el número oficial."""
    row = 4
    columns = list(CONTEXT_COLUMNS) + list(previred.FIELD_NAMES)
    for index, label in enumerate(columns):
        sheet.write(row, index, label, styles["header"])
    if technical_row:
        for index in range(len(CONTEXT_COLUMNS)):
            sheet.write(row + 1, index, "contexto", styles["header_tech"])
        for index in range(previred.FIELD_COUNT):
            sheet.write(row + 1, len(CONTEXT_COLUMNS) + index,
                        "campo %d" % (index + 1), styles["header_tech"])
    sheet.set_column(0, 0, 24)
    sheet.set_column(1, 1, 13)
    sheet.set_column(2, 2, 13)
    sheet.set_column(3, 3, 5)
    sheet.set_column(4, 6, 20)
    sheet.set_column(7, len(columns) - 1, 14)
    first_data = row + (2 if technical_row else 1)
    # Congelar encabezados y dejar el autofiltro sobre la fila legible.
    sheet.freeze_panes(first_data, 1)
    sheet.autofilter(row, 0, first_data - 1, len(columns) - 1)
    return first_data


def _write_records(sheet, styles, records, first_row):
    """Escribe los trabajadores conservando principal + anexas contiguas."""
    row = first_row
    for index, record in enumerate(records):
        base = styles["cell"] if index % 2 == 0 else styles["cell_alt"]
        for offset, values in enumerate(record.rows):
            style = base if offset == 0 else styles["cell_annex"]
            line_type = ""
            if len(values) == previred.FIELD_COUNT:
                line_type = values[previred.F_LINE_TYPE - 1]
            sheet.write_string(row, 0, record.department_label, style)
            sheet.write_string(
                row, 1,
                "%s %s" % (line_type,
                           previred.LINE_TYPE_LABELS.get(line_type, "")),
                style)
            for position, cell in enumerate(values):
                sheet.write_string(row, len(CONTEXT_COLUMNS) + position,
                                   str(cell or ""), style)
            row += 1
    return row


def _write_summary(workbook, styles, dataset, scope_label, file_entries):
    sheet = workbook.add_worksheet(SUMMARY_SHEET)
    sheet.set_column(0, 0, 34)
    sheet.set_column(1, 1, 72)
    _write_masthead(sheet, styles, dataset, 1,
                    "%s · período %s" % (dataset.company_name, dataset.period))

    counters = dataset.counters
    rows = [
        ("Empresa", dataset.company_name),
        ("RUT empresa", dataset.company_vat or "-"),
        ("Período", dataset.period),
        ("Alcance", scope_label),
        ("Motor de nómina", dataset.engine or "-"),
        ("Perfil de formato", dataset.profile_name or "-"),
        ("Formato Previred", "%s — versión %s (%s)"
         % (previred.SPEC_NAME, dataset.spec_version,
            dataset.spec_effective_from)),
        ("Fuente de la especificación", dataset.spec_url),
        ("Campos por registro", str(previred.FIELD_COUNT)),
        ("Trabajadores", str(counters["workers"])),
        ("Líneas principales", str(counters["principal"])),
        ("Líneas anexas", str(counters["annexes"])),
        ("Total de líneas", str(counters["rows"])),
        ("Departamentos", str(counters["departments"])),
        ("Registros sin departamento", str(counters["without_department"])),
        ("Errores", str(counters["errors"])),
        ("Advertencias", str(counters["warnings"])),
    ]
    row = 4
    for key, value in rows:
        sheet.write(row, 0, key, styles["key"])
        sheet.write(row, 1, value, styles["value"])
        row += 1

    # Conciliación agregada: cuántas líneas aporta cada departamento. Es el
    # control que permite comprobar que la suma de los archivos por
    # departamento es el consolidado.
    row += 1
    sheet.write(row, 0, "Conciliación por departamento", styles["header"])
    sheet.write(row, 1, "trabajadores / líneas principales / líneas anexas",
                styles["header"])
    row += 1
    grouped = dataset.by_department()
    for department_id, label, _code in dataset.departments():
        records = grouped.get(department_id, [])
        annexes = sum(len(record.annexes) for record in records)
        sheet.write(row, 0, label, styles["key"])
        sheet.write(row, 1, "%d / %d / %d"
                    % (len(records), len(records), annexes), styles["value"])
        row += 1
    sheet.write(row, 0, "TOTAL", styles["key"])
    sheet.write(row, 1, "%d / %d / %d"
                % (counters["workers"], counters["principal"],
                   counters["annexes"]), styles["value"])
    row += 2

    if file_entries:
        sheet.write(row, 0, "Archivos oficiales del lote", styles["header"])
        sheet.write(row, 1, "SHA-256", styles["header"])
        row += 1
        for entry in file_entries:
            sheet.write(row, 0, entry["filename"], styles["value"])
            sheet.write(row, 1, entry["sha256"], styles["value"])
            row += 1
        row += 1

    if dataset.issues:
        sheet.write(row, 0, "Hallazgos", styles["header"])
        sheet.write(row, 1, "", styles["header"])
        row += 1
        for issue in dataset.issues:
            style = styles["issue_error"] if issue.is_error \
                else styles["issue_warning"]
            sheet.write(row, 0,
                        "ERROR" if issue.is_error else "Advertencia", style)
            sheet.write(row, 1, issue.message, style)
            row += 1


def _add_records_sheet(workbook, styles, dataset, records, sheet_name,
                       subtitle, technical_row):
    sheet = workbook.add_worksheet(sheet_name)
    last_column = len(CONTEXT_COLUMNS) + previred.FIELD_COUNT - 1
    _write_masthead(sheet, styles, dataset, last_column, subtitle)
    first_row = _write_headers(sheet, styles, technical_row)
    _write_records(sheet, styles, records, first_row)
    return sheet


def build_workbook(stream, dataset, scope_label="Consolidado",
                   per_department_sheets=False, records=None,
                   file_entries=(), technical_row=True):
    """Escribe el Excel de revisión en `stream`.

    `records` permite generar el libro de un solo departamento reutilizando el
    mismo dataset; si es `None` se usa el lote completo.
    """
    selected = dataset.sorted_records() if records is None else list(records)
    if len(selected) > MAX_ROWS:
        raise ValueError(
            "El lote tiene %d trabajadores y una hoja de Excel admite %d "
            "filas. Genere el archivo por departamento."
            % (len(selected), MAX_ROWS))

    workbook = xlsxwriter.Workbook(stream, {
        "in_memory": True,
        # Sin esto xlsxwriter convierte «08-2026» o un RUT largo en número.
        "strings_to_numbers": False,
        "strings_to_formulas": False,
        "strings_to_urls": False,
    })
    workbook.set_properties({
        "title": "Previred — archivo de revisión",
        "subject": "%s · %s" % (dataset.company_name, dataset.period),
        "comments": previred.REVIEW_WARNING,
    })
    styles = _formats(workbook)

    _write_summary(workbook, styles, dataset, scope_label, file_entries)

    namer = _SheetNamer()
    namer.take(SUMMARY_SHEET)
    _add_records_sheet(
        workbook, styles, dataset, selected, namer.take(CONSOLIDATED_SHEET),
        "%s · período %s · %d trabajadores"
        % (dataset.company_name, dataset.period, len(selected)),
        technical_row)

    if per_department_sheets:
        grouped = {}
        for record in selected:
            grouped.setdefault(record.department_id or 0, []).append(record)
        for department_id, label, _code in dataset.departments():
            department_records = grouped.get(department_id)
            if not department_records:
                continue
            _add_records_sheet(
                workbook, styles, dataset, department_records,
                namer.take(label),
                "%s · %s · período %s"
                % (dataset.company_name, label, dataset.period),
                technical_row)

    workbook.close()
    return workbook
