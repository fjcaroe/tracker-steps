from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon


@tagged("post_install", "-at_install")
class TestFase3EstimationCurves(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["step.management.fruit.category"].create({
            "name": "Exportación", "code": "EXP", "company_id": cls.company_a.id,
        })
        cls.fruit_class = cls.env["step.management.fruit.class"].create({
            "name": "Exportación", "code": "EXP", "category_id": cls.category.id,
            "company_id": cls.company_a.id, "use_harvest": True,
        })
        cls.caliber_group = cls.env["step.management.caliber.group"].create({
            "name": "Jumbo", "code": "J", "company_id": cls.company_a.id,
        })

    def _curve(self, curve_type, lines, code=None):
        return self.env["step.management.estimation.curve"].create({
            "name": "Curva %s" % curve_type,
            "code": code or "C-%s" % curve_type,
            "curve_type": curve_type,
            "company_id": self.company_a.id,
            "line_ids": [(0, 0, vals) for vals in lines],
        })

    def test_unit_requires_positive_kg_factor(self):
        with self.assertRaises(ValidationError):
            self.env["step.management.estimation.unit"].create({
                "name": "Racimo", "code": "RAC", "kg_factor": 0,
                "company_id": self.company_a.id,
            })

    def test_week_curve_validates_at_exactly_100(self):
        curve = self._curve("week", [
            {"week_number": 45, "percentage": 40},
            {"week_number": 46, "percentage": 60},
        ])
        self.assertTrue(curve.distribution_complete)
        self.assertEqual(curve.line_ids.mapped("dimension_name"), ["W45", "W46"])
        curve.action_validate()
        self.assertEqual(curve.state, "validated")
        self.assertEqual(curve.validated_by_id, self.env.user)

    def test_caliber_and_class_curves_validate(self):
        caliber = self._curve("caliber", [{
            "caliber_group_id": self.caliber_group.id, "percentage": 100,
        }])
        fruit_class = self._curve("class", [{
            "fruit_class_id": self.fruit_class.id, "percentage": 100,
        }])
        caliber.action_validate()
        fruit_class.action_validate()
        self.assertEqual(caliber.state, "validated")
        self.assertEqual(fruit_class.state, "validated")

    def test_incomplete_curve_cannot_validate(self):
        curve = self._curve("week", [{"week_number": 45, "percentage": 99}])
        with self.assertRaises(UserError):
            curve.action_validate()

    def test_dimension_must_match_curve_type(self):
        with self.assertRaises(ValidationError):
            self._curve("week", [{
                "week_number": 45, "caliber_group_id": self.caliber_group.id,
                "percentage": 100,
            }])
        with self.assertRaises(ValidationError):
            self._curve("week", [{"week_number": 54, "percentage": 100}])

    def test_duplicate_dimension_has_database_constraint(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self._curve("week", [
                    {"week_number": 45, "percentage": 50},
                    {"week_number": 45, "percentage": 50},
                ])

    def test_validated_curve_and_lines_are_immutable(self):
        curve = self._curve("week", [{"week_number": 45, "percentage": 100}])
        curve.action_validate()
        with self.assertRaises(UserError):
            curve.write({"name": "Cambio"})
        with self.assertRaises(UserError):
            curve.line_ids.write({"percentage": 90})
        with self.assertRaises(UserError):
            curve.line_ids.unlink()
        with self.assertRaises(UserError):
            curve.unlink()
        curve.action_set_draft()
        curve.line_ids.write({"percentage": 90})
        self.assertEqual(curve.state, "draft")

    def test_operator_cannot_create_or_validate_curve(self):
        with self.assertRaises(AccessError):
            self.env["step.management.estimation.curve"].with_user(
                self.user_operator
            ).create({
                "name": "No autorizada", "code": "NO", "curve_type": "week",
                "company_id": self.company_a.id,
            })
        curve = self._curve("week", [{"week_number": 45, "percentage": 100}])
        with self.assertRaises(UserError):
            curve.with_user(self.user_operator).action_validate()

    def test_company_rule_and_cross_company_dimension(self):
        group_b = self.env["step.management.caliber.group"].create({
            "name": "Grupo B", "code": "GB", "company_id": self.company_b.id,
        })
        with self.assertRaises(UserError):
            self._curve("caliber", [{
                "caliber_group_id": group_b.id, "percentage": 100,
            }])
        curve_b = self.env["step.management.estimation.curve"].create({
            "name": "Curva B", "code": "CB", "curve_type": "week",
            "company_id": self.company_b.id,
        })
        visible = self.env["step.management.estimation.curve"].with_user(
            self.user_operator
        ).search([])
        self.assertNotIn(curve_b, visible)
