"""Calculate existing draft slips through OCA, without generating their data."""
from datetime import datetime, time, timedelta

import pytz
from psycopg2 import sql

from odoo import _, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


def _read(records, names):
    records.check_access("read")
    records.check_field_access_rights("read", names)
    return records


def _lock(records, mode="UPDATE"):
    _read(records, ["id"])
    if not records:
        return
    records.env.cr.execute(sql.SQL("SELECT id FROM {} WHERE id=ANY(%s) ORDER BY id FOR " + mode).format(
        sql.Identifier(records._table)), (records.ids,))
    if {row[0] for row in records.env.cr.fetchall()} != set(records.ids):
        raise UserError(_("Original payroll references changed while opening the batch."))
    # Another transaction may have committed before this lock was acquired.
    # Subsequent qualification must not use values cached before the lock.
    records.invalidate_recordset()


def _children(parent, model_name, inverse):
    model = parent.env[model_name].with_context(active_test=False)
    names = [name for name, field in model._fields.items() if field.store and field.column_type]
    _read(model, names)
    model.flush_model([inverse])
    parent.env.cr.execute(sql.SQL("SELECT id FROM {} WHERE {}=ANY(%s) ORDER BY id").format(
        sql.Identifier(model._table), sql.Identifier(inverse)), (parent.ids,))
    records = model.browse([row[0] for row in parent.env.cr.fetchall()])
    _read(records, names)
    _lock(records)
    return records


def _stored(records):
    """Private comparison only, after complete stored-field authorization."""
    names = [name for name, field in records._fields.items() if field.store and field.column_type]
    _read(records, names)
    records.flush_recordset(names)
    records.env.cr.execute(sql.SQL("SELECT id,to_jsonb(r) FROM {} r WHERE id=ANY(%s) ORDER BY id").format(
        sql.Identifier(records._table)), (records.ids,))
    return records.env.cr.fetchall()


def _lock_relation(records, name):
    _read(records, [name])
    field = records._fields[name]
    records.flush_recordset([name])
    records.env.cr.execute(sql.SQL("SELECT {},{} FROM {} WHERE {}=ANY(%s) ORDER BY {},{} FOR SHARE").format(
        sql.Identifier(field.column1), sql.Identifier(field.column2), sql.Identifier(field.relation),
        sql.Identifier(field.column1), sql.Identifier(field.column1), sql.Identifier(field.column2)), (records.ids,))
    return records.env.cr.fetchall()


def _bounds(contract, first, last):
    _read(contract, ["resource_calendar_id"])
    calendar = _read(contract.resource_calendar_id, ["tz", "hours_per_day"])
    if not calendar or not calendar.tz or calendar.hours_per_day <= 0:
        raise UserError(_("Existing batch payroll requires the original calendar and positive daily hours."))
    try:
        zone = pytz.timezone(calendar.tz)
    except pytz.UnknownTimeZoneError:
        raise UserError(_("The original payroll calendar timezone is invalid.")) from None
    result = []
    for day in (first, last + timedelta(days=1)):
        value = datetime.combine(day, time.min)
        for minute in range(24 * 60 + 1):
            try:
                boundary = zone.localize(value, is_dst=None)
                break
            except pytz.AmbiguousTimeError:
                boundary = min(zone.localize(value, is_dst=flag) for flag in (True, False))
                break
            except pytz.NonExistentTimeError:
                value += timedelta(minutes=1)
        else:
            raise UserError(_("The original payroll period contains a nonexistent local date."))
        result.append(boundary.astimezone(pytz.UTC).replace(tzinfo=None))
    return tuple(result)


class PayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def _step_existing_batch_preflight(self):
        normal = self.sudo(False).with_context(active_test=False)
        normal.ensure_one()
        if type(normal.id) is not int or normal.id <= 0:
            raise UserError(_("Open an existing saved payroll batch before calculating its drafts."))
        if not normal.env.user.has_group("payroll.group_payroll_manager"):
            raise AccessError(_("Calculating saved batch drafts requires the payroll manager."))
        normal.env.cr.execute("""SELECT name FROM ir_module_module WHERE name IN ('payroll','hr_payroll')
            AND state IN ('installed','to upgrade','to install','to remove')""")
        if {row[0] for row in normal.env.cr.fetchall()} != {"payroll"}:
            raise UserError(_("Saved draft batch calculation requires the actual OCA payroll engine."))
        run_fields = ["state", "slip_ids", "date_start", "date_end", "struct_id", "credit_note"]
        if "company_id" in normal._fields:
            run_fields.append("company_id")
        _read(normal, run_fields)
        normal.check_access("write")
        _lock(normal)
        normal.invalidate_recordset(run_fields)
        if normal.state != "draft" or not normal.date_start or not normal.date_end or normal.date_start > normal.date_end:
            raise UserError(_("Select an open saved payroll batch with a valid period."))
        slips = _children(normal, "hr.payslip", "payslip_run_id")
        slips.check_access("write")
        if not slips or any(slip.state != "draft" or slip.paid or slip.step_history_locked for slip in slips):
            raise UserError(_("Only existing draft slips may be calculated; validated or paid history is excluded."))
        company = normal.company_id if "company_id" in normal._fields else slips.company_id
        _read(company, ["country_id"])
        if len(company) != 1 or company != normal.env.company or any(slip.company_id != company for slip in slips):
            raise UserError(_("Select the original batch company before calculating saved drafts."))
        if any(slip.date_from != normal.date_start or slip.date_to != normal.date_end
                or slip.credit_note != normal.credit_note for slip in slips):
            raise UserError(_("Every saved draft must retain the batch period and refund policy."))
        contracts = _read(slips.contract_id, ["employee_id", "company_id", "state", "date_start", "date_end",
            "struct_id", "structure_type_id", "schedule_pay", "wage_type", "resource_calendar_id"])
        _lock(_read(slips.employee_id, ["company_id", "active"]))
        _lock(contracts)
        contract_fields = ["employee_id", "state", "date_start", "date_end"]
        if "active" in contracts._fields:
            contract_fields.append("active")
        contracts.flush_model(contract_fields)
        for slip in slips:
            contract = slip.contract_id
            if (not contract or not slip.employee_id.active or slip.employee_id.company_id != company
                    or contract.employee_id != slip.employee_id or contract.company_id != company
                    or contract.state != "open" or not contract.date_start or contract.date_start > normal.date_start
                    or (contract.date_end and contract.date_end < normal.date_end)):
                raise UserError(_("Saved batch drafts require their original active full-period contracts and employees."))
            if contract.schedule_pay != "monthly" or contract.wage_type != "monthly":
                raise UserError(_("Saved batch drafts support the audited monthly contract policy only."))
            active = " AND active" if "active" in contracts._fields else ""
            normal.env.cr.execute("""SELECT id FROM hr_contract WHERE employee_id=%s AND state='open'
                AND date_start<=%s AND (date_end IS NULL OR date_end>=%s)""" + active,
                (slip.employee_id.id, normal.date_end, normal.date_start))
            candidates = contracts.browse([row[0] for row in normal.env.cr.fetchall()])
            _read(candidates, contract_fields)
            if set(candidates.ids) != set(contract.ids):
                raise UserError(_("The saved payroll period requires one unambiguous original active contract."))
            if not slip.struct_id or (normal.struct_id and slip.struct_id != normal.struct_id):
                raise UserError(_("Select the original explicit payroll structure on every saved draft."))
        if "step_payroll_migration_review" in contracts._fields:
            _read(contracts, ["step_payroll_migration_review"])
            if any(contracts.mapped("step_payroll_migration_review")):
                raise UserError(_("Confirm the original contract payroll review before calculating saved drafts."))
        structures = normal.env["hr.payroll.structure"]
        rules = normal.env["hr.salary.rule"]
        for slip in slips:
            for root in slip._step_selected_payroll_structures():
                scope = root._step_effective_rule_scope()
                structures |= scope["structures"]
                rules |= scope["rules"]
        _read(structures, ["use_work_entries", "type_id", "unpaid_work_entry_type_ids"])
        if "step_legacy_payroll" in structures._fields:
            _read(structures, ["step_legacy_payroll"])
            if any(structures.mapped("step_legacy_payroll")):
                raise UserError(_("Historical payroll structures cannot be calculated from saved drafts."))
        if any(not slip.struct_id.use_work_entries for slip in slips):
            raise UserError(_("Saved batch drafts require the real work-entry payroll policy."))
        # Parent locks cover new FK children. Existing child locks cover edits
        # and removals. No contract, entry, input or worked-day row is created.
        inputs = _children(slips, "hr.payslip.input", "payslip_id")
        days = _children(slips, "hr.payslip.worked_days", "payslip_id")
        lines = _children(slips, "hr.payslip.line", "slip_id")
        entries = normal.env["hr.work.entry"].with_context(active_test=False)
        entry_fields = ["contract_id", "employee_id", "company_id", "date_start", "date_stop", "state", "active", "work_entry_type_id", "duration"]
        _read(entries, entry_fields)
        entries.flush_model(entry_fields)
        for slip in slips:
            first, last = _bounds(slip.contract_id, normal.date_start, normal.date_end)
            normal.env.cr.execute("""SELECT id FROM hr_work_entry WHERE contract_id=%s AND active
                AND state!='cancelled' AND date_start<%s AND date_stop>%s ORDER BY id""", (slip.contract_id.id, last, first))
            entries |= entries.browse([row[0] for row in normal.env.cr.fetchall()])
        _read(entries, entry_fields)
        _lock(entries)
        _read(contracts.structure_type_id, ["default_work_entry_type_id", "default_schedule_pay", "wage_type"])
        kinds = entries.work_entry_type_id | days.work_entry_type_id | contracts.structure_type_id.default_work_entry_type_id
        _read(kinds, ["code", "name", "sequence", "round_days", "round_days_type", "unpaid_structure_ids", "country_id"])
        if any(kind.country_id and kind.country_id != company.country_id for kind in kinds):
            raise UserError(_("Every original work-entry type must match the batch company country or be shared."))
        # UPDATE locks on actual configuration parents also exclude new FK
        # memberships. SHARE locks on their current M2M rows exclude removals.
        # None of these locks assigns or changes a business field.
        for records in (structures, rules, kinds, contracts.structure_type_id, contracts.resource_calendar_id, inputs.input_type_id):
            _lock(records)
        for name in ("rule_ids", "unpaid_work_entry_type_ids", "input_line_type_ids"):
            _lock_relation(structures, name)
        _lock_relation(inputs.input_type_id, "struct_ids")
        _children(rules, rules._fields["input_ids"].comodel_name, rules._fields["input_ids"].inverse_name)
        _read(rules, [name for name, field in rules._fields.items() if field.store and field.column_type])
        _read(structures, ["name"])
        # Recheck the entire hierarchy after locking its initially selected
        # parents. A concurrently changed graph is never accepted partially.
        locked_structures, locked_rules = set(structures.ids), set(rules.ids)
        checked_structures, checked_rules = set(), set()
        for slip in slips:
            for root in slip._step_selected_payroll_structures():
                scope = root._step_effective_rule_scope()
                checked_structures.update(scope["structures"].ids)
                checked_rules.update(scope["rules"].ids)
        if checked_structures != locked_structures or checked_rules != locked_rules:
            raise UserError(_("Original payroll configuration changed while locking the saved batch; reopen it."))
        current_types = entries.work_entry_type_id | days.work_entry_type_id | contracts.structure_type_id.default_work_entry_type_id
        if set(current_types.ids) != set(kinds.ids):
            raise UserError(_("Original work-entry type policy changed while locking the saved batch; reopen it."))
        for slip in slips:
            own = entries.filtered(lambda entry: entry.contract_id == slip.contract_id)
            if not own or any(entry.state not in ("draft", "validated") or not entry.work_entry_type_id
                    or entry.employee_id != slip.employee_id or entry.company_id != company for entry in own):
                raise UserError(_("Resolve actual work-entry conflicts and identities before calculating the saved batch."))
            ordered = own.sorted(lambda entry: (entry.date_start, entry.id))
            if any(left.date_start < right.date_stop and right.date_start < left.date_stop
                    for index, left in enumerate(ordered) for right in ordered[index + 1:]):
                raise UserError(_("Resolve overlapping actual work entries before calculating the saved batch."))
            slip._step_check_saved_input_values()
            slip._step_check_original_configuration(operation="calculate")
            if structures.filtered(lambda structure: structure.name == "Nómina Chile"):
                _read(slip.contract_id, [name for name in ("contract_type_id", "analytic_account_id", "health_institution",
                    "pension_option", "income_tax_type", "work_schedule_id") if name in slip.contract_id._fields])
                _read(slip.employee_id, [name for name in ("hr_commune", "identification_id", "country_id", "birthday", "gender")
                    if name in slip.employee_id._fields])
            if hasattr(slip, "_step_check_country_calculation_configuration"):
                slip._step_check_country_calculation_configuration()
            elif structures.filtered(lambda structure: structure.name == "Nómina Chile"):
                raise UserError(_("Load the original Chile payroll calculation admission before processing this batch."))
            actual = slip.with_context(active_test=True)._get_worked_day_lines()
            saved = days.filtered(lambda day: day.payslip_id == slip)
            by_type = {row["work_entry_type_id"]: row for row in actual}
            if (len(by_type) != len(actual) or len(saved.work_entry_type_id) != len(saved)
                    or set(saved.work_entry_type_id.ids) != set(by_type)):
                raise UserError(_("Save the complete original typed worked days before calculating the batch; no days are generated here."))
            for day in saved:
                row = by_type[day.work_entry_type_id.id]
                if (day.contract_id != slip.contract_id or day.code != row["code"]
                        or float_compare(day.number_of_days, row["number_of_days"], precision_digits=5)
                        or float_compare(day.number_of_hours, row["number_of_hours"], precision_digits=5)):
                    raise UserError(_("Saved worked days must match the real original period entries before batch calculation."))
        return slips, inputs, days, entries

    def action_step_compute_existing_drafts(self):
        """All admission precedes the first real OCA calculation."""
        normal = self.sudo(False).with_context(active_test=False)
        with normal.env.cr.savepoint():
            slips, inputs, days, entries = normal._step_existing_batch_preflight()
            before_inputs, before_days, before_entries = _stored(inputs), _stored(days), _stored(entries)
            numbers = {slip.id: slip.number for slip in slips}
            slips.with_context(active_test=True).compute_sheet()
            if (set(_children(normal, "hr.payslip", "payslip_run_id").ids) != set(slips.ids)
                    or set(_children(slips, "hr.payslip.input", "payslip_id").ids) != set(inputs.ids)
                    or set(_children(slips, "hr.payslip.worked_days", "payslip_id").ids) != set(days.ids)
                    or _stored(inputs) != before_inputs or _stored(entries) != before_entries):
                raise UserError(_("The provider changed original saved payroll rows during batch calculation."))
            # OCA refreshes existing draft day metadata with the same actual
            # values. Ignore only ordinary write audit timestamps on those rows.
            stable = lambda rows: [(ident, {key: value for key, value in values.items() if key not in ("write_uid", "write_date")})
                for ident, values in rows]
            if stable(_stored(days)) != stable(before_days) or any(number and slips.browse(ident).number != number for ident, number in numbers.items()):
                raise UserError(_("The provider changed original saved worked-day values or assigned payroll references."))
        return {"type": "ir.actions.act_window", "res_model": "hr.payslip.run", "res_id": normal.id,
            "view_mode": "form", "target": "current"}
