#!/usr/bin/env python3
"""Regenera la matriz Previred desde el código de los generadores vigentes.

La correspondencia campo Previred → dato del motor **no se escribe a mano**:
se extrae del generador que cada proveedor tiene en producción. Si el
proveedor cambia su generador, este script vuelve a leerlo y las pruebas de
los bridges detectan la diferencia.

Uso (con los addons del proveedor accesibles en local o por SSH):

    python tools/regen_previred_matrix.py /ruta/a/opt/rrhh

Escribe:
    step_hr_previred_blueminds/models/field_matrix.py
    step_hr_previred_simpledigital/models/field_matrix.py
    docs/PREVIRED_MATRIZ.md
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BLUEMINDS = "l10n_cl_hr/wizard/wizard_export_csv_previred.py"
SIMPLEDIGITAL = "l10n_cl_simpledigital_payroll/controllers/previred_txt.py"


def classify(expr):
    """Clasifica la expresión del generador en un tipo de origen."""
    if "get_payslip_lines_value_2" in expr or "_get_payslip_lines" in expr \
            or "rule_codes" in expr:
        return "rule"
    if "indicadores_id" in expr or "previred_indicator" in expr:
        return "indicator"
    if "contract." in expr or "contract_id." in expr:
        return "contract"
    if ("employee_id." in expr or "employee." in expr or "name_parts" in expr
            or "gender" in expr or "country" in expr):
        return "employee"
    if "company." in expr or "self.env.user.company_id" in expr:
        return "company"
    if ("period_str" in expr or "date_start_format" in expr
            or "date_stop_format" in expr or "period_dt" in expr):
        return "period"
    if re.fullmatch(r'''\s*["'].*["']\s*''', expr):
        return "constant"
    return "computed"


def normalize(expr):
    expr = re.sub(r"\s+", " ", expr.split("#")[0].strip())
    if expr in ('"0"', "'0'"):
        return "unused", '"0" (uso futuro / no aplica en este motor)'
    if expr in ('" "', "''", '""'):
        return "unused", "en blanco (uso futuro / no aplica)"
    return classify(expr), expr


def parse_blueminds(path):
    """Extrae la lista `line_employee` del asistente del proveedor."""
    src = io.open(path, encoding="utf-8").read()
    start = src.index("line_employee = [self._acortar_str(rut, 11)")
    end = src.index("writer.writerow([str(l) for l in line_employee])")
    block = src[start:end]
    block = "\n".join(
        line for line in block.split("\n")
        if not line.strip().startswith("#"))
    block = block[block.index("[") + 1:block.rindex("]")]
    return _split_top_level(block)


def parse_simpledigital(path):
    """Extrae los nombres de la f-string principal y sus asignaciones."""
    src = io.open(path, encoding="utf-8").read()
    match = re.search(r'formatted_line = f"([^"]+)"', src)
    names = re.findall(r"\{(\w+)\}", match.group(1))
    body = src[src.index("def download_previred_txt"):
               src.index('formatted_line = f"')]
    assign = {}
    for line in body.split("\n"):
        found = re.match(r"\s*(\w+)\s*=\s*(.+)$", line)
        if found and found.group(1) in names:
            assign.setdefault(found.group(1), []).append(found.group(2).strip())
    return [" ;; ".join(assign.get(name, [])) or '""' for name in names]


def _split_top_level(text):
    items, buf, depth = [], "", 0
    for char in text:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            items.append(buf.strip())
            buf = ""
        else:
            buf += char
    if buf.strip():
        items.append(buf.strip())
    return [re.sub(r"\s+", " ", item.split("#")[0].strip())
            for item in items if item.strip()]


HEADER = '''"""Matriz campo Previred -> dato del motor {label}.

**Generada desde el codigo del generador vigente**, no deducida: cada entrada
guarda la expresion exacta de `{source}` que produce ese campo.

Es la evidencia de que ninguna correspondencia entre regla salarial y campo
oficial se adivino, y el punto de partida para conciliar importes contra
muestras existentes. Si el proveedor cambia su generador, esta matriz debe
regenerarse y las pruebas de conciliacion lo detectan.

NO EDITAR A MANO: `python tools/regen_previred_matrix.py <ruta a /opt/rrhh>`.
"""

from odoo.addons.step_hr_previred.models.previred_adapter import FieldSource

#: `(posicion, tipo de origen, expresion del generador)`
RAW_MATRIX = [
'''

FOOTER = ''']


def field_sources(notes=None):
    """Los 105 `FieldSource`, con las notas de revision que se le pasen."""
    notes = notes or {}
    return [FieldSource(position, kind, source, notes.get(position, ""))
            for position, kind, source in RAW_MATRIX]
'''


def write_matrix(module, label, source, expressions):
    if len(expressions) != 105:
        raise SystemExit(
            "%s entregó %d campos y deben ser 105." % (label, len(expressions)))
    rows = []
    for index, expr in enumerate(expressions, start=1):
        kind, text = normalize(expr)
        rows.append("    (%d, %r, %r),\n" % (index, kind, text))
    path = os.path.join(HERE, module, "models", "field_matrix.py")
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        HEADER.format(label=label, source=source) + "".join(rows) + FOOTER)
    print("escrito", path)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    root = sys.argv[1]
    write_matrix(
        "step_hr_previred_blueminds", "Blueminds (l10n_cl_hr)",
        "wizard.export.csv.previred.action_generate_csv",
        parse_blueminds(os.path.join(root, BLUEMINDS)))
    write_matrix(
        "step_hr_previred_simpledigital", "SimpleDigital",
        "PreviredExportController.download_previred_txt",
        parse_simpledigital(os.path.join(root, SIMPLEDIGITAL)))
    print("Regenere después docs/PREVIRED_MATRIZ.md con el mismo script de "
          "documentación.")


if __name__ == "__main__":
    main()
