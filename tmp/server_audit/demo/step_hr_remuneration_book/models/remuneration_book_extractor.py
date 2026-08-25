import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from ..tools import dt_book
from . import remuneration_book_adapter as adapters

_logger = logging.getLogger(__name__)


class RemunerationBookExtractor(models.AbstractModel):
    """Extractor propio de Steps: liquidación → valores por código DT.

    Lee únicamente valores YA calculados por el motor de nómina instalado. No
    replica fórmulas previsionales ni modifica el módulo del proveedor, y no
    depende de `request`, de modo que funciona igual desde el asistente, desde
    el motor de informes, desde pruebas y desde trabajos programados.
    """

    _name = "step.remuneration.book.extractor"
    _description = "Extractor del Libro de Remuneraciones Steps"

    # -- API pública --------------------------------------------------------

    @api.model
    def payslip_rule_codes(self, payslips):
        """Códigos de regla presentes en ESTAS liquidaciones.

        Es la única base admitida para autodetectar un perfil: mirar todas las
        reglas de la base mezclaría motores de nómina de otras compañías.
        """
        return set(payslips.mapped("line_ids.code")) - {False, ""}

    @api.model
    def extract_lines(self, payslips, profile):
        """Devuelve ``(lines, issues)`` para el conjunto de liquidaciones.

        Cada liquidación produce exactamente una línea, resuelta de forma
        determinística por su propio registro: no hay correspondencia por
        posición ni por proximidad.
        """
        issues = []
        blocking = profile.validation_errors()
        if blocking:
            issues.append(dt_book.Issue(
                "error", "invalid_profile",
                _("El perfil «%(profile)s» no puede usarse: %(errors)s",
                  profile=profile.name, errors=" ".join(blocking)),
            ))
            return [], issues

        # Una sola lectura por lote de todo lo que se va a recorrer.
        payslips.mapped("line_ids.code")
        payslips.mapped("worked_days_line_ids.work_entry_type_id.code")
        payslips.mapped("contract_id.department_id.name")
        payslips.mapped("employee_id.department_id.name")

        adapter_values, adapter_issues = self._adapter_values(payslips, profile)
        issues.extend(adapter_issues)
        order = self._resolution_order(profile)

        lines = []
        for payslip in payslips:
            line, line_issues = self._extract_line(
                payslip, profile, order, adapter_values)
            issues.extend(line_issues)
            if line is not None:
                lines.append(line)
        issues.extend(self._check_ambiguity(lines))
        return lines, issues

    # -- adaptadores --------------------------------------------------------

    def _adapter_values(self, payslips, profile):
        """Resuelve TODOS los adaptadores del perfil en una sola pasada.

        Se agrupa por `(adaptador, parámetro)` para no repetir la misma
        consulta en dos códigos DT distintos y para no consultar una vez por
        liquidación.
        """
        issues = []
        results = {}
        wanted = {}
        for mapping in profile.line_ids:
            if mapping.source_type != "adapter":
                continue
            wanted.setdefault(
                (mapping.adapter_key, mapping.adapter_param or ""), []
            ).append(mapping.dt_code)

        for (key, param), dt_codes in wanted.items():
            adapter = adapters.get_adapter(key)
            if adapter is None or not adapter.is_installed(self.env):
                issues.append(dt_book.Issue(
                    "error", "adapter_unavailable",
                    _("El adaptador «%(key)s» que el perfil usa para los "
                      "códigos %(codes)s no está disponible en esta base.",
                      key=key or "-", codes=", ".join(sorted(dt_codes))),
                ))
                continue
            message = adapter.check_param(param)
            if message:
                issues.append(dt_book.Issue(
                    "error", "adapter_param_rejected", message))
                continue
            results[(key, param)] = adapter.values(self.env, payslips, param)
        return results, issues

    # -- orden de resolución -------------------------------------------------

    def _resolution_order(self, profile):
        """Orden topológico de los códigos DT del perfil.

        Se calcula una vez por informe, no una vez por liquidación. El perfil
        ya fue validado, así que aquí no puede haber ciclos.
        """
        mappings = {(line.dt_code or "").strip(): line for line in profile.line_ids}
        pending = dict(mappings)
        order = []
        resolved = set()
        while pending:
            ready = [
                code for code, mapping in pending.items()
                if mapping.source_type not in ("aggregate", "difference")
                or all(
                    operand in resolved
                    for operand in mapping.codes_list("operand_codes")
                )
            ]
            if not ready:
                # Defensivo: la validación del perfil ya lo impide.
                order.extend(pending.values())
                break
            for code in sorted(ready):
                order.append(pending.pop(code))
                resolved.add(code)
        return order

    # -- resolución de una liquidación --------------------------------------

    def _extract_line(self, payslip, profile, order, adapter_values):
        issues = []
        department, department_issue = self._resolve_department(payslip)
        if department_issue:
            issues.append(department_issue)

        rut = payslip.employee_id.identification_id or ""
        if not dt_book.rut_key(rut):
            issues.append(dt_book.Issue(
                "warning", "line_without_rut",
                _("La liquidación %s no tiene RUT registrado en el trabajador.",
                  payslip.id),
            ))
        elif not dt_book.is_valid_rut(rut):
            issues.append(dt_book.Issue(
                "warning", "invalid_rut",
                _("La liquidación %s tiene un RUT con dígito verificador "
                  "inválido.", payslip.id),
            ))

        values = self._resolve_values(payslip, order, adapter_values)
        negatives = [
            code for code in dt_book.REQUIRED_DT_CODES
            if code != dt_book.CODE_RUT and int(values.get(code) or 0) < 0
        ]
        if negatives:
            issues.append(dt_book.Issue(
                "warning", "negative_value",
                _("La liquidación %(id)s informa valores negativos en los "
                  "códigos %(codes)s.", id=payslip.id,
                  codes=", ".join(sorted(negatives))),
            ))

        line = dt_book.BookLine(
            payslip_id=payslip.id,
            employee_id=payslip.employee_id.id,
            employee_name=payslip.employee_id.name or "",
            rut=rut,
            department=department,
            values=values,
        )
        return line, issues

    def _resolve_department(self, payslip):
        """Departamento histórico de la línea.

        Prioridad verificada contra la base: el contrato guarda un
        departamento propio y estable; el de la liquidación es un campo
        `related` almacenado que se recalcula si luego se mueve al trabajador,
        así que sólo se usa como respaldo; el del empleado es el último recurso
        y queda advertido.
        """
        contract_department = payslip.contract_id.department_id
        if contract_department:
            return contract_department.name, None
        payslip_department = payslip.department_id
        if payslip_department:
            return payslip_department.name, dt_book.Issue(
                "warning", "department_from_payslip",
                _("La liquidación %s no tiene departamento en el contrato: se "
                  "usó el de la liquidación, que puede reflejar el estado "
                  "actual del trabajador.", payslip.id),
            )
        employee_department = payslip.employee_id.department_id
        if employee_department:
            return employee_department.name, dt_book.Issue(
                "warning", "department_from_employee",
                _("La liquidación %s tomó el departamento actual del "
                  "trabajador: el libro histórico podría cambiar si se le "
                  "reasigna.", payslip.id),
            )
        return "", dt_book.Issue(
            "warning", "department_missing",
            _("La liquidación %(id)s no tiene departamento: se agrupa en "
              "«%(label)s».", id=payslip.id, label=dt_book.NO_DEPARTMENT_LABEL),
        )

    def _resolve_values(self, payslip, order, adapter_values):
        """Aplica el perfil sobre una liquidación siguiendo el orden topológico.

        No hay «pasadas»: cuando llega el turno de un código derivado, sus
        operandos ya están resueltos. Si alguno faltara -lo que la validación
        del perfil impide- el código no se inventa como cero: queda ausente y
        el validador estructural lo detecta.
        """
        values = {}
        rule_totals = None
        for mapping in order:
            source = mapping.source_type
            if source in ("aggregate", "difference"):
                operands = mapping.codes_list("operand_codes")
                numbers = [int(values.get(code) or 0) for code in operands]
                if source == "aggregate":
                    result = sum(numbers)
                else:
                    result = numbers[0] - sum(numbers[1:]) if numbers else 0
                values[mapping.dt_code] = mapping.apply_sign(result)
                continue
            if source == "rule":
                if rule_totals is None:
                    rule_totals = self._rule_totals(payslip)
                codes = mapping.codes_list("rule_codes")
                total = sum(rule_totals.get(code, 0.0) for code in codes)
                values[mapping.dt_code] = mapping.apply_sign(int(round(total)))
                continue
            if source == "worked_days":
                codes = mapping.codes_list("rule_codes")
                total = sum(
                    line.number_of_days or 0.0
                    for line in payslip.worked_days_line_ids
                    if line.work_entry_type_id.code in codes
                )
                values[mapping.dt_code] = mapping.apply_sign(int(round(total)))
                continue
            if source == "adapter":
                key = (mapping.adapter_key, mapping.adapter_param or "")
                raw = adapter_values.get(key, {}).get(payslip.id, 0)
                values[mapping.dt_code] = mapping.apply_sign(int(raw))
                continue
            # `employee_rut` y `zero` no aportan importe a la fila.
            values[mapping.dt_code] = 0
        return values

    @staticmethod
    def _rule_totals(payslip):
        totals = {}
        for line in payslip.line_ids:
            if line.code:
                totals[line.code] = totals.get(line.code, 0.0) + line.total
        return totals

    # -- correspondencia segura ---------------------------------------------

    def _check_ambiguity(self, lines):
        """Detecta líneas que no se pueden distinguir entre sí.

        Dos liquidaciones del mismo trabajador en el mes son legítimas y se
        muestran por separado; lo que no se admite es no poder identificar a
        qué liquidación pertenece cada fila. Como cada línea nace de su propio
        registro, la ambigüedad sólo puede aparecer si dos liquidaciones
        comparten identificador, lo que indica datos corruptos.
        """
        issues = []
        seen = set()
        for line in lines:
            if line.payslip_id in seen:
                issues.append(dt_book.Issue(
                    "error", "duplicated_payslip",
                    _("La liquidación %s aparece dos veces en el informe.",
                      line.payslip_id),
                ))
            seen.add(line.payslip_id)
        return issues

    # -- CSV oficial ---------------------------------------------------------

    @api.model
    def official_csv_source(self):
        """Fuente instalada capaz de generar el archivo oficial DT, o vacío."""
        installed = set(self.env["ir.module.module"].sudo().search([
            ("name", "in", [
                "l10n_cl_simpledigital_payroll", "l10n_cl_hr_electronic_book",
            ]),
            ("state", "=", "installed"),
        ]).mapped("name"))
        if "l10n_cl_simpledigital_payroll" in installed:
            return "l10n_cl_simpledigital_payroll", "Steps"
        if "l10n_cl_hr_electronic_book" in installed:
            return ("l10n_cl_hr_electronic_book",
                    "Libro de Remuneraciones Electrónico")
        return "", ""

    @api.model
    def official_csv(self, wizard):
        """Delega el archivo oficial LRE en la fuente instalada.

        El archivo para Mi DT debe conservar íntegramente sus columnas y su
        orden, así que se reutiliza tal cual lo entrega el proveedor y no se
        reconstruye desde el libro consolidado de 24 columnas.
        """
        module, label = self.official_csv_source()
        if module == "l10n_cl_simpledigital_payroll":
            return self._official_csv_simpledigital(wizard), label
        if module == "l10n_cl_hr_electronic_book":
            return self._official_csv_electronic_book(wizard), label
        raise UserError(_(
            "No hay una fuente instalada que genere el archivo oficial de la "
            "Dirección del Trabajo. Instale un motor de nómina compatible o el "
            "Libro de Remuneraciones Electrónico."
        ))

    def _official_csv_simpledigital(self, wizard):
        """Aísla aquí la dependencia del proveedor con `request`.

        El controlador de SimpleDigital usa `request.env` internamente, por lo
        que sólo puede ejecutarse dentro de una solicitud HTTP. La limitación
        queda encapsulada en este único método.
        """
        from odoo.addons.l10n_cl_simpledigital_payroll.controllers.libro_remuneraciones import (
            LibroRemuneracionesController,
        )
        payslips = wizard._payslips()
        return LibroRemuneracionesController()._generate_csv_content(
            payslips, include_header=True
        )

    def _official_csv_electronic_book(self, wizard):
        import base64
        import re

        source = self.env["hr.salary.employee.month"].with_company(
            wizard.company_id
        ).with_context(
            allowed_company_ids=[wizard.company_id.id]
        ).create({"end_date": wizard.date_to})
        action = source.library()
        match = re.search(r"[?&]id=(\d+)", action.get("url", ""))
        if not match:
            raise UserError(_("La fuente de nómina no devolvió un archivo válido."))
        attachment = self.env["ir.attachment"].sudo().browse(
            int(match.group(1))
        ).exists()
        if not attachment or not attachment.datas:
            raise UserError(_(
                "No fue posible leer el archivo oficial generado por la fuente."
            ))
        try:
            return base64.b64decode(attachment.datas).decode("cp1252")
        finally:
            # No se conserva copia permanente del archivo con datos personales.
            attachment.unlink()
