"""Resolve the actual OCA rule hierarchy without inventing base configuration."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    # The pinned OCA function default refers to hr_payroll.structure_base.
    # Its OCA equivalent and essential rules exist only in demo data. Do not
    # silently make sample payroll a Chilean production configuration. Existing
    # parents remain intact; an original adopted parent is chosen explicitly.
    parent_id = fields.Many2one(default=False)

    @api.constrains("parent_id", "company_id")
    def _check_original_parent_company(self):
        for structure in self:
            parent = structure.parent_id
            if parent and parent.company_id != structure.company_id:
                raise ValidationError(_("Salary structure and its original parent must belong to the same company."))

    def _step_effective_rule_scope(self):
        """Match OCA's public hierarchy API, after checking its complete scope.

        Relational IDs are read from SQL only to detect record-rule omissions.
        No sudo, formula evaluation, historical payslip or monetary write is
        involved. Every real structure/rule must pass normal read access.
        """
        self.ensure_one()
        self.check_access("read")
        self.check_field_access_rights("read", ["parent_id", "rule_ids", "company_id"])
        self.env["hr.payroll.structure"].flush_model(["parent_id", "company_id", "rule_ids"])
        self.env["hr.salary.rule"].flush_model(["active", "parent_rule_id", "company_id"])
        structures = self.env["hr.payroll.structure"]
        seen = set()
        current = self
        while current:
            current.check_access("read")
            if current.id in seen:
                raise UserError(_("Salary structure hierarchy contains a cycle."))
            if current.company_id != self.company_id:
                raise UserError(_("Salary structure hierarchy crosses company boundaries."))
            seen.add(current.id)
            structures |= current
            current = current.parent_id

        self.env.cr.execute("""SELECT rel.struct_id, rel.rule_id
            FROM hr_structure_salary_rule_rel rel JOIN hr_salary_rule rule ON rule.id=rel.rule_id
            WHERE rel.struct_id=ANY(%s) AND rule.active ORDER BY rel.struct_id,rel.rule_id""", (structures.ids,))
        memberships = self.env.cr.fetchall()
        roots = {rule for structure, rule in memberships}
        direct = {rule for structure, rule in memberships if structure == self.id}
        parents = {}
        frontier = roots
        while frontier:
            records = self.env["hr.salary.rule"].with_context(active_test=False).browse(sorted(frontier))
            records.check_access("read")
            records.check_field_access_rights("read", ["active", "parent_rule_id", "company_id"])
            if any(rule.company_id and rule.company_id != self.company_id for rule in records):
                raise UserError(_("Salary rule hierarchy crosses company boundaries."))
            parents.update({rule.id: rule.parent_rule_id.id or False for rule in records})
            self.env.cr.execute("SELECT id FROM hr_salary_rule WHERE parent_rule_id=ANY(%s) AND active", (sorted(frontier),))
            frontier = {row[0] for row in self.env.cr.fetchall()} - parents.keys()
        for ident in parents:
            path = set()
            current = ident
            while current in parents:
                if current in path:
                    raise UserError(_("Salary rule hierarchy contains a cycle."))
                path.add(current)
                current = parents[current]

        # Invoke the real OCA APIs, never reconstruct their calculation order.
        ordered = self.with_context(active_test=True).get_structure_with_parents()
        ordered.check_access("read")
        if set(ordered.ids) != seen:
            raise UserError(_("Salary structure selection changed; review the original hierarchy."))
        rules = ordered.get_all_rules().filtered("active")
        rules.check_access("read")
        if set(rules.ids) != set(parents):
            raise UserError(_("Salary rule selection changed or is incomplete; review the original hierarchy."))
        return {"rules": rules, "structures": ordered,
                "direct_rule_ids": sorted(direct), "backend": "oca-structures-with-parents"}


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _get_salary_rules(self):
        self.ensure_one()
        if self.struct_id:
            return self.struct_id._step_effective_rule_scope()["rules"]
        return super()._get_salary_rules()
