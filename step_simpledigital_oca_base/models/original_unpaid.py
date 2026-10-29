"""The original unpaid relation, shared by structures and real work-entry types."""
from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError

from odoo.addons.step_payroll_contracts.history import history_protected


RELATION = "hr_payroll_structure_hr_work_entry_type_rel"


def _normal(records):
    # Stored computations normally receive compute_sudo=True. Keep the actual
    # uid and context while restoring ordinary field and record permissions.
    return records.with_env(api.Environment(records.env.cr, records.env.uid, dict(records.env.context), su=False))


def _command_ids(commands):
    result = set()
    for command in commands or ():
        if isinstance(command, int):
            result.add(command)
        elif isinstance(command, (tuple, list)) and command:
            if command[0] in (1, 2, 3, 4) and len(command) > 1 and command[1]:
                result.add(command[1])
            elif command[0] == 6 and len(command) > 2:
                result.update(command[2])
    return result


def _policy_component(env, structure_ids=(), type_ids=(), validate=False, company=None):
    """Read every original endpoint, including hidden/archived neighbours.

    Raw IDs detect omission; every endpoint and field still needs ordinary
    access. Before editing, only visibility is required so a visible invalid
    country relationship can be removed. After editing, remaining pairs must
    have compatible explicit scope. A global structure is never given an owner.
    """
    structures_model = _normal(env["hr.payroll.structure"]).with_context(active_test=False)
    types_model = structures_model.env["hr.work.entry.type"].with_context(active_test=False)
    structures_model.flush_model(["unpaid_work_entry_type_ids", "company_id", "country_id"])
    types_model.flush_model(["unpaid_structure_ids", "country_id"])
    structure_ids, type_ids = set(structure_ids), set(type_ids)
    pairs = set()
    while True:
        env.cr.execute("""SELECT hr_payroll_structure_id,hr_work_entry_type_id
            FROM hr_payroll_structure_hr_work_entry_type_rel
            WHERE hr_payroll_structure_id=ANY(%s) OR hr_work_entry_type_id=ANY(%s)""",
            (sorted(structure_ids), sorted(type_ids)))
        found = set(env.cr.fetchall())
        all_structures = structure_ids | {row[0] for row in found}
        all_types = type_ids | {row[1] for row in found}
        pairs |= found
        if (all_structures, all_types) == (structure_ids, type_ids):
            break
        structure_ids, type_ids = all_structures, all_types
    structures = structures_model.browse(sorted(structure_ids))
    types = types_model.browse(sorted(type_ids))
    if structures:
        structures.check_access("read")
        structures.check_field_access_rights("read", ["unpaid_work_entry_type_ids", "company_id", "country_id"])
    if types:
        types.check_access("read")
        types.check_field_access_rights("read", ["unpaid_structure_ids", "country_id"])
    if set(structures.exists().ids) != structure_ids or set(types.exists().ids) != type_ids:
        raise UserError(_("Select existing original payroll unpaid-policy references."))
    if validate:
        by_structure = {record.id: record for record in structures}
        by_type = {record.id: record for record in types}
        if company:
            company = company.with_env(structures.env)
            company.check_access("read")
            company.check_field_access_rights("read", ["country_id"])
        for structure_id, type_id in pairs:
            structure, kind = by_structure[structure_id], by_type[type_id]
            structure.company_id.check_access("read")
            structure.company_id.check_field_access_rights("read", ["country_id"])
            country = structure.country_id or structure.company_id.country_id
            # Only actual processing supplies its real payslip company. Setup
            # deliberately leaves a country-less global structure unresolved.
            country = country or (company.country_id if company else False)
            if kind.country_id and country and kind.country_id != country:
                raise UserError(_("Original unpaid payroll policy crosses country boundaries."))
    return {"structures": structures, "types": types, "pairs": pairs}


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    unpaid_work_entry_type_ids = fields.Many2many(
        "hr.work.entry.type", RELATION, "hr_payroll_structure_id", "hr_work_entry_type_id", copy=True,
        string="Unpaid Work Entry Types")

    @api.model_create_multi
    def create(self, vals_list):
        planned = set().union(*(_command_ids(vals.get("unpaid_work_entry_type_ids")) for vals in vals_list))
        if planned:
            _policy_component(self.env, type_ids=planned)
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            _policy_component(self.env, structure_ids=records.ids, validate=True)
            return records

    def write(self, vals):
        if not {"unpaid_work_entry_type_ids", "company_id", "country_id"} & vals.keys():
            return super().write(vals)
        normal = _normal(self)
        normal.check_access("write")
        normal.check_field_access_rights("write", list(set(vals) & {"unpaid_work_entry_type_ids", "company_id", "country_id"}))
        _policy_component(normal.env, structure_ids=self.ids, type_ids=_command_ids(vals.get("unpaid_work_entry_type_ids")))
        with self.env.cr.savepoint():
            result = super().write(vals)
            _policy_component(normal.env, structure_ids=self.ids, validate=True)
            return result

    def unlink(self):
        _policy_component(self.env, structure_ids=self.ids)
        return super().unlink()

    def copy_data(self, default=None):
        policy = _policy_component(self.env, structure_ids=self.ids)
        result = super().copy_data(default=default)
        if "unpaid_work_entry_type_ids" not in (default or {}):
            for record, values in zip(self, result):
                if values is not None:
                    values["unpaid_work_entry_type_ids"] = [Command.set(sorted(kind for structure, kind in policy["pairs"] if structure == record.id))]
        return result


class WorkEntryType(models.Model):
    _inherit = "hr.work.entry.type"

    unpaid_structure_ids = fields.Many2many(
        "hr.payroll.structure", RELATION, "hr_work_entry_type_id", "hr_payroll_structure_id", copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        planned = set().union(*(_command_ids(vals.get("unpaid_structure_ids")) for vals in vals_list))
        if planned:
            _policy_component(self.env, structure_ids=planned)
        with self.env.cr.savepoint():
            records = super().create(vals_list)
            _policy_component(self.env, type_ids=records.ids, validate=True)
            return records

    def write(self, vals):
        if not {"unpaid_structure_ids", "country_id"} & vals.keys():
            return super().write(vals)
        normal = _normal(self)
        normal.check_access("write")
        normal.check_field_access_rights("write", list(set(vals) & {"unpaid_structure_ids", "country_id"}))
        _policy_component(normal.env, type_ids=self.ids, structure_ids=_command_ids(vals.get("unpaid_structure_ids")))
        with self.env.cr.savepoint():
            result = super().write(vals)
            _policy_component(normal.env, type_ids=self.ids, validate=True)
            return result

    def unlink(self):
        _policy_component(self.env, type_ids=self.ids)
        return super().unlink()

    def copy_data(self, default=None):
        policy = _policy_component(self.env, type_ids=self.ids)
        result = super().copy_data(default=default)
        if "unpaid_structure_ids" not in (default or {}):
            for record, values in zip(self, result):
                if values is not None:
                    values["unpaid_structure_ids"] = [Command.set(sorted(structure for structure, kind in policy["pairs"] if kind == record.id))]
        return result


class WorkedDays(models.Model):
    _inherit = "hr.payslip.worked_days"

    def _compute_payment(self):
        # Closed rows must restore stored values even when today's policy is
        # hidden, archived, incompatible or simply different from the past.
        normal = _normal(self)
        for line in normal.filtered(lambda row: not history_protected(row.payslip_id)):
            line.check_access("read")
            line.check_field_access_rights("read", ["payslip_id", "work_entry_type_id", "contract_id", "number_of_days"])
            slip = line.payslip_id
            slip.check_access("read")
            slip.check_field_access_rights("read", ["struct_id", "company_id"])
            if not slip.struct_id:
                raise UserError(_("Select the original payslip structure before calculating worked-day payment."))
            line.contract_id.check_access("read")
            line.contract_id.check_field_access_rights("read", ["wage", "schedule_pay"])
            slip.struct_id._step_check_payroll_scope(slip.company_id)
            _policy_component(normal.env, structure_ids=slip.struct_id.ids,
                type_ids=line.work_entry_type_id.ids, validate=True, company=slip.company_id)
        # The actual existing formula and frozen-cache restoration remain the
        # provider. active_test=False prevents archiving from changing policy.
        return super(WorkedDays, self.with_context(active_test=False))._compute_payment()


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _step_check_original_configuration(self, operation="calculate"):
        result = super()._step_check_original_configuration(operation=operation)
        normal = _normal(self)
        days = normal.env["hr.payslip.worked_days"]
        days.flush_model(["payslip_id", "work_entry_type_id"])
        for slip in normal:
            normal.env.cr.execute("SELECT id FROM hr_payslip_worked_days WHERE payslip_id=%s", (slip.id,))
            original_days = days.browse([row[0] for row in normal.env.cr.fetchall()])
            original_days.check_access("read")
            original_days.check_field_access_rights("read", ["work_entry_type_id"])
            if original_days and not slip.struct_id:
                raise UserError(_("Select the original payslip structure before calculating worked-day payment."))
            _policy_component(normal.env, structure_ids=slip._step_selected_payroll_structures().ids,
                type_ids=original_days.work_entry_type_id.ids, validate=True, company=slip.company_id)
        return result
