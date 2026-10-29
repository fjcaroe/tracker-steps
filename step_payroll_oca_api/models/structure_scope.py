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
    # Native configuration is global or country-scoped, with no company owner.
    # Keep OCA's normal company default for new records; adoption supplies an
    # explicit NULL rather than assigning an invented owner to original data.
    company_id = fields.Many2one(required=False, ondelete="restrict")
    country_id = fields.Many2one("res.country", string="Country", ondelete="set null")

    def _step_scope_problem(self, company, country=False):
        self.ensure_one()
        if self.company_id and self.company_id != company:
            return "company"
        effective_country = country or company.country_id
        if self.country_id and self.country_id != effective_country:
            return "country"
        return False

    def _step_check_payroll_scope(self, company):
        if any(structure._step_scope_problem(company) for structure in self):
            raise UserError(_("Payroll configuration is outside the original company or country scope."))

    @api.constrains("parent_id", "company_id", "country_id")
    def _check_original_parent_company(self):
        for structure in self:
            parent = structure.parent_id
            if parent and parent._step_scope_problem(structure.company_id, structure.country_id):
                raise ValidationError(_("Salary structure and its original parent have incompatible company or country scope."))
            if structure.company_id and structure.country_id and structure.country_id != structure.company_id.country_id:
                raise ValidationError(_("Salary structure country must match its original company."))

    def _step_effective_rule_scope(self):
        """Match OCA's public hierarchy API, after checking its complete scope.

        Relational IDs are read from SQL only to detect record-rule omissions.
        No sudo, formula evaluation, historical payslip or monetary write is
        involved. Every real structure/rule must pass normal read access.
        """
        self.ensure_one()
        self.check_access("read")
        self.check_field_access_rights("read", ["parent_id", "rule_ids", "company_id", "country_id"])
        self.env["hr.payroll.structure"].flush_model(["parent_id", "company_id", "country_id", "rule_ids"])
        self.env["hr.salary.rule"].flush_model(["active", "parent_rule_id", "company_id", "struct_id"])
        structures = self.env["hr.payroll.structure"]
        seen = set()
        current = self
        while current:
            current.check_access("read")
            if current.id in seen:
                raise UserError(_("Salary structure hierarchy contains a cycle."))
            if current._step_scope_problem(self.company_id, self.country_id):
                raise UserError(_("Salary structure hierarchy crosses company or country boundaries."))
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
            records.check_field_access_rights("read", ["active", "parent_rule_id", "company_id", "struct_id"])
            if any(rule.company_id and rule.company_id != self.company_id for rule in records):
                raise UserError(_("Salary rule hierarchy crosses company boundaries."))
            for rule in records.filtered("struct_id"):
                rule.struct_id.check_access("read")
                if rule.struct_id._step_scope_problem(self.company_id, self.country_id):
                    raise UserError(_("Salary rule primary structure crosses company or country boundaries."))
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

    def _get_employee_contracts(self):
        model = self.env["hr.contract"]
        names = ["employee_id", "company_id", "state", "date_start", "date_end", "struct_id"]
        if "active" in model._fields:
            names.append("active")
        model.flush_model(names)
        expected = set()
        for slip in self:
            slip.employee_id.check_access("read")
            if slip.contract_id:
                original = slip.contract_id
            elif slip.employee_id and slip.date_from and slip.date_to:
                active = " AND active" if "active" in model._fields and slip.employee_id.env.context.get("active_test", True) else ""
                self.env.cr.execute("""SELECT id FROM hr_contract
                    WHERE employee_id=%s AND state='open' AND date_start<=%s
                    AND (date_end IS NULL OR date_end>=%s)""" + active,
                    (slip.employee_id.id, slip.date_to, slip.date_from))
                original = model.browse([row[0] for row in self.env.cr.fetchall()])
            else:
                raise UserError(_("Select the original employee and payslip period before resolving contracts."))
            original.check_access("read")
            if any(contract.employee_id != slip.employee_id or
                   (slip.company_id and contract.company_id != slip.company_id) for contract in original):
                raise UserError(_("Payroll must retain its original employee and company contracts."))
            expected.update(original.ids)
        selected = super()._get_employee_contracts()
        selected.check_access("read")
        if set(selected.ids) != expected:
            raise UserError(_("Payroll contract selection is incomplete or changed; review the original scope."))
        return selected

    def _step_selected_payroll_structures(self):
        """Validate the same explicit/fallback structure set the real OCA API uses."""
        structures = self.struct_id
        if structures:
            for slip in self:
                if slip.struct_id and slip.company_id:
                    slip.struct_id._step_check_payroll_scope(slip.company_id)
        else:
            contracts = self._get_employee_contracts()
            for contract in contracts:
                if contract.struct_id:
                    contract.struct_id._step_check_payroll_scope(contract.company_id)
            structures = contracts.struct_id
        structures.check_access("read")
        for structure in structures:
            structure._step_effective_rule_scope()
        return structures

    def _get_salary_rules(self):
        expected = self.env["hr.salary.rule"]
        for structure in self._step_selected_payroll_structures():
            expected |= structure._step_effective_rule_scope()["rules"]
        # Keep the existing chain, including its original (sequence, id) tie
        # breaker. A scope validator must not replace the provider's policy.
        selected = super()._get_salary_rules()
        selected.check_access("read")
        if set(selected.ids) != set(expected.ids):
            raise UserError(_("Payroll rule selection is incomplete or changed; review the original scope."))
        return selected
