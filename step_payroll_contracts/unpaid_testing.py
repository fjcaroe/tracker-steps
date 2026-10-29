"""Two shared real-relation cases; no inference about the native payroll formula."""
from odoo import api, Command


class UnpaidRelationFixture:
    payroll_group = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Private unpaid relation company",
            "country_id": cls.env.ref("base.cl").id, "currency_id": cls.env.ref("base.CLP").id})
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private unpaid relation manager", "login": "private-unpaid-relation-manager",
            "company_id": cls.company.id, "company_ids": [Command.set(cls.company.ids)],
            "groups_id": [Command.set([cls.env.ref(xmlid).id for xmlid in (
                "base.group_user", cls.payroll_group, "hr.group_hr_manager", "account.group_account_manager")])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids), su=False)
        cls.kind = cls.scope["hr.payroll.structure.type"].create({"name": "Private unpaid relation type"})
        cls.structures = cls.scope["hr.payroll.structure"].create([
            {"name": "Private unpaid relation structure", "code": "PRIVATE_UNPAID_RELATION",
                "type_id": cls.kind.id, "company_id": cls.company.id},
            {"name": "Private archived unpaid relation structure", "code": "PRIVATE_UNPAID_ARCHIVE",
                "type_id": cls.kind.id, "company_id": cls.company.id},
        ])
        cls.structure, cls.other_structure = cls.structures
        cls.entry_types = cls.scope["hr.work.entry.type"].create([
            {"name": "Private unpaid relation entry", "code": "PRIVATE_UNPAID_ENTRY", "country_id": cls.company.country_id.id},
            {"name": "Private second unpaid relation entry", "code": "PRIVATE_UNPAID_SECOND", "country_id": cls.company.country_id.id},
        ])
        cls.entry_type, cls.other_entry_type = cls.entry_types

    def unpaid_pairs(self):
        self.structures.flush_recordset(["unpaid_work_entry_type_ids"])
        self.entry_types.flush_recordset(["unpaid_structure_ids"])
        self.env.cr.execute("""SELECT hr_payroll_structure_id,hr_work_entry_type_id
            FROM hr_payroll_structure_hr_work_entry_type_rel WHERE hr_payroll_structure_id=ANY(%s)
            AND hr_work_entry_type_id=ANY(%s) ORDER BY 1,2""", (self.structures.ids, self.entry_types.ids))
        return self.env.cr.fetchall()

    def case_real_unpaid_relation_metadata_inverse_and_raw_pairs(self):
        self.assertFalse(self.scope.su)
        for model, field_name, column1, column2 in (
            ("hr.payroll.structure", "unpaid_work_entry_type_ids", "hr_payroll_structure_id", "hr_work_entry_type_id"),
            ("hr.work.entry.type", "unpaid_structure_ids", "hr_work_entry_type_id", "hr_payroll_structure_id"),
        ):
            field = self.scope[model]._fields[field_name]
            self.assertEqual(field.type, "many2many")
            self.assertTrue(field.store)
            self.assertTrue(field.copy)
            self.assertFalse(field.readonly)
            self.assertEqual(field.relation, "hr_payroll_structure_hr_work_entry_type_rel")
            self.assertEqual((field.column1, field.column2), (column1, column2))
        self.structure.unpaid_work_entry_type_ids = [Command.link(self.entry_type.id)]
        self.other_entry_type.unpaid_structure_ids = [Command.link(self.structure.id)]
        self.assertEqual(set(self.structure.with_context(active_test=False).unpaid_work_entry_type_ids.ids), set(self.entry_types.ids))
        self.assertEqual(self.entry_type.with_context(active_test=False).unpaid_structure_ids, self.structure)
        self.assertEqual(self.unpaid_pairs(), sorted((self.structure.id, kind.id) for kind in self.entry_types))
        self.entry_type.unpaid_structure_ids = [Command.unlink(self.structure.id)]
        self.assertEqual(self.structure.unpaid_work_entry_type_ids, self.other_entry_type)
        self.assertEqual(self.unpaid_pairs(), [(self.structure.id, self.other_entry_type.id)])

    def case_real_unpaid_relation_keeps_archived_original_pairs(self):
        self.entry_type.unpaid_structure_ids = [Command.set(self.structures.ids)]
        self.other_structure.active = False
        self.entry_type.active = False
        before = self.unpaid_pairs()
        self.assertEqual(before, sorted((structure.id, self.entry_type.id) for structure in self.structures))
        self.assertEqual(set(self.entry_type.with_context(active_test=False).unpaid_structure_ids.ids), set(self.structures.ids))
        for structure in self.structures:
            self.assertEqual(structure.with_context(active_test=False).unpaid_work_entry_type_ids, self.entry_type)
        self.assertEqual(self.unpaid_pairs(), before)
