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

        result = adapter.generate_rows(
            self.env, company, date_from, date_to, payslips)
        # El contrato del adaptador admite `(rows, issues)` o, cuando el motor
        # puede correlacionar cada línea principal con su contrato de forma
        # determinística, `(rows, issues, row_meta)`. `row_meta` es una lista
        # paralela a las líneas **principales** en su orden de aparición; cada
        # entrada lleva `contract_id` y, opcionalmente, `payslip_id`. Ese dato
        # no toca ninguna de las 105 posiciones del TXT.
        if len(result) == 3:
            rows, issues, row_meta = result
        else:
            rows, issues = result
            row_meta = None
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
        self._attach_contract_meta(records, row_meta, dataset)

        index = self._payslip_index(payslips)
        records = self._enforce_eligibility(records, index, dataset)
        self._match_contracts(records, index, dataset)

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
        adjuntan hasta la próxima. **No** se agrupa por RUT: un trabajador con
        dos contratos elegibles en el mismo período tiene dos líneas
        principales (código `00`) y forma dos registros, cada uno con sus
        propias anexas. Las líneas 01/02/03 son anexas de su principal y no
        cuentan como contratos adicionales.
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

        La cantidad admitida de líneas principales por RUT es el número de
        **contratos** elegibles distintos de esa persona en la compañía y el
        período, no el de liquidaciones. Si el motor entrega más líneas
        principales que contratos elegibles, se bloquea la generación.
        """
        kept = []
        dropped_other = 0
        generated = Counter(previred.rut_key(r.rut + r.dv) for r in records)
        eligible_contracts = {
            key: {entry["payslip"].contract_id.id for entry in entries
                  if entry["payslip"].contract_id}
            for key, entries in index.items()
        }
        for key, count in generated.items():
            if key not in eligible_contracts:
                continue
            allowed = len(eligible_contracts[key]) or len(index[key])
            if count > allowed:
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "too_many_principal_lines",
                    _("El motor generó %(generated)s línea(s) principal(es) "
                      "para un RUT con sólo %(allowed)s contrato(s) "
                      "elegible(s) en la compañía y el período. Revise "
                      "duplicados, reliquidaciones o estados.",
                      generated=count, allowed=allowed)))
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

    # -- correlación línea principal ↔ contrato -----------------------------

    def _attach_contract_meta(self, records, row_meta, dataset):
        """Adjunta a cada registro el `contract_id` que declaró el motor.

        `row_meta` viene del bridge y es paralelo a las líneas **principales**
        en su orden de aparición. Si el motor no lo entrega, no se hace nada:
        la unicidad caerá al respaldo por compañía + período + RUT.
        """
        if not row_meta:
            return
        if len(row_meta) != len(records):
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_ERROR, "engine_meta_mismatch",
                _("El motor entregó %(meta)s descriptor(es) de contrato para "
                  "%(rows)s línea(s) principal(es). No es seguro asociarlos.",
                  meta=len(row_meta), rows=len(records))))
            return
        for record, meta in zip(records, row_meta):
            contract_id = (meta or {}).get("contract_id")
            record.contract_id = contract_id or None

    def _match_contracts(self, records, index, dataset):
        """Empareja cada línea principal con una liquidación elegible.

        Cuando el motor entregó `contract_id`, el emparejamiento es por
        contrato y es determinístico. Sin esa metadata se mantiene el
        emparejamiento posicional anterior, **pero sólo si no es ambiguo**:
        si un RUT tiene varias líneas principales y varias liquidaciones
        elegibles y no hay forma segura de aparearlas, se bloquea con un
        error explícito en vez de asignar por posición en silencio.
        """
        grouped = defaultdict(list)
        for record in records:
            grouped[previred.rut_key(record.rut + record.dv)].append(record)

        for key, group in grouped.items():
            entries = list(index.get(key) or [])
            if not entries:
                continue
            used = set()
            for record in group:
                entry = None
                if record.contract_id is not None:
                    for position, candidate in enumerate(entries):
                        if position in used:
                            continue
                        contract = candidate["payslip"].contract_id
                        if contract and contract.id == record.contract_id:
                            entry = candidate
                            used.add(position)
                            break
                if entry is None:
                    free = [p for p in range(len(entries)) if p not in used]
                    ambiguous = len(group) > 1 and len(free) > 1
                    if ambiguous:
                        dataset.issues.append(previred.Issue(
                            previred.SEVERITY_ERROR,
                            "ambiguous_contract_correlation",
                            _("RUT %(rut)s-%(dv)s: hay varias líneas "
                              "principales y varias liquidaciones elegibles y "
                              "el motor no entregó el contrato de cada línea. "
                              "No se asigna por posición; corrija el motor o "
                              "los datos del período.",
                              rut=record.rut, dv=record.dv)))
                        continue
                    position = free[0] if free else len(entries) - 1
                    entry = entries[position]
                    used.add(position)
                if record.contract_id is None and entry["payslip"].contract_id:
                    record.contract_id = entry["payslip"].contract_id.id
                self._assign_department(record, entry, dataset)
                self._enrich_official_fields(record, entry["payslip"], dataset)

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
        # «Horas de la semana» = campo «Tiempo completo de la empresa» del
        # horario (`full_time_required_hours`). Previred valida el sueldo
        # mínimo del campo 27 contra el tipo de jornada del campo 93: una
        # jornada semanal **inferior a 40 h** es parcial (tipo 2) y admite
        # una renta imponible bajo el mínimo legal; 40 h o más es completa
        # (tipo 1) y exige el mínimo. Ticket EMCA agosto 2026, RUT
        # 12588103-3: calendario «Jornada parcial 24 horas» (24 h en «Tiempo
        # completo de la empresa»), rechazado porque salía como tipo 1.
        weekly = getattr(calendar, "full_time_required_hours", 0.0) or getattr(
            calendar, "hours_per_week", 0.0) or 0.0
        # La configuración explícita del horario es la fuente oficial. La
        # heurística por horas queda sólo como respaldo para datos históricos
        # aún no migrados.
        workday_type = getattr(calendar, "previred_workday_type", False)
        workday_type = (
            workday_type or ("2" if weekly and weekly < 40 else "1")
        )
        # Previred exige que el campo 93 de cada línea anexa 01/02/03 sea
        # idéntico al de la línea principal 00 del trabajador. Algunos
        # motores recalculan este valor por línea y pueden entregar, por
        # ejemplo, 00=1 y 01=2. La jornada pertenece al contrato, por lo que
        # se normaliza una vez y se propaga al bloque completo.
        for record_row in record.rows:
            if len(record_row) == previred.FIELD_COUNT:
                record_row[previred.F_WORKDAY_TYPE - 1] = workday_type

        self._set_worked_days(record, payslip, dataset)

        # Campo 105: centro de costo del contrato. En SimpleDigital el campo
        # visible como Centro de Costos es analytic_account_id; algunas bases
        # Blueminds usan cost_center_id. Se conserva esa precedencia y se usa
        # el nombre si el maestro no tiene código, evitando exportar vacío.
        # Se translitera a ASCII (ver `previred.strip_accents`): un nombre con
        # tilde («Administración») se codifica en UTF-8 y Previred lo relee
        # como Latin-1, mostrando «AdministraciÃ³n» y rechazando la línea por
        # «Error de formato en el campo Centro de Costos» (ticket PreviRed
        # 2026-08, Agrícola Los Lingues y Megafrut).
        contract = payslip.contract_id
        cost_center = getattr(contract, "analytic_account_id", False) or \
            getattr(contract, "cost_center_id", False)
        cost_center_value = ""
        if cost_center:
            cost_center_value = (getattr(cost_center, "code", False)
                                 or cost_center.name or "")
        cost_center_value = previred.strip_accents(
            str(cost_center_value).strip())
        row[previred.F_COST_CENTER - 1] = cost_center_value[:20]

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

        self._set_medical_leave_bases(record, payslip, dataset)

    # -- licencia médica: base imponible + RIMA --------------------------

    def _set_medical_leave_bases(self, record, payslip, dataset):
        """Rebasa las cotizaciones de cargo del empleador sobre imponible + RIMA.

        Regla funcional (tickets S&S 2026-09, Somed / Carolina Medel y
        Servicio de Bienestar / Valentina Parada; valores confirmados por el
        cliente en las respuestas del 2026-09-08):

        * En licencia médica la base de las cotizaciones de cargo del
          empleador es **Renta Imponible AFP del mes (campo 27) + RIMA
          (campo 92)**. Sobre esa base se recalculan con la tasa estatutaria:
          SIS (29), Acc. Trabajo ISL (71, sólo si la línea usa ISL y no
          mutual), Expectativa de Vida (94), Rentabilidad Protegida (95),
          Renta Imponible Seguro Cesantía (100) y Aporte Empleador Seguro
          Cesantía (102).
        * **No** se tocan la cotización adicional AFP del campo 28 (va sólo
          sobre el imponible del mes) ni la mutualidad (campos 97 / 98), que
          no suma RIMA (usuario, 2026-09-08, conflicto tickets #13 vs #15).
        * Sólo actúa cuando el motor **ya informó la RIMA** en el campo 92.
          Cuando el mes es de licencia completa y el motor no la informó,
          deja un aviso trazable y no recalcula: el cálculo de la RIMA
          (sueldo base + gratificación con tope IMM, o liquidación previa) es
          el «corte 2» especificado en
          `docs/PREVIRED_TICKET_LICENCIA_JORNADA_2026-09.md`.

        MUEVE MONTOS DECLARADOS A PREVIRED. Cada override deja un hallazgo
        auditable; requiere validación funcional contra datos reales antes de
        aplicarse en SyS.
        """
        if dataset.spec_version != "98":
            return
        row = record.principal
        if len(row) != previred.FIELD_COUNT:
            return

        regime = str(row[previred.F_PENSION_REGIME - 1] or "").strip().upper()
        worker_type = str(row[previred.F_WORKER_TYPE - 1] or "").strip()
        afp_code = str(row[previred.F_AFP_CODE - 1] or "").strip()
        if (regime != "AFP" or worker_type != "0" or not afp_code
                or afp_code in ("0", "00")):
            return

        def _int(position):
            raw = str(row[position - 1] or "0").strip()
            return int(raw) if raw.lstrip("-").isdigit() else 0

        worked = str(row[previred.F_WORKED_DAYS - 1] or "").strip()
        full_month_leave = worked.isdigit() and int(worked) == 0
        rima = _int(previred.F_RIMA)
        if rima <= 0:
            if full_month_leave:
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_WARNING, "medical_leave_rima_missing",
                    _("RUT %(rut)s-%(dv)s: mes completo de licencia médica y "
                      "el motor no informó la RIMA (campo 92). Los campos 29, "
                      "71, 94, 95, 100 y 102 no se recalcularon; requiere el "
                      "cálculo de RIMA del corte 2.",
                      rut=record.rut, dv=record.dv),
                    record.department_label))
            return

        taxable = _int(previred.F_AFP_TAXABLE)
        base = taxable + rima
        fixed_term = bool(getattr(payslip.contract_id, "date_end", False))

        def _contribution(rate):
            return str(int((Decimal(base) * Decimal(str(rate)) / 100)
                           .quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

        changes = []

        def _set(position, value):
            value = str(value)
            old = str(row[position - 1] or "").strip()
            if old != value:
                changes.append("%s: %s → %s" % (
                    previred.field_label(position), old or "0", value))
            row[position - 1] = value

        _set(previred.F_SIS_CONTRIBUTION,
             _contribution(previred.sis_rate(dataset.period)))
        _set(previred.F_LIFE_EXPECTANCY,
             _contribution(previred.life_expectancy_rate(dataset.period)))
        _set(previred.F_PROTECTED_RETURN,
             _contribution(previred.protected_return_rate(dataset.period)))
        _set(previred.F_UNEMPLOYMENT_TAXABLE, base)
        _set(previred.F_UNEMPLOYMENT_EMPLOYER,
             _contribution(previred.unemployment_employer_rate(
                 dataset.period, fixed_term)))

        mutual_code = str(row[previred.F_MUTUAL_CODE - 1] or "").strip()
        uses_mutual = mutual_code not in ("", "0", "00")
        if not uses_mutual and _int(previred.F_ISL_ACCIDENT) > 0:
            _set(previred.F_ISL_ACCIDENT,
                 _contribution(previred.isl_accident_rate(dataset.period)))

        if changes:
            dataset.issues.append(previred.Issue(
                previred.SEVERITY_WARNING, "medical_leave_bases_rebased",
                _("RUT %(rut)s-%(dv)s: licencia médica; cotizaciones de cargo "
                  "del empleador recalculadas sobre imponible %(taxable)s + "
                  "RIMA %(rima)s = %(base)s. %(detail)s. MUEVE MONTOS "
                  "DECLARADOS: validar antes de SyS.",
                  rut=record.rut, dv=record.dv, taxable=taxable, rima=rima,
                  base=base, detail="; ".join(changes)),
                record.department_label))

    # -- campo 13 «Días Trabajados» ---------------------------------------

    @staticmethod
    def _payslip_ref(payslip):
        """Referencia segura de una liquidación para los mensajes de error.

        Usa el número de documento (`SLIP/491`), que no lleva datos
        personales; si no lo tiene, el id interno.
        """
        return payslip.number or ("#%s" % payslip.id)

    def _set_worked_days(self, record, payslip, dataset):
        """Fija el campo 13 desde la línea de asistencia de la liquidación.

        Regla (documento funcional, corrección 1):

        * La fuente es la línea de días trabajados cuyo tipo de entrada es
          «Asistencia»: se prefiere el código técnico estable
          `WORK100`; si la instalación no lo usa, se acepta una línea cuyo
          Tipo **y** Descripción sean ambos «Asistencia» (normalizados).
        * Se suman **sólo** esas líneas. «Fuera de contrato», licencias,
          permisos, ausencias y vacaciones quedan excluidos siempre. Se
          elimina el respaldo genérico que sumaba toda línea no marcada como
          ausencia (podía incluir «Fuera de contrato» y dar un valor falso).
        * El formato oficial es entero: `6.00` se exporta como `6`. Una
          fracción no representable no se trunca en silencio: se informa un
          error auditable.
        * El mes previsional Previred es de 30 días: la especificación exige
          `0 =< días =< 30` y el propio generador del proveedor acota con
          `min(30, …)`. Si la suma de asistencia supera 30 (p. ej. un mes
          calendario de 31 días) se acota a 30 y queda una advertencia; no es
          pérdida de dato sino el modelo de 30 días del formato.
        * Si todas las líneas con días son ausencias (p. ej. licencia médica
          todo el mes), el campo 13 es `0`: la persona trabajó 0 días.
        * Si hay días en líneas que no son ausencia ni asistencia (p. ej.
          «Fuera de contrato») y ninguna de asistencia, no se inventa un valor
          (ni días calendario, ni el rango de la liquidación, ni
          «30 − ausencias»): se informa un error preciso que identifica la
          liquidación y las líneas conflictivas.
        * El valor resultante se escribe en **todas** las filas del registro
          (principal y anexas): Previred exige el campo 13 en cada línea y
          las anexas son del mismo trabajador y período.
        """
        worked_days_lines = payslip.worked_days_line_ids
        attendance = worked_days_lines.filtered(
            lambda line: (line.work_entry_type_id.code or "")
            in previred.ATTENDANCE_CODES and (line.number_of_days or 0) > 0)
        if not attendance:
            attendance = worked_days_lines.filtered(
                lambda line: previred.is_attendance_label(
                    line.work_entry_type_id.name, line.name)
                and (line.number_of_days or 0) > 0)

        current = str(record.principal[previred.F_WORKED_DAYS - 1] or "").strip()
        value = None
        if attendance:
            total = sum(attendance.mapped("number_of_days"))
            amount = Decimal(str(total))
            if amount != amount.to_integral_value():
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "worked_days_fraction",
                    _("RUT %(rut)s-%(dv)s: los días de asistencia de la "
                      "liquidación %(slip)s son %(value)s y el campo 13 "
                      "oficial exige un entero. Revise la línea de asistencia.",
                      rut=record.rut, dv=record.dv,
                      slip=self._payslip_ref(payslip), value=total)))
            else:
                days = int(amount.quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP))
                if days > 30:
                    dataset.issues.append(previred.Issue(
                        previred.SEVERITY_WARNING, "worked_days_capped",
                        _("RUT %(rut)s-%(dv)s: la asistencia de la liquidación "
                          "%(slip)s suma %(days)s días; el mes previsional "
                          "Previred es de 30 y el campo 13 se acota a 30.",
                          rut=record.rut, dv=record.dv,
                          slip=self._payslip_ref(payslip), days=days)))
                    days = 30
                value = str(days)
        elif worked_days_lines:
            non_leave = worked_days_lines.filtered(
                lambda line: not line.work_entry_type_id.is_leave
                and (line.number_of_days or 0) > 0)
            if not non_leave:
                # Todas las líneas con días son ausencias (p. ej. licencia
                # médica todo el mes): 0 días trabajados es el valor correcto,
                # no una fuente faltante.
                value = "0"
            else:
                # Hay líneas con días que no son ausencia ni asistencia (p. ej.
                # «Fuera de contrato»): no se deduce el campo 13 de ellas ni de
                # ninguna otra fuente. Se bloquea con un error trazable.
                dataset.issues.append(previred.Issue(
                    previred.SEVERITY_ERROR, "worked_days_source_missing",
                    _("RUT %(rut)s-%(dv)s: la liquidación %(slip)s tiene días "
                      "en líneas que no son de asistencia (%(lines)s) y "
                      "ninguna línea de asistencia (código %(code)s, o Tipo y "
                      "Descripción «Asistencia») de la que tomar el campo 13.",
                      rut=record.rut, dv=record.dv,
                      slip=self._payslip_ref(payslip),
                      lines=", ".join(sorted(set(
                          non_leave.mapped("work_entry_type_id.name")))),
                      code="/".join(previred.ATTENDANCE_CODES))))

        if value is None:
            # Sin fuente canónica: se conserva lo que entregó el motor (en el
            # motor Blueminds y en las bases de prueba suele ser un valor
            # válido). Si viene vacío, `validate_row` lo marcará como campo
            # obligatorio faltante y el error anterior explica la causa real.
            value = current

        for row in record.rows:
            if len(row) == previred.FIELD_COUNT:
                row[previred.F_WORKED_DAYS - 1] = value

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
