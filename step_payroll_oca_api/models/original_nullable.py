"""Native required contracts, without replacing OCA's optional configuration.

The explicit adoption admission is deliberately not a generic compute hook:
OCA really supports rules without a code, category or primary structure.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class StructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    name = fields.Char(required=True)


class SalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    category_id = fields.Many2one(ondelete="restrict")


class PayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    # Classical inheritance from salary.rule must not propagate the master's
    # new delete policy into stored historical OCA lines. Native line.category
    # is a non-stored related field; equivalence remains a separate conversion.
    category_id = fields.Many2one(required=False, ondelete="set null")


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    def _step_original_configured_rules(self, structures):
        """Include archived members/children and detect record-rule omissions."""
        normal = self.sudo(False).with_context(active_test=False)
        structures = structures.with_env(normal.env)
        structures.check_access("read")
        structures.check_field_access_rights("read", ["rule_ids"])
        if any(type(ident) is not int for ident in structures.ids):
            raise UserError(_("Save original payroll structures before adoption admission."))
        rules = normal.env["hr.salary.rule"]
        rule_fields = ["parent_rule_id", "struct_id", "code", "category_id", "company_id"]
        rules.check_access("read")
        rules.check_field_access_rights("read", rule_fields)
        rules.flush_model(["parent_rule_id", "struct_id", "code", "category_id"])
        structures.flush_recordset(["rule_ids"])
        normal.env.cr.execute("SELECT rule_id FROM hr_structure_salary_rule_rel WHERE struct_id=ANY(%s)", (structures.ids,))
        frontier = {row[0] for row in normal.env.cr.fetchall()}
        parents = {}
        while frontier:
            records = rules.browse(sorted(frontier))
            records.check_access("read")
            records.check_field_access_rights("read", rule_fields)
            records.parent_rule_id.check_access("read")
            parents.update({rule.id: rule.parent_rule_id.id or False for rule in records})
            normal.env.cr.execute("SELECT id FROM hr_salary_rule WHERE parent_rule_id=ANY(%s)", (sorted(frontier),))
            frontier = {row[0] for row in normal.env.cr.fetchall()} - parents.keys()
        for ident in parents:
            seen = set()
            current = ident
            while current in parents:
                if current in seen:
                    raise UserError(_("Original payroll rule hierarchy contains a cycle."))
                seen.add(current)
                current = parents[current]
        selected = structures.with_context(active_test=False).get_all_rules()
        selected.check_access("read")
        if set(selected.ids) != set(parents):
            raise UserError(_("Original payroll adoption rule membership is incomplete."))
        # A native O2M rule cannot be silently omitted from its projected M2M.
        normal.env.cr.execute("SELECT id FROM hr_salary_rule WHERE struct_id=ANY(%s)", (structures.ids,))
        primary = rules.browse([row[0] for row in normal.env.cr.fetchall()])
        primary.check_access("read")
        primary.check_field_access_rights("read", rule_fields)
        if primary - selected:
            raise UserError(_("Original payroll primary rules are missing their structure membership."))
        return selected

    def _step_check_original_required_contract(self):
        """Read-only precondition for a future original-identity adoption.

        Passing proves only required values and reference scope, not identity,
        original formulas, fiscal certification or an integral conversion.
        No marker, context bypass, master creation or historical calculation.
        """
        normal = self.sudo(False).with_context(active_test=False)
        normal.check_access("read")
        structure_fields = ["type_id", "company_id", "country_id", "parent_id", "rule_ids"]
        normal.check_field_access_rights("read", structure_fields)
        if not normal:
            raise UserError(_("Select original payroll structures before adoption admission."))
        if any(type(ident) is not int for ident in normal.ids):
            raise UserError(_("Save original payroll structures before adoption admission."))
        company = normal.env.company
        company.check_access("read")
        company.check_field_access_rights("read", ["country_id"])
        company.country_id.check_access("read")
        for root in normal:
            (root.company_id | company).check_access("read")
            root.country_id.check_access("read")
            root._step_check_payroll_scope(company)
            structures = root._step_effective_rule_scope()["structures"]
            structures.check_access("read")
            structures.check_field_access_rights("read", structure_fields)
            for structure in structures:
                structure.company_id.check_access("read")
                structure.country_id.check_access("read")
                kind = structure.type_id
                kind.check_access("read")
                kind.check_field_access_rights("read", ["name", "country_id"])
                if not kind or not kind.name:
                    raise UserError(_("Original payroll adoption requires a structure type with its original name."))
                kind.country_id.check_access("read")
                country = structure.country_id or company.country_id
                if kind.country_id and kind.country_id != country:
                    raise UserError(_("Original payroll type is outside the adoption country scope."))
            rules = root._step_original_configured_rules(structures)
            for rule in rules:
                rule.company_id.check_access("read")
                if rule.company_id and rule.company_id != company:
                    raise UserError(_("Original payroll rule is outside the adoption company scope."))
                rule.struct_id.check_access("read")
                rule.struct_id.check_field_access_rights("read", structure_fields)
                rule.category_id.check_access("read")
                if not rule.code or not rule.struct_id or not rule.category_id:
                    raise UserError(_("Original payroll adoption requires each rule's original code, category and primary structure."))
                if rule.struct_id not in structures:
                    raise UserError(_("Original payroll primary structure is outside the adoption hierarchy."))
                category = rule.category_id
                seen = set()
                while category:
                    category.check_access("read")
                    category.check_field_access_rights("read", ["code", "parent_id", "company_id"])
                    if category.id in seen:
                        raise UserError(_("Original payroll category hierarchy contains a cycle."))
                    seen.add(category.id)
                    if not category.code:
                        raise UserError(_("Original payroll adoption requires each category's original code."))
                    category.company_id.check_access("read")
                    if category.company_id and category.company_id != company:
                        raise UserError(_("Original payroll category is outside the adoption company scope."))
                    category = category.parent_id
        return True
