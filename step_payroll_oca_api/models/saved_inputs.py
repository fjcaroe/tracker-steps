"""Admission of complete saved input values; no generation or amount inference.

OCA has no declared amount default. Its Float cache presents SQL NULL as 0.0,
so only the authorized physical value can distinguish missing data from a saved
zero. A non-NULL zero is accepted, without certifying who entered or approved it.
"""
from collections import defaultdict
from decimal import Decimal

from psycopg2 import sql

from odoo import _, models
from odoo.exceptions import UserError


def _existing(records, ids):
    records.check_access("read")
    if set(records.exists().ids) != set(ids):
        raise UserError(_("Original saved payroll input references are incomplete."))
    return records


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _step_check_saved_input_values(self):
        """Validate existing mutable slips and return True without changing them.

        Typed identities are explicit saved FKs. Legacy descriptors have only a
        code contract: require one unambiguous descriptor and one explicitly
        saved type for that exact code; never assign a type by code or label.
        This API is deliberately not a global compute_sheet hook.
        """
        normal = self.sudo(False).with_context(active_test=False)
        if normal._name != "hr.payslip" or any(type(ident) is not int or ident <= 0 for ident in normal.ids):
            raise UserError(_("Save the actual draft payslip before checking its original input values."))
        _existing(normal, normal.ids)
        header = ["state", "employee_id", "company_id", "contract_id", "struct_id", "date_from", "date_to", "input_line_ids"]
        header += [name for name in ("paid", "step_history_locked") if name in normal._fields]
        normal.check_field_access_rights("read", header)
        normal.flush_recordset(header)
        normal.invalidate_recordset([name for name in header if name != "input_line_ids"])
        inputs = normal.env["hr.payslip.input"]
        fields = ["payslip_id", "contract_id", "input_type_id", "code", "amount"]
        inputs.check_access("read")
        inputs.check_field_access_rights("read", fields)
        inputs.flush_model(fields)
        for slip in normal:
            if (slip.state not in ("draft", "verify") or ("paid" in slip._fields and slip.paid)
                    or ("step_history_locked" in slip._fields and slip.step_history_locked)):
                raise UserError(_("Closed payroll history cannot be processed as saved draft inputs."))
            company, employee, contract = slip.company_id, slip.employee_id, slip.contract_id
            if not company or company != normal.env.company:
                raise UserError(_("Select the payslip's original company before checking saved inputs."))
            company.check_access("read")
            company.check_field_access_rights("read", ["country_id"])
            company.country_id.check_access("read")
            employee.check_access("read")
            employee.check_field_access_rights("read", ["company_id"])
            contract.check_access("read")
            contract.check_field_access_rights("read", ["employee_id", "company_id", "date_start", "date_end"])
            if (not employee or not contract or employee.company_id != company
                    or contract.employee_id != employee or contract.company_id != company):
                raise UserError(_("Saved inputs require the payslip's original employee and company contract."))
            if (not slip.date_from or not slip.date_to or slip.date_from > slip.date_to
                    or (contract.date_start and contract.date_start > slip.date_to)
                    or (contract.date_end and contract.date_end < slip.date_from)):
                raise UserError(_("Saved inputs require the actual payslip period to overlap its original contract."))
            structures, rules = normal.env["hr.payroll.structure"], normal.env["hr.salary.rule"]
            for root in slip._step_selected_payroll_structures():
                scope = root._step_effective_rule_scope()
                structures |= scope["structures"]
                rules |= scope["rules"]
            if not structures:
                raise UserError(_("Select the original payroll structure before checking saved inputs."))

            # Read IDs first; monetary values are fetched only after every
            # actual child row and its fields pass the normal actor's access.
            normal.env.cr.execute("SELECT id FROM hr_payslip_input WHERE payslip_id=%s ORDER BY id", (slip.id,))
            identifiers = [row[0] for row in normal.env.cr.fetchall()]
            saved = _existing(inputs.browse(identifiers), identifiers)
            normal.env.cr.execute("SELECT id,payslip_id,contract_id,input_type_id,code,amount FROM hr_payslip_input WHERE id=ANY(%s) ORDER BY id", (identifiers,))
            rows = normal.env.cr.fetchall()
            if {row[0] for row in rows} != set(identifiers):
                raise UserError(_("Original saved payroll input rows changed during admission."))
            if any(not row[3] for row in rows):
                raise UserError(_("Select the existing original input type on every saved input; untyped legacy rows require explicit identity."))

            types = normal.env["hr.payslip.input.type"]
            types.check_access("read")
            types.check_field_access_rights("read", ["code", "active", "country_id", "struct_ids"])
            membership = types._fields["struct_ids"]
            if (membership.type != "many2many" or not membership.store
                    or membership.comodel_name != structures._name or not membership.relation
                    or not membership.column1 or not membership.column2):
                raise UserError(_("The original input-type structure relation requires audited storage."))
            structures.check_field_access_rights("read", ["company_id", "country_id"])
            if "input_line_type_ids" in structures._fields:
                structures.check_field_access_rights("read", ["input_line_type_ids"])
            types.flush_model(["code", "active", "country_id", "struct_ids"])
            relation, type_column, structure_column = map(sql.Identifier,
                (membership.relation, membership.column1, membership.column2))
            normal.env.cr.execute(sql.SQL("SELECT {},{} FROM {} WHERE {}=ANY(%s)").format(
                type_column, structure_column, relation, structure_column), (structures.ids,))
            configured_pairs = normal.env.cr.fetchall()
            configured = {row[0] for row in configured_pairs}
            used = {row[3] for row in rows}
            actual_types = _existing(types.browse(sorted(configured | used)), configured | used)
            actual_types.country_id.check_access("read")
            normal.env.cr.execute(sql.SQL("SELECT {},{} FROM {} WHERE {}=ANY(%s)").format(
                type_column, structure_column, relation, type_column), (actual_types.ids,))
            all_pairs = normal.env.cr.fetchall()
            linked_ids = {row[1] for row in all_pairs}
            linked = _existing(structures.browse(sorted(linked_ids)), linked_ids)
            linked.check_field_access_rights("read", ["company_id", "country_id"])
            by_type = {kind.id: kind for kind in actual_types}
            by_code = defaultdict(set)
            for ident, parent, owner, kind_id, code, amount in rows:
                kind = by_type[kind_id]
                if parent != slip.id or owner != contract.id:
                    raise UserError(_("Saved input rows must retain the payslip's original contract."))
                if not kind.active or (kind.country_id and kind.country_id != company.country_id):
                    raise UserError(_("The original input type must be active and match the payslip country or be shared."))
                allowed = {structure for kind_ident, structure in all_pairs if kind_ident == kind_id}
                if allowed and slip.struct_id.id not in allowed:
                    raise UserError(_("The saved input type is not configured for the original payslip structure."))
                if not code or code != kind.code:
                    raise UserError(_("Saved input codes must match their explicit original types."))
                if amount is None:
                    raise UserError(_("Complete the amount on the existing saved input. SQL NULL is missing data; a saved zero is valid."))
                if isinstance(amount, bool) or not Decimal(str(amount)).is_finite():
                    raise UserError(_("Original saved input amounts must be finite."))
                by_code[code].add(kind_id)
            if any(len(kinds) != 1 for kinds in by_code.values()):
                raise UserError(_("The saved input code has multiple explicit type identities."))
            if configured - used:
                raise UserError(_("Complete the existing saved input values for every configured original type."))

            rules.check_field_access_rights("read", ["input_ids"])
            field = rules._fields["input_ids"]
            if field.type != "one2many" or not field.inverse_name:
                raise UserError(_("The legacy payroll input descriptor relation requires audited storage."))
            descriptors = normal.env[field.comodel_name]
            inverse = descriptors._fields.get(field.inverse_name)
            if (not descriptors._auto or not inverse or inverse.type != "many2one"
                    or not inverse.store or inverse.comodel_name != rules._name):
                raise UserError(_("The legacy payroll input descriptor ownership requires audited storage."))
            descriptors.check_access("read")
            descriptors.check_field_access_rights("read", [inverse.name, "code"])
            descriptors.flush_model([inverse.name, "code"])
            normal.env.cr.execute(sql.SQL("SELECT id FROM {} WHERE {}=ANY(%s)").format(
                sql.Identifier(descriptors._table), sql.Identifier(inverse.name)), (rules.ids,))
            descriptor_ids = [row[0] for row in normal.env.cr.fetchall()]
            required = _existing(descriptors.browse(descriptor_ids), descriptor_ids)
            codes = defaultdict(set)
            for descriptor in required:
                codes[descriptor.code].add(descriptor.id)
            if any(not code or len(owners) != 1 or len(by_code.get(code, ())) != 1 for code, owners in codes.items()):
                raise UserError(_("Legacy payroll descriptors require an unambiguous exact code and an explicitly saved original input type."))
            # Actual existing typed-policy checker, with complete visibility and
            # normal field permissions already checked above; no assignments.
            saved._check_typed_input()
        return True
