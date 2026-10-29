"""Observe the original relationship APIs with normal actors in both engines."""
from odoo import api, Command


class OriginalTypeRelationCases:
    __slots__ = ()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env["res.company"].create({
            "name": "Private original type relation company", "country_id": cls.env.ref("base.cl").id})
        role = "hr_payroll.group_hr_payroll_manager" if cls.NATIVE else "payroll.group_payroll_manager"
        actor = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Private original type relation manager", "login": "private-original-type-relation-manager",
            "company_id": company.id, "company_ids": [Command.set(company.ids)],
            "groups_id": [Command.set([cls.env.ref(role).id, cls.env.ref("base.group_user").id])],
        })
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=company.ids), su=False)
        cls.kinds = cls.scope["hr.payroll.structure.type"].create([
            {"name": "Private original type monthly", "default_schedule_pay": "monthly"},
            {"name": "Private original type weekly", "default_schedule_pay": "weekly"},
        ])
        cls.structures = cls.scope["hr.payroll.structure"]
        for index in range(2):
            values = {"name": "Private original type relation %s" % index,
                "type_id": cls.kinds[0].id, "country_id": company.country_id.id}
            if "code" in cls.structures._fields:
                values["code"] = "PRIVATE_TYPE_RELATION_%s" % index
            if "parent_id" in cls.structures._fields:
                values["parent_id"] = False
            if "company_id" in cls.structures._fields:
                values["company_id"] = False
            cls.structures |= cls.scope["hr.payroll.structure"].create(values)

    def case_type_inverse_is_the_original_fk_without_a_shadow_relation(self):
        self.assertFalse(self.scope.su)
        field = self.scope["hr.payroll.structure.type"]._fields["struct_ids"]
        self.assertEqual((field.type, field.comodel_name, field.inverse_name),
            ("one2many", "hr.payroll.structure", "type_id"))
        self.assertEqual(set(self.kinds[0].struct_ids.ids), set(self.structures.ids))
        self.structures.flush_recordset(["type_id"])
        self.env.cr.execute("SELECT id FROM hr_payroll_structure WHERE type_id=%s ORDER BY id", [self.kinds[0].id])
        self.assertEqual([row[0] for row in self.env.cr.fetchall()], sorted(self.structures.ids))

    def case_type_inverse_write_moves_the_real_fk_and_related_schedule(self):
        structure = self.structures[0]
        original_id = structure.id
        self.kinds[1].write({"struct_ids": [Command.link(original_id)]})
        self.assertEqual(structure.type_id, self.kinds[1])
        self.assertEqual(structure.schedule_pay, "weekly")
        self.assertNotIn(structure, self.kinds[0].struct_ids)
        self.assertEqual(structure.id, original_id)

    def case_schedule_is_readonly_related_and_changes_without_storing_a_new_value(self):
        field = self.scope["hr.payroll.structure"]._fields["schedule_pay"]
        self.assertEqual(tuple(field.related), ("type_id", "default_schedule_pay"))
        self.assertFalse(field.store)
        self.assertTrue(field.readonly)
        self.assertEqual(self.structures.mapped("schedule_pay"), ["monthly", "monthly"])
        self.kinds[0].default_schedule_pay = "weekly"
        self.assertEqual(self.structures.mapped("schedule_pay"), ["weekly", "weekly"])

    def case_count_uses_the_current_visible_original_inverse(self):
        self.assertEqual(self.kinds[0].struct_type_count, len(self.kinds[0].struct_ids))
        self.assertEqual(self.kinds[0].struct_type_count, 2)
        self.kinds[1].write({"struct_ids": [Command.link(self.structures[0].id)]})
        self.assertEqual(self.kinds[0].struct_type_count, 1)
        self.assertEqual(self.kinds[1].struct_type_count, 1)
