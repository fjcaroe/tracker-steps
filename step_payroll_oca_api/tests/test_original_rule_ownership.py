"""Real OCA ownership mutations keep physical references and historical lines."""
from unittest import TestCase
from unittest.mock import patch

from odoo import api, Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class OriginalRuleOwnershipCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({
            "name": "Private rule ownership company", "country_id": cls.env.ref("base.cl").id,
            "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private rule ownership manager", "login": "private-rule-ownership-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", "payroll.group_payroll_manager", "account.group_account_manager", "hr.group_hr_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id,
            dict(cls.env.context, allowed_company_ids=cls.company.ids, lang="en_US"), su=False)
        cls.journal = cls.scope["account.journal"].create({
            "name": "Private rule ownership journal", "code": "ROW", "type": "general", "company_id": cls.company.id})
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private rule ownership type"})
        cls.owner = cls._structure("OWNER")
        cls.target = cls._structure("TARGET")
        cls.extra = cls._structure("EXTRA")
        cls.category = cls.scope["hr.salary.rule.category"].create({
            "name": "Private rule ownership category", "code": "PRIVATE_RULE_OWNER_CATEGORY", "company_id": cls.company.id})
        cls.rule = cls.scope["hr.salary.rule"].create(cls._rule_values("RESULT", cls.owner))
        # Provision real private employment masters as the fixture author. The
        # tested payroll actor receives no allocation/contact creation grants.
        author = cls.env["hr.employee"].with_company(cls.company)
        cls.employee = author.create({"name": "Private rule ownership employee", "company_id": cls.company.id}).with_env(cls.scope)
        values = {"name": "Private rule ownership contract", "employee_id": cls.employee.id,
            "company_id": cls.company.id, "state": "open", "date_start": fields.Date.today().replace(day=1),
            "wage": 100.0, "structure_type_id": cls.kind.id, "struct_id": cls.owner.id, "journal_id": cls.journal.id}
        if "contract_type_id" in cls.scope["hr.contract"]._fields:
            field = cls.scope["hr.contract"]._fields["contract_type_id"]
            values["contract_type_id"] = cls.env[field.comodel_name].search([], limit=1).id
        cls.contract = cls.env["hr.contract"].with_company(cls.company).create(values).with_env(cls.scope)

    @classmethod
    def _structure(cls, suffix):
        return cls.scope["hr.payroll.structure"].create({
            "name": "Private rule ownership " + suffix, "code": "PRIVATE_RULE_OWNER_" + suffix,
            "parent_id": False, "type_id": cls.kind.id, "company_id": cls.company.id,
            "journal_id": cls.journal.id})

    @classmethod
    def _rule_values(cls, suffix, owner):
        return {"name": "Private rule ownership " + suffix, "code": "PRIVATE_RULE_OWNER_" + suffix,
            "sequence": 1, "category_id": cls.category.id, "company_id": cls.company.id,
            "struct_id": owner.id, "condition_select": "none", "amount_select": "fix", "amount_fix": 100.0}

    def _slip(self):
        return self.scope["hr.payslip"].create({
            "name": "Private rule ownership payslip", "number": "PRIVATE/RULE/OWNER",
            "employee_id": self.employee.id, "company_id": self.company.id,
            "contract_id": self.contract.id, "struct_id": self.owner.id,
            "date_from": fields.Date.today().replace(day=1), "date_to": fields.Date.today()})

    def _configuration(self):
        self.env.flush_all()
        self.env.cr.execute("SELECT id,struct_id FROM hr_salary_rule WHERE id=%s", (self.rule.id,))
        primary = self.env.cr.fetchall()
        self.env.cr.execute("""SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel
            WHERE struct_id=ANY(%s) OR rule_id=%s ORDER BY struct_id,rule_id""",
            ((self.owner | self.target | self.extra).ids, self.rule.id))
        return primary, self.env.cr.fetchall()

    def _hide(self, model, domain, **permissions):
        values = {"name": "Private original ownership visibility", "model_id": self.env["ir.model"]._get_id(model),
            "domain_force": repr(domain), "perm_read": True, "perm_write": True,
            "perm_create": True, "perm_unlink": True}
        values.update(permissions)
        return self.env["ir.rule"].create(values)

    def _history(self, slip):
        self.env.flush_all()
        rows = []
        for table, column, ident in (("hr_payslip", "id", slip.id), ("hr_payslip_line", "slip_id", slip.id),
                ("account_move", "id", slip.move_id.id), ("account_move_line", "move_id", slip.move_id.id)):
            self.env.cr.execute("SELECT to_jsonb(r) FROM " + table + " r WHERE " + column + "=%s ORDER BY id", (ident,))
            rows.append(self.env.cr.fetchall())
        return rows

    def test_move_retains_explicit_memberships_parents_and_master_identity(self):
        self.extra.write({"rule_ids": [Command.link(self.rule.id)]})
        self.target.parent_id = self.owner
        before_id = self.rule.id
        self.rule.write({"struct_id": self.target.id})
        self.assertEqual(self.rule.id, before_id)
        self.assertEqual(self.rule.struct_id, self.target)
        self.assertNotIn(self.rule, self.owner.rule_ids)
        self.assertIn(self.rule, self.target.rule_ids)
        self.assertIn(self.rule, self.extra.rule_ids)
        self.assertEqual(self.target.parent_id, self.owner)
        self.assertEqual(self._configuration(), ([(before_id, self.target.id)],
            sorted([(self.target.id, before_id), (self.extra.id, before_id)])))

    def test_caught_second_step_denial_rolls_back_primary_fk_and_memberships(self):
        # B is accessible before linking. Its real record rule rejects it once
        # the moved master becomes a member, after FK update and old unlink.
        self._hide("hr.payroll.structure", ["|", ("id", "!=", self.target.id), ("rule_ids", "not in", self.rule.ids)])
        self.target.check_access("write")
        self.rule.read(["struct_id"])
        self.owner.read(["rule_ids"])
        before = self._configuration()
        # unittest's assertion owns no savepoint: the product must roll back
        # even when an RPC caller catches this actual late AccessError.
        with TestCase.assertRaises(self, AccessError):
            self.rule.write({"struct_id": self.target.id})
        self.assertEqual(self._configuration(), before)
        self.assertEqual(self.rule.struct_id, self.owner)
        self.assertIn(self.rule, self.owner.rule_ids)
        self.assertNotIn(self.rule, self.target.rule_ids)

    def test_create_denial_keeps_no_master_or_membership_residue(self):
        self._hide("hr.payroll.structure", [("id", "!=", self.target.id)],
            perm_read=False, perm_create=False, perm_unlink=False)
        self.target.check_access("read")
        before = self._configuration()
        values = self._rule_values("REJECTED_CREATE", self.target)
        with TestCase.assertRaises(self, AccessError):
            self.scope["hr.salary.rule"].create(values)
        self.assertEqual(self._configuration(), before)
        self.env.cr.execute("SELECT id FROM hr_salary_rule WHERE code=%s", (values["code"],))
        self.assertFalse(self.env.cr.fetchall())

    def test_hidden_primary_and_field_acl_cannot_be_omitted_from_structure_write(self):
        self.rule.active = False
        self.owner.with_context(active_test=False).read(["rule_ids"])
        self.rule.read(["struct_id"])
        before = self._configuration()
        hidden = self._hide("hr.salary.rule", [("id", "!=", self.rule.id)])
        # Cache a privileged relation, then invoke a public mutator as the
        # original payroll UID. sudo must not hide the normal caller's ACL.
        self.owner.sudo().with_context(active_test=False).read(["rule_ids"])
        with TestCase.assertRaises(self, AccessError):
            self.owner.sudo().write({"rule_ids": [Command.clear()]})
        self.assertEqual(self._configuration(), before)
        hidden.unlink()
        with patch.object(self.scope["hr.salary.rule"]._fields["struct_id"], "groups", "base.group_system"):
            with TestCase.assertRaises(self, AccessError):
                self.owner.sudo().write({"rule_ids": [Command.set(self.rule.ids)]})
        self.assertEqual(self._configuration(), before)
        with TestCase.assertRaises(self, AccessError):
            with patch.object(self.owner._fields["rule_ids"], "groups", "base.group_system"):
                self.owner.sudo().write({"rule_ids": [Command.set(self.rule.ids)]})
        self.assertEqual(self._configuration(), before)
        # Include the archived primary in the ORM operation: default CLEAR
        # preserves archived pairs outside its active relation cache. An
        # actual removal must fail atomically after the relation operation.
        with TestCase.assertRaisesRegex(self, ValidationError, "primary structure"):
            self.owner.with_context(active_test=False).write({"rule_ids": [Command.clear()]})
        self.assertEqual(self._configuration(), before)

    def test_classical_payslip_line_has_its_own_namespace_during_real_calculation(self):
        before = self._configuration()
        slip = self._slip()
        # OCA classically inherits salary.rule. A default on its actual line
        # model is not a request to attach that line ID to a master structure.
        slip.with_context(default_struct_id=self.target.id).compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(slip.line_ids.total, 100.0)
        self.assertEqual(slip.line_ids.struct_id, self.target)
        self.assertEqual(self._configuration(), before)
        slip.line_ids.write({"struct_id": self.extra.id})
        self.assertEqual(slip.line_ids.struct_id, self.extra)
        self.assertEqual(self._configuration(), before)

    def test_owner_edit_preserves_real_posted_lines_ledger_and_history_guards(self):
        debit = self.scope["account.account"].create({"name": "Private rule ownership cost", "code": "940071",
            "account_type": "expense", "company_ids": [Command.set(self.company.ids)]})
        credit = self.scope["account.account"].create({"name": "Private rule ownership debt", "code": "940072",
            "account_type": "liability_current", "company_ids": [Command.set(self.company.ids)]})
        self.rule.write({"account_debit": debit.id, "account_credit": credit.id})
        slip = self._slip()
        slip.compute_sheet()
        self.assertEqual(slip.line_ids.salary_rule_id, self.rule)
        self.assertEqual(slip.line_ids.total, 100.0)
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        self.assertEqual(slip.state, "done")
        self.assertEqual(slip.move_id.state, "posted")
        self.assertEqual(sum(slip.move_id.line_ids.mapped("debit")), 100.0)
        before = self._history(slip)
        self.rule.write({"struct_id": self.target.id})
        self.assertEqual(self.rule.struct_id, self.target)
        self.assertEqual(self._history(slip), before)
        with TestCase.assertRaisesRegex(self, UserError, "Closed payroll"):
            slip.line_ids.write({"struct_id": self.extra.id})
        self.assertEqual(self._history(slip), before)
