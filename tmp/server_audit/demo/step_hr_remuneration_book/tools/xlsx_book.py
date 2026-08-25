"""Layout Steps del libro consolidado en Excel.

Reproduce la lógica del libro que usa la contabilidad —agrupación por
departamento, subtotales, total general y las 24 columnas por código DT— sin
copiar sus defectos visuales: no hay celdas rellenas de negro para simular
vacíos, ni hojas ocultas con el LRE completo.
"""

import xlsxwriter

from . import dt_book

SHEET_NAME = "Libro de Remuneraciones"
CONTROL_SHEET_NAME = "Control"

#: Legal horizontal, igual que el libro que ya se imprime hoy. A4 no permite
#: leer 24 columnas y A3 no está disponible en las impresoras del cliente.
PAPER_LEGAL = 5

HEADER_ROW = 4
FIRST_DATA_ROW = HEADER_ROW + 1

GREEN_DARK = "#174A35"
GREEN_MID = "#2E6B4C"
GREEN_SOFT = "#EAF4EE"
GREEN_LINE = "#D4E3DA"
GREY_LINE = "#DCE7E0"


def _formats(workbook):
    money = "#,##0"
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
        "header": workbook.add_format({
            "bold": True, "font_size": 9, "font_color": "#FFFFFF",
            "bg_color": GREEN_MID, "border": 1, "border_color": GREEN_LINE,
            "text_wrap": True, "align": "center", "valign": "vcenter",
        }),
        "text": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "valign": "vcenter",
        }),
        "text_alt": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "bg_color": "#F5F9F6", "valign": "vcenter",
        }),
        "money": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "num_format": money, "valign": "vcenter",
        }),
        "money_alt": workbook.add_format({
            "font_size": 9, "border": 1, "border_color": GREY_LINE,
            "bg_color": "#F5F9F6", "num_format": money, "valign": "vcenter",
        }),
        "subtotal_text": workbook.add_format({
            "bold": True, "font_size": 9, "bg_color": "#DCEAE1",
            "border": 1, "border_color": GREEN_LINE, "valign": "vcenter",
        }),
        "subtotal_money": workbook.add_format({
            "bold": True, "font_size": 9, "bg_color": "#DCEAE1",
            "border": 1, "border_color": GREEN_LINE, "num_format": money,
            "valign": "vcenter",
        }),
        "total_text": workbook.add_format({
            "bold": True, "font_size": 10, "font_color": "#FFFFFF",
            "bg_color": GREEN_DARK, "border": 1, "border_color": GREEN_DARK,
            "valign": "vcenter",
        }),
        "total_money": workbook.add_format({
            "bold": True, "font_size": 10, "font_color": "#FFFFFF",
            "bg_color": GREEN_DARK, "border": 1, "border_color": GREEN_DARK,
            "num_format": money, "valign": "vcenter",
        }),
        "control_key": workbook.add_format({"bold": True, "valign": "top"}),
        "control_value": workbook.add_format({"valign": "top"}),
        "control_wrap": workbook.add_format({"text_wrap": True, "valign": "top"}),
    }


def _column_letter(index):
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def build_workbook(stream, dataset):
    """Escribe el libro consolidado en ``stream`` y devuelve el workbook."""
    workbook = xlsxwriter.Workbook(stream, {"in_memory": True})
    styles = _formats(workbook)
    sheet = workbook.add_worksheet(SHEET_NAME)
    columns = dataset.columns
    last_column = len(columns) - 1

    _write_masthead(sheet, styles, dataset, last_column)
    _write_headers(sheet, styles, columns)
    subtotal_rows = _write_body(sheet, styles, dataset, columns)
    _write_grand_total(sheet, styles, dataset, columns, subtotal_rows)
    _configure_printing(sheet)
    _write_control_sheet(workbook, styles, dataset)

    workbook.close()
    return workbook


def _write_masthead(sheet, styles, dataset, last_column):
    sheet.merge_range(0, 0, 0, last_column, dataset.title, styles["title"])
    company_line = dataset.company_name
    if dataset.company_vat:
        company_line = "%s · RUT %s" % (
            company_line, dt_book.rut_display(dataset.company_vat))
    sheet.merge_range(1, 0, 1, last_column, company_line, styles["subtitle"])
    sheet.merge_range(
        2, 0, 2, last_column,
        "Período %s a %s · Fuente del cálculo: %s · %s · Generado %s" % (
            dataset.date_from, dataset.date_to, dataset.source,
            dataset.scope_label, dataset.generated_at),
        styles["subtitle"],
    )
    sheet.set_row(0, 30)
    sheet.set_row(1, 20)
    sheet.set_row(2, 18)
    sheet.set_row(3, 6)


def _write_headers(sheet, styles, columns):
    sheet.set_row(HEADER_ROW, 46)
    for index, column in enumerate(columns):
        sheet.write(HEADER_ROW, index, column.header, styles["header"])
        sheet.set_column(index, index, column.width)


def _write_body(sheet, styles, dataset, columns):
    """Escribe detalle y subtotales. Devuelve las filas de subtotal."""
    row = FIRST_DATA_ROW
    subtotal_rows = []
    for group in dataset.groups:
        first_line_row = row
        for position, line in enumerate(group.lines):
            alternate = position % 2 == 1
            for index, column in enumerate(columns):
                value = line.cell(column)
                if column.kind == "count":
                    # Cantidad va vacía en el detalle, como el libro original.
                    sheet.write_blank(
                        row, index, None,
                        styles["money_alt" if alternate else "money"])
                elif column.kind == "rut":
                    # Siempre texto: conserva ceros iniciales y la K.
                    sheet.write_string(
                        row, index, value or "",
                        styles["text_alt" if alternate else "text"])
                elif column.is_numeric:
                    sheet.write_number(
                        row, index, value or 0,
                        styles["money_alt" if alternate else "money"])
                else:
                    sheet.write_string(
                        row, index, value or "",
                        styles["text_alt" if alternate else "text"])
            row += 1
        last_line_row = row - 1
        _write_subtotal(sheet, styles, group, columns, row,
                        first_line_row, last_line_row)
        subtotal_rows.append(row)
        row += 1
    return subtotal_rows


def _write_subtotal(sheet, styles, group, columns, row, first_row, last_row):
    for index, column in enumerate(columns):
        value = group.cell(column)
        if column.kind == "group":
            sheet.write_string(row, index, value, styles["subtotal_text"])
        elif column.kind == "count":
            # Cantidad cuenta líneas de detalle, no suma celdas: una fórmula
            # SUM sobre celdas vacías daría cero al recalcular.
            sheet.write_number(row, index, value or 0, styles["subtotal_money"])
        elif column.is_numeric:
            if group.lines:
                # Fórmula auditable con el resultado ya escrito en caché: el
                # archivo muestra el valor correcto aunque no se recalcule.
                letter = _column_letter(index)
                sheet.write_formula(
                    row, index,
                    "=SUM(%s%s:%s%s)" % (letter, first_row + 1, letter,
                                         last_row + 1),
                    styles["subtotal_money"], value or 0,
                )
            else:
                sheet.write_number(row, index, value or 0,
                                   styles["subtotal_money"])
        else:
            sheet.write_blank(row, index, None, styles["subtotal_text"])


def _write_grand_total(sheet, styles, dataset, columns, subtotal_rows):
    row = FIRST_DATA_ROW + len(dataset.lines) + len(dataset.groups)
    for index, column in enumerate(columns):
        value = dataset.total_cell(column)
        if column.kind == "group":
            sheet.write_string(row, index, value, styles["total_text"])
        elif column.is_numeric:
            if subtotal_rows:
                letter = _column_letter(index)
                formula = "=%s" % "+".join(
                    "%s%s" % (letter, number + 1) for number in subtotal_rows
                )
                sheet.write_formula(row, index, formula,
                                    styles["total_money"], value or 0)
            else:
                sheet.write_number(row, index, value or 0,
                                   styles["total_money"])
        else:
            sheet.write_blank(row, index, None, styles["total_text"])
    sheet.set_row(row, 20)


def _configure_printing(sheet):
    # Congela cabecera y las tres primeras columnas (departamento, RUT, nombre).
    sheet.freeze_panes(FIRST_DATA_ROW, 3)
    sheet.set_landscape()
    sheet.set_paper(PAPER_LEGAL)
    sheet.fit_to_pages(1, 0)  # una página de ancho, alto libre
    sheet.repeat_rows(0, HEADER_ROW)
    sheet.repeat_columns(0, 2)
    sheet.set_margins(0.3, 0.3, 0.4, 0.4)
    # Sin autofiltro: las filas de subtotal quedarían dentro del rango filtrado
    # y darían resultados engañosos.


def _write_control_sheet(workbook, styles, dataset):
    """Hoja de control sin duplicar datos personales."""
    sheet = workbook.add_worksheet(CONTROL_SHEET_NAME)
    sheet.set_column(0, 0, 42)
    sheet.set_column(1, 1, 60)
    counters = dataset.counters
    rows = [
        ("Empresa", dataset.company_name),
        ("RUT empresa", dt_book.rut_display(dataset.company_vat)),
        ("Período", dataset.period_label),
        ("Desde", str(dataset.date_from)),
        ("Hasta", str(dataset.date_to)),
        ("Alcance del informe", dataset.scope_label),
        ("Perfil de mapeo DT", dataset.source),
        ("Origen del perfil", dataset.profile_origin_label),
        ("Generado", dataset.generated_at),
        ("Tolerancia de conciliación (pesos)", dataset.tolerance),
        ("Liquidaciones consideradas", counters.get("payslips", 0)),
        ("Líneas del informe", counters.get("lines", 0)),
        ("Trabajadores únicos", counters.get("unique_employees", 0)),
        ("Departamentos", counters.get("departments", 0)),
        ("Líneas sin departamento", counters.get("without_department", 0)),
        ("Líneas sin RUT", counters.get("without_rut", 0)),
        ("Líneas con RUT inválido", counters.get("invalid_rut", 0)),
        ("Trabajadores con más de una liquidación",
         counters.get("multiple_payslips", 0)),
        ("Diferencias de conciliación",
         counters.get("reconciliation_warnings", 0)),
    ]
    for index, (key, value) in enumerate(rows):
        sheet.write(index, 0, key, styles["control_key"])
        sheet.write(index, 1, value, styles["control_value"])

    row = len(rows) + 1
    sheet.write(row, 0, "Advertencias", styles["control_key"])
    warnings = dataset.warnings or []
    if not warnings:
        sheet.write(row, 1, "Sin advertencias.", styles["control_value"])
    for offset, issue in enumerate(warnings):
        sheet.write(row + offset, 1, issue.message, styles["control_wrap"])
