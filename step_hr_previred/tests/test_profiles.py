"""Regresiones de vigencia: nunca elegir un formato por orden o fecha de alta."""

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from ..models import previred_adapter as adapters
from .common import FakeAdapter, PreviredCase


@tagged("post_install", "-at_install")
class TestProfiles(PreviredCase):

    @classmethod
    def setUpClass(cls):
        adapters.register(FakeAdapter)
        super().setUpClass()
        cls.Profile = cls.env["step.previred.profile"]
        cls.v84 = cls.Profile.create({
            "name": "Fake v84", "engine": "fake", "layout": "variable",
            "spec_version": "84", "spec_date": "2025-07",
            "effective_from": "2025-08", "effective_to": "2026-07",
            "source_url": "https://example.invalid/v84",
            "eligible_states": "done,paid",
            "company_ids": [(6, 0, cls.company.ids)],
        })
        cls.v98 = cls.Profile.create({
            "name": "Fake v98", "engine": "fake", "layout": "variable",
            "spec_version": "98", "spec_date": "2026-08",
            "effective_from": "2026-08",
            "source_url": "https://example.invalid/v98",
            "eligible_states": "done,paid",
            "company_ids": [(6, 0, cls.company.ids)],
        })

    def test_period_selects_historical_and_current_profile(self):
        self.assertEqual(
            self.Profile.default_for(self.company, "2026-07"), self.v84)
        self.assertEqual(
            self.Profile.default_for(self.company, "2026-08"), self.v98)

    def test_overlapping_profiles_are_never_selected_silently(self):
        self.Profile.create({
            "name": "Fake v99 overlapping", "engine": "fake",
            "layout": "fixed", "spec_version": "99",
            "spec_date": "2026-08", "effective_from": "2026-08",
            "source_url": "https://example.invalid/v99",
            "eligible_states": "done,paid",
            "company_ids": [(6, 0, self.company.ids)],
        })
        # El largo fijo no está disponible, por lo que no crea ambigüedad.
        self.assertEqual(
            self.Profile.default_for(self.company, "2026-08"), self.v98)
        duplicate = self.Profile.create({
            "name": "Fake v97 overlapping", "engine": "fake",
            "layout": "variable", "spec_version": "97",
            "spec_date": "2026-08", "effective_from": "2026-08",
            "source_url": "https://example.invalid/v97",
            "eligible_states": "done,paid",
            "company_ids": [(6, 0, self.company.ids)],
        })
        with self.assertRaises(UserError):
            self.Profile.default_for(self.company, "2026-08", strict=True)
        duplicate.active = False

