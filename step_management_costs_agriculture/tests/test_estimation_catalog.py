from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.addons.step_management_costs_agriculture.models.estimation_catalog import backfill_catalog_links


@tagged("post_install", "-at_install")
class TestEstimationCatalog(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.season = cls.env["step.temporada"].create({"name": "T50 2026/2027", "code": "T50TEMP"})
        cls.species = cls.env["step.especie"].create({"name": "T50 Cereza", "type_especie": "frutal", "group_especie": "fruta_h"})
        cls.other_species = cls.env["step.especie"].create({"name": "T50 Manzana", "type_especie": "frutal", "group_especie": "poma"})
        group = cls.env["step.grupo.variedad"].create({"name": "T50 Grupo", "especie_id": cls.species.id})
        cls.variety = cls.env["step.variedad"].create({"name": "T50 Santina", "cod_variedad": "T50SANT", "especie_id": cls.species.id, "grupo_variedad_id": group.id})
        cls.version = cls.env["step.management.estimation.version"].create({"name": "T50 Version", "code": "T50VERSION", "season_id": cls.season.id})
        cls.unit = cls.env["step.management.estimation.unit"].create({"name": "T50 Kilo", "code": "T50KILO", "kg_factor": 1})

    def estimation(self, **values):
        vals = {"version_id": self.version.id, "unit_id": self.unit.id}
        vals.update(values)
        return self.env["step.management.estimation"].create(vals)

    def test_catalog_selectors_and_snapshots(self):
        est = self.estimation(species_id=self.species.id, variety_id=self.variety.id)
        est.flush_recordset()
        est.invalidate_recordset()
        self.assertEqual(est.season_id, self.season)
        self.assertEqual(est.season, self.season.name)
        self.assertEqual(est.species, self.species.name)
        self.assertEqual(est.variety, self.variety.name)
        for name, model in [("season_id", "step.temporada"), ("species_id", "step.especie"), ("variety_id", "step.variedad")]:
            self.assertEqual(est._fields[name].comodel_name, model)

    def test_form_version_season_and_species_domain(self):
        with Form(self.env["step.management.estimation"]) as form:
            form.version_id = self.version
            self.assertEqual(form.season_id, self.season)
            form.unit_id = self.unit
            form.species_id = self.species
            form.variety_id = self.variety
            form.species_id = self.other_species
            self.assertFalse(form.variety_id)
        self.assertEqual(form.record.species, self.other_species.name)

    def test_reject_wrong_species_and_company(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.estimation(species_id=self.other_species.id, variety_id=self.variety.id)
        company_values = {"name": "T50 Other Company"}
        if "security_lead" in self.env["res.company"]._fields:
            company_values["security_lead"] = 0
        other_company = self.env["res.company"].create(company_values)
        foreign_season = self.env["step.temporada"].create({"name": "T50 Foreign", "company_id": other_company.id})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.estimation(season_id=foreign_season.id)

    def test_change_species_clears_previous_variety(self):
        est = self.estimation(species_id=self.species.id, variety_id=self.variety.id)
        est.write({"species_id": self.other_species.id})
        self.assertFalse(est.variety_id)
        self.assertFalse(est.variety)
        est.write({"species_id": False})
        self.assertFalse(est.species)

    def test_unique_import_texts_resolve_existing_masters(self):
        est = self.estimation(season=" t50temp ", species="t50 cereza", variety="T50SANT")
        self.assertEqual(est.season_id, self.season)
        self.assertEqual(est.species_id, self.species)
        self.assertEqual(est.variety_id, self.variety)
        self.assertEqual(est.season, " t50temp ")

    def test_ambiguous_and_unknown_texts_are_preserved(self):
        self.env["step.temporada"].create({"name": self.season.name})
        est = self.estimation(season=self.season.name, species="Unknown species")
        self.assertFalse(est.season_id)
        self.assertFalse(est.species_id)
        self.assertEqual(est.species, "Unknown species")

    def test_migration_preserves_frozen_snapshot_and_is_idempotent(self):
        est = self.estimation(season="t50temp", species=self.species.name, variety=self.variety.name)
        original = (est.season, est.species, est.variety)
        self.env.cr.execute("UPDATE step_management_estimation SET season_id=NULL, species_id=NULL, variety_id=NULL, state='validated', validation_snapshot='T50 frozen' WHERE id=%s", [est.id])
        est.invalidate_recordset()
        backfill_catalog_links(self.env)
        self.assertEqual(est.season_id, self.season)
        self.assertEqual(est.species_id, self.species)
        self.assertEqual(est.variety_id, self.variety)
        self.assertEqual((est.season, est.species, est.variety), original)
        self.assertEqual(est.validation_snapshot, "T50 frozen")
        backfill_catalog_links(self.env)
        with self.assertRaises(UserError):
            est.write({"season_id": self.season.id})

    def test_catalog_rename_does_not_rewrite_snapshot(self):
        est = self.estimation(species_id=self.species.id, variety_id=self.variety.id)
        original = (est.season, est.species, est.variety)
        self.season.name = "T50 season renamed"
        self.species.name = "T50 species renamed"
        self.variety.name = "T50 variety renamed"
        est.invalidate_recordset()
        self.assertEqual((est.season, est.species, est.variety), original)

    def test_copy_preserves_unknown_historical_season(self):
        est = self.estimation(season='Historical unmatched season', species='Historical species')
        self.assertFalse(est.season_id)
        revision = est.copy()
        self.assertEqual(revision.season, est.season)
        self.assertEqual(revision.species, est.species)
        self.assertFalse(revision.season_id)
