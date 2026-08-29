"""Constructor del dataset canónico Previred.

Hay **una sola** función que construye el lote: `build_dataset`. El TXT
consolidado, cada TXT por departamento, el Excel consolidado y el Excel por
departamento son particiones de su resultado. Ninguna salida vuelve a
consultar la base ni recalcula un importe, que es lo que garantiza que todas
cuadren entre sí.

Correcciones que el dataset aplica sobre los generadores vigentes
-----------------------------------------------------------------
El generador de Blueminds busca `hr.payslip` por `date_from` **sin filtrar
compañía ni estado**: exporta liquidaciones de otras empresas y liquidaciones
en borrador. El core no hereda ese comportamiento: selecciona él mismo las
liquidaciones elegibles y **descarta toda fila que no corresponda a una de
ellas**, aunque el motor la haya emitido. La divergencia es deliberada y está
cubierta por pruebas.
"""

import logging
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP

from odoo import _, api, models

from ..tools import previred

_logger = logging.getLogger(__name__)

#: Estados que NUNCA pueden exportarse, sea cual sea el motor: una liquidación
#: en borrador no está calculada y una cancelada fue rechazada.
FORBIDDEN_STATES = ("draft", "cancel")


class PreviredExtractor(models.AbstractModel):
    """Extractor del lote Previred."""

    _name = "step.previred.extractor"
    _description = "Extractor del dataset Previred"

    # -- API pública --------------------------------------------------------

    @api.model
    def eligible_payslips(self, company, date_from, date_to, states):
        """Liquidaciones elegibles. **Este** es el dominio correcto.

        Se acota por compañía, por período completo y por los estados que el
        motor declara como validados, excluyendo siempre borradores y
        canceladas.
        """
        states = tuple(state for state in states
                       if state not in FORBIDDEN_STATES)
        return self.env["hr.payslip"].search([
            ("company_id", "=", company.id),
            ("date_from", "=", date_from),
            ("date_to", "=", date_to),
            ("state", "in", list(states)),
        ], order="employee_id, id")

    @api.model
    def build_dataset(self, company, date_from, date_to, adapter,
                      states=None, departments=None,
                      allow_without_department=False, profile_name="",
                      spec_version=previred.SPEC_VERSION,
                      spec_url=previred.SPEC_URL,
                      spec_effective_from=previred.SPEC_EFFECTIVE_FROM):
        """Construye el lote completo. Es el único punto de entrada."""
        states = tuple(states or adapter.eligible_states)
        dataset = previred.Dataset(
            company_name=company.name,
            company_vat=self._company_vat(company),
            period=date_from.strftime("%Y%m"),
            profile_name=profile_name,
            engine=adapter.label,
            spec_version=spec_version,
            spec_url=spec_url,
            spec_effective_from=spec_effective_from,
        )
        dataset.eligible_states = states

        payslips = self.eligible_payslips(company, date_from, date_to, states)
        dataset.eligible_payslip_count = len(payslips)
        if not payslips:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_WARNING, "no_eligible_payslips",
                _("No hay liquidaciones en estado %(states)s para «%(company)s» "
                  "en el período.", states=", ".join(states),
                  company=company.display_name)))

        rows, issues = adapter.generate_rows(
            self.env, company, date_from, date_to, payslips)
        dataset.issues.extend(issues)
        if not rows:
            return dataset

        for index, row in enumerate(rows, start=1):
            if len(row) != previred.FIELD_COUNT:
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "field_count",
                    _("La línea %(line)s que entregó el motor tiene "
                      "%(found)s campos y la especificación exige "
                      "%(expected)s.",
                      line=index, found=len(row),
                      expected=previred.FIELD_COUNT)))

        records, group_issues = self._group_rows(rows, adapter)
        dataset.issues.extend(group_issues)

        index = self._payslip_index(payslips)
        records = self._enforce_eligibility(records, index, dataset)

        positions = defaultdict(int)
        for record in records:
            key = previred.rut_key(record.rut + record.dv)
            entries = index.get(key) or []
            if not entries:
                continue
            position = positions[key]
            entry = entries[min(position, len(entries) - 1)]
            positions[key] += 1
            self._assign_department(record, entry, dataset)
            self._enrich_official_fields(record, entry["payslip"], dataset)

        dataset.records = records
        dataset.issues.extend(previred.validate_dataset(dataset))
        self._apply_scope(dataset, departments, allow_without_department)
        return dataset

    # -- agrupación de filas en trabajadores --------------------------------

    def _group_rows(self, rows, adapter):
        """Convierte filas planas en trabajadores con sus anexas.

        La especificación garantiza que una línea anexa va inmediatamente
        después de su principal, así que el agrupamiento es posicional: se
        abre un registro con cada línea principal y las siguientes se le
        adjuntan hasta la próxima. **No** se agrupa por RUT: un segundo
        contrato del mismo trabajador es una línea anexa, no una principal.
        """
        records = []
        issues = []
        current = None
        for index, row in enumerate(rows, start=1):
            if len(row) != previred.FIELD_COUNT:
                continue
            line_type = previred.normalize_line_type(
                row[previred.F_LINE_TYPE - 1])
            rut = (row[previred.F_RUT - 1] or "").strip()
            dv = (row[previred.F_DV - 1] or "").strip()

            if line_type == previred.LINE_PRINCIPAL or current is None:
                if line_type != previred.LINE_PRINCIPAL:
                    issues.append(previred.Issue(
                        previred.SEVERITY_ERROR, "orphan_annex",
                        _("La línea %(line)s es anexa (tipo %(type)s) pero no "
                          "hay ninguna línea principal antes; Previred no la "
                          "contabilizaría.", line=index, type=line_type)))
                current = previred.PreviredRecord(
                    rut=rut, dv=dv, principal=row)
                records.append(current)
                continue

            if not adapter.supports_annexes:
                issues.append(previred.Issue(
                    previred.SEVERITY_WARNING, "unexpected_annex",
                    _("El motor «%(engine)s» entregó una línea anexa en la "
                      "posición %(line)s pero no declara soportarlas.",
                      engine=adapter.label, line=index)))
            if previred.rut_key(rut + dv) != previred.rut_key(
                    current.rut + current.dv):
                issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "annex_rut_mismatch",
                    _("La línea anexa %(line)s pertenece a un RUT distinto "
                      "del de su línea principal.", line=index)))
            current.annexes.append(row)
        return records, issues

    # -- elegibilidad --------------------------------------------------------

    def _payslip_index(self, payslips):
        """`{clave RUT: datos}` de las liquidaciones elegibles.

        Se indexa por RUT porque es lo único que el archivo oficial lleva para
        identificar a la persona.
        """
        payslips.mapped("employee_id.identification_id")
        payslips.mapped("contract_id.department_id.name")
        payslips.mapped("employee_id.department_id.name")

        index = defaultdict(list)
        for payslip in payslips:
            identification = payslip.employee_id.identification_id
            if not identification:
                continue
            key = previred.rut_key(identification)
            department, origin = self._resolve_department(payslip)
            index[key].append({
                "department": department,
                "origin": origin,
                "employee_id": payslip.employee_id.id,
                "payslip_id": payslip.id,
                "company_id": payslip.company_id.id,
                "state": payslip.state,
                "payslip": payslip,
            })
        return dict(index)

    def _enforce_eligibility(self, records, index, dataset):
        """Descarta las filas que el motor emitió pero NO son exportables.

        Es la corrección de fondo sobre el generador de Blueminds, que no
        filtra por compañía ni por estado: aquí se comprueba que cada línea
        principal corresponda a una liquidación realmente elegible.
        """
        kept = []
        dropped_other = 0
        generated = Counter(previred.rut_key(r.rut + r.dv) for r in records)
        expected = {key: len(entries) for key, entries in index.items()}
        for key, count in generated.items():
            if key in expected and count != expected[key]:
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "ambiguous_engine_rows",
                    _("El motor generó %(generated)s línea(s) principal(es) "
                      "para un RUT con %(expected)s liquidación(es) elegible(s). "
                      "No es seguro decidir cuál corresponde; revise "
                      "duplicados, reliquidaciones o estados del período.",
                      generated=count, expected=expected[key])))
        for record in records:
            if previred.rut_key(record.rut + record.dv) in index:
                kept.append(record)
            else:
                dropped_other += 1
        if dropped_other:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_WARNING, "dropped_not_eligible",
                _("Se descartaron %(count)s trabajador(es) que el motor "
                  "entregó pero que no corresponden a una liquidación de esta "
                  "compañía en estado %(states)s.",
                  count=dropped_other,
                  states=", ".join(dataset.eligible_states))))
            dataset.dropped_count = dropped_other
        return kept

    # -- departamento --------------------------------------------------------

    def _resolve_department(self, payslip):
        """Precedencia documentada: contrato → liquidación → trabajador.

        Es la misma precedencia que usa el Libro de Remuneraciones, para que
        ambos informes agrupen exactamente igual. Se devuelve también el
        origen para poder advertir cuando no vino del contrato, que es la
        fuente que manda.
        """
        contract_department = payslip.contract_id.department_id
        if contract_department:
            return contract_department, "contract"
        payslip_department = getattr(payslip, "department_id", False)
        if payslip_department:
            return payslip_department, "payslip"
        employee_department = payslip.employee_id.department_id
        if employee_department:
            return employee_department, "employee"
        return self.env["hr.department"], "none"

    def _assign_department(self, record, entry, dataset):
        department = entry["department"]
        record.employee_id = entry["employee_id"]
        record.payslip_id = entry["payslip_id"]
        record.company_id = entry["company_id"]
        if department:
            record.department = department.name
            record.department_id = department.id
            # El código lleva el id de la compañía: dos departamentos con el
            # mismo nombre en compañías distintas no pueden colisionar en un
            # nombre de archivo.
            record.department_code = "%s_%s" % (
                previred.slugify_code(department.name, "DEPTO", 32),
                department.id,
            )
        else:
            record.department_code = previred.NO_DEPARTMENT_CODE

        if entry["origin"] == "payslip":
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_WARNING, "department_from_payslip",
                _("RUT %(rut)s-%(dv)s: el contrato no tiene departamento; se "
                  "usó el de la liquidación.", rut=record.rut, dv=record.dv),
                  record.department_label))
        elif entry["origin"] == "employee":
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_WARNING, "department_from_employee",
                _("RUT %(rut)s-%(dv)s: ni el contrato ni la liquidación "
                  "tienen departamento; se usó el del trabajador.",
                  rut=record.rut, dv=record.dv),
                record.department_label))

    def _enrich_official_fields(self, record, payslip, dataset):
        """Normaliza los campos que los motores antiguos no emiten en v98.

        Los montos usan la misma renta imponible AFP ya conciliada en el
        archivo del motor. No se recalcula la nómina ni se inventa una base.
        """
        for row in record.rows:
            if len(row) == previred.FIELD_COUNT:
                row[previred.F_LINE_TYPE - 1] = previred.normalize_line_type(
                    row[previred.F_LINE_TYPE - 1])
        if len(record.principal) != previred.FIELD_COUNT:
            return

        row = record.principal
        calendar = payslip.contract_id.resource_calendar_id
        weekly = getattr(calendar, "hours_per_week", 0.0) or getattr(
            calendar, "full_time_required_hours", 0.0) or 0.0
        # La configuración explícita del horario es la fuente oficial. La
        # heurística queda sólo como respaldo para datos históricos aún no
        # migrados.
        workday_type = getattr(calendar, "previred_workday_type", False)
        row[previred.F_WORKDAY_TYPE - 1] = (
            workday_type or ("2" if weekly and weekly <= 30 else "1")
        )

        # Campo 13: días efectivamente trabajados. Los generadores anteriores
        # sumaban todas las líneas y contaban licencias médicas, permisos y
        # ausencias como días trabajados. Si existe WORK100 se usa como fuente
        # canónica; en instalaciones que usan otro código se suman únicamente
        # líneas cuyo tipo de entrada NO sea ausencia.
        worked_lines = payslip.worked_days_line_ids.filtered(
            lambda line: line.number_of_days > 0
            and not line.work_entry_type_id.is_leave
        )
        attendance_lines = worked_lines.filtered(
            lambda line: line.work_entry_type_id.code == "WORK100"
        )
        source_lines = attendance_lines or worked_lines
        worked_days = sum(source_lines.mapped("number_of_days"))
        row[previred.F_WORKED_DAYS - 1] = str(int(Decimal(
            str(worked_days)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

        # Campo 105: centro de costo del contrato. En SimpleDigital el campo
        # visible como Centro de Costos es analytic_account_id; algunas bases
        # Blueminds usan cost_center_id. Se conserva esa precedencia y se usa
        # el nombre si el maestro no tiene código, evitando exportar vacío.
        contract = payslip.contract_id
        cost_center = getattr(contract, "analytic_account_id", False) or \
            getattr(contract, "cost_center_id", False)
        cost_center_value = ""
        if cost_center:
            cost_center_value = (getattr(cost_center, "code", False)
                                 or cost_center.name or "")
        row[previred.F_COST_CENTER - 1] = str(cost_center_value).strip()[:20]

        # Los tres campos anteriores existen tanto en el perfil histórico
        # v84 como en v98. Los campos de la reforma previsional que siguen sí
        # pertenecen exclusivamente al formato v98.
        if dataset.spec_version != "98":
            return

        afp_code = str(row[previred.F_AFP_CODE - 1] or "").strip()
        regime = str(row[previred.F_PENSION_REGIME - 1] or "").strip().upper()
        worker_type = str(row[previred.F_WORKER_TYPE - 1] or "").strip()
        taxable = str(row[previred.F_AFP_TAXABLE - 1] or "0").strip()
        taxable_amount = Decimal(taxable) if taxable.isdigit() else Decimal(0)
        if (regime != "AFP" or worker_type != "0" or not afp_code
                or afp_code in ("0", "00")):
            row[previred.F_LIFE_EXPECTANCY - 1] = "0"
            row[previred.F_PROTECTED_RETURN - 1] = "0"
            return

        def contribution(rate):
            return str(int((taxable_amount * Decimal(str(rate)) / 100)
                           .quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

        # El monto CEV calculado por nómina tiene precedencia porque puede
        # incorporar RIMA en licencias. Blueminds lo guarda como CEV y
        # SimpleDigital como EXP_VIDA. Sólo se usa la tasa legal de respaldo
        # si el motor antiguo no lo dejó ni en el archivo ni en la liquidación.
        current_life = str(row[previred.F_LIFE_EXPECTANCY - 1] or "").strip()
        if not current_life.isdigit() or int(current_life) == 0:
            lines = payslip.line_ids.filtered(
                lambda line: line.code in ("CEV", "EXP_VIDA"))
            payroll_life = sum(lines.mapped("total")) if lines else 0
            if payroll_life:
                row[previred.F_LIFE_EXPECTANCY - 1] = str(int(Decimal(
                    str(payroll_life)).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP)))
            else:
                row[previred.F_LIFE_EXPECTANCY - 1] = contribution(
                    previred.life_expectancy_rate(dataset.period))

        row[previred.F_PROTECTED_RETURN - 1] = contribution(
            previred.protected_return_rate(dataset.period))

    # -- alcance -------------------------------------------------------------

    def _apply_scope(self, dataset, departments, allow_without_department):
        """Filtra por departamento y aplica la política de «sin departamento».

        Por defecto un trabajador sin departamento **bloquea** la generación:
        repartir el archivo dejaría fuera a esa persona sin que nadie lo note.
        Sólo una opción explícita del asistente permite agruparlos aparte, y
        queda registrada en la auditoría.
        """
        orphans = dataset.without_department
        if orphans and not allow_without_department:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_ERROR, "without_department",
                _("%(count)s trabajador(es) no tienen departamento. Asigne el "
                  "departamento en su contrato, o marque «Permitir "
                  "trabajadores sin departamento» para agruparlos en un "
                  "archivo «%(label)s».",
                  count=len(orphans), label=previred.NO_DEPARTMENT_LABEL)))

        if departments:
            selected_ids = set(departments.ids)
            kept = []
            dropped = 0
            for record in dataset.records:
                if record.department_id in selected_ids:
                    kept.append(record)
                elif not record.department and allow_without_department:
                    kept.append(record)
                else:
                    dropped += 1
            dataset.records = kept
            if dropped:
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_WARNING, "scope_filtered",
                    _("%(count)s trabajador(es) quedaron fuera del archivo "
                      "por la selección de departamentos.", count=dropped)))

    # -- utilidades ----------------------------------------------------------

    @staticmethod
    def _company_vat(company):
        """RUT de la compañía para el nombre del archivo."""
        vat = company.vat or company.partner_id.vat or ""
        return previred.vat_code(vat)
