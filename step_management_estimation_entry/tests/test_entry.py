from lxml import etree
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger
from odoo.tools.safe_eval import safe_eval
from psycopg2 import IntegrityError


def estimation_entry_sample(env):
    season = env["step.temporada"].create({"name": "QA T226 Temporada"})
    species = env["step.especie"].create({
        "name": "QA T226 Especie", "type_especie": "frutal", "group_especie": "baya",
    })
    group = env["step.grupo.variedad"].create({"name": "QA T226 Grupo", "especie_id": species.id})
    variety = env["step.variedad"].create({
        "name": "QA T226 Variedad", "cod_variedad": "QA-T226",
        "especie_id": species.id, "grupo_variedad_id": group.id,
    })
    farm = env["step.fundo"].create({"name": "QA T226 Fundo"})
    other_farm = env["step.fundo"].create({"name": "QA T226 Otro fundo"})
    plan = env["account.analytic.plan"].create({"name": "QA T226 Centros"})
    common = {
        "plan_id": plan.id, "company_id": env.company.id, "type_costo": "fruta",
        "especie_id": species.id, "variedad_id": variety.id, "has_cost": 2,
        "plant_cost": 1200,
    }
    center = env["account.analytic.account"].create(dict(common, name="QA T226 Centro", fundo_id=farm.id))
    other = env["account.analytic.account"].create(dict(common, name="QA T226 Otro", fundo_id=other_farm.id))
    plots = env["step.cuartel.line"].create([
        {"name": "QA Cuartel A", "centro_id": center.id, "has_cuartel": 1, "plant_cuartel": 600},
        {"name": "QA Cuartel B", "centro_id": center.id, "has_cuartel": 1, "plant_cuartel": 600},
    ])
    unit = env["step.management.estimation.unit"].create({
        "name": "QA T226 Kg", "code": "QA-T226", "kg_factor": 1,
    })
    version = env["step.management.estimation.version"].create({
        "name": "QA T226 Versión", "code": "QA-T226", "season_id": season.id,
    })
    estimation = env["step.management.estimation"].create({
        "version_id": version.id, "unit_id": unit.id, "farm_id": farm.id,
        "species_id": species.id, "variety_id": variety.id, "method": "plants",
        "default_yield_ue": 4,
    })
    return estimation, center, other, plots


def exercise_estimation_entry(estimation, center, other, plots):
    env = estimation.env
    view = env["step.management.estimation"].get_view(
        view_id=env.ref("step_management_costs.view_estimation_form").id, view_type="form",
    )
    arch = etree.fromstring(view["arch"].encode())
    assert arch.xpath("./sheet/group/group/field[@name='farm_id']")
    center_field = arch.xpath(".//field[@name='line_ids']/list/field[@name='center_id']")[0]
    assert center_field.get("readonly") == "False"
    assert arch.xpath(".//field[@name='line_ids']/list/field[@name='cuartel_ids']")
    assert arch.xpath(".//field[@name='line_ids']/list/field[@name='cuartel_id']")
    centers_field = arch.xpath(".//field[@name='center_ids']")[0]
    scope = {name: estimation[name].id for name in ("company_id", "farm_id", "species_id", "variety_id")}
    domain = safe_eval(centers_field.get("domain"), scope)
    choices = env["account.analytic.account"].search(domain)
    assert center in choices and other not in choices

    with Form(estimation) as form:
        with form.line_ids.new() as line_form:
            line_form.center_id = center
            line_form.cuartel_id = plots[0]
            assert line_form.plants == 600 and line_form.hectares == 1
            assert line_form.yield_ue == 4 and line_form.total_kg == 2400
    assert estimation.center_ids == center
    line = estimation.line_ids
    assert line.cuartel_id == plots[0] and line.plot == plots[0].name
    estimation.action_compute_lines()
    assert estimation.total_kg == 4800 and len(estimation.line_ids) == 2
    assert estimation.total_hectares == 2 and estimation.total_plants == 1200
    second = estimation.line_ids - line
    line.yield_ue = 5
    second.yield_ue = 2
    ids = estimation.line_ids.ids
    estimation.action_compute_lines()
    assert estimation.total_kg == 4200 and estimation.line_ids.ids == ids
    assert line.yield_ue == 5 and second.yield_ue == 2
    estimation.method = "hectares"
    assert estimation.total_kg == 7
    estimation.method = "kilos"
    line.total_kg_input = 1000
    second.total_kg_input = 2200
    assert estimation.total_kg == 3200
    line.unlink()
    assert estimation.center_ids == center
    second.unlink()
    assert not estimation.center_ids
    estimation.web_save({"center_ids": [Command.set(center.ids)]}, {"center_ids": {}})
    estimation.method = "plants"
    estimation.action_compute_lines()
    assert estimation.total_kg == 4800 and estimation.line_ids.cuartel_id == plots
    return estimation


@tagged("post_install", "-at_install")
class TestEstimationEntry(TransactionCase):
    def test_form_selection_calculation_and_native_plots(self):
        exercise_estimation_entry(*estimation_entry_sample(self.env))

    def test_filters_reject_another_farm_without_changing_the_master(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        estimation.center_ids = other
        with self.assertRaises(ValidationError):
            estimation.action_compute_lines()
        self.assertFalse(estimation.line_ids)
        self.assertNotEqual(other.fundo_id, estimation.farm_id)

    def test_legacy_draft_expands_without_reusing_center_totals_for_every_plot(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        legacy = self.env["step.management.estimation.line"].create({
            "estimation_id": estimation.id, "center_id": center.id, "yield_ue": 3,
        })
        original_id = legacy.id
        estimation.action_compute_lines()
        self.assertIn(original_id, estimation.line_ids.ids)
        self.assertEqual(estimation.line_ids.cuartel_id, plots)
        self.assertEqual(estimation.total_plants, 1200)
        self.assertEqual(estimation.total_kg, 3600)
        self.assertEqual(estimation.line_ids.mapped("yield_ue"), [3, 3])

    def test_plot_must_belong_to_center_and_cannot_be_repeated(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        estimation.center_ids = center
        estimation.action_compute_lines()
        line = estimation.line_ids[0]
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.write({"center_id": other.id, "cuartel_id": plots[0].id})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                line.copy()

    def test_kilo_aggregate_is_not_duplicated_across_plots(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        estimation.method = "kilos"
        line = self.env["step.management.estimation.line"].create({
            "estimation_id": estimation.id, "center_id": center.id, "total_kg_input": 3200,
        })
        with self.assertRaises(UserError):
            estimation.action_compute_lines()
        self.assertEqual(estimation.line_ids, line)
        self.assertEqual(estimation.total_kg, 3200)
        line.cuartel_id = plots[0]
        estimation.action_compute_lines()
        self.assertEqual(estimation.total_kg, 3200)
        self.assertEqual(len(estimation.line_ids), 2)

    def test_legacy_aggregate_remains_unique(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        line = self.env["step.management.estimation.line"].create({
            "estimation_id": estimation.id, "center_id": center.id,
        })
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                line.copy()

    def test_validated_plot_rows_are_preserved_in_a_revision(self):
        estimation, center, other, plots = estimation_entry_sample(self.env)
        estimation.center_ids = center
        estimation.action_compute_lines()
        estimation.line_ids[0].yield_ue = 5
        estimation.line_ids[1].yield_ue = 2
        category = self.env["step.management.fruit.category"].create({
            "name": "QA T227 fruta", "code": "QA-T227",
        })
        fruit_class = self.env["step.management.fruit.class"].create({
            "name": "QA T227 clase", "code": "QA-T227", "category_id": category.id,
        })
        caliber = self.env["step.management.caliber.group"].create({
            "name": "QA T227 calibre", "code": "QA-T227",
        })
        dimensions = {
            "week": {"week_number": 10},
            "caliber": {"caliber_group_id": caliber.id},
            "class": {"fruit_class_id": fruit_class.id},
        }
        for axis, dimension in dimensions.items():
            curve = self.env["step.management.estimation.curve"].create({
                "name": "QA T227 " + axis, "code": "QA-T227-" + axis,
                "curve_type": axis,
                "line_ids": [Command.create(dict(dimension, percentage=100))],
            })
            curve.action_validate()
            estimation[axis + "_curve_id"] = curve
        user = new_test_user(self.env, login="qa-t227-review", groups="step_management_costs.group_management_manager")
        estimation = estimation.with_user(user)
        estimation.action_validate()
        snapshot, digest = estimation.validation_snapshot, estimation.validation_hash
        with self.assertRaises(UserError):
            estimation.line_ids[0].yield_ue = 9
        with self.assertRaises(UserError):
            estimation.line_ids[0].cuartel_id = plots[1]
        revision = estimation.browse(estimation.action_new_revision()["res_id"])
        self.assertEqual(revision.line_ids.cuartel_id, plots)
        revision.action_compute_lines()
        self.assertEqual(revision.total_kg, estimation.total_kg)
        self.assertEqual((estimation.validation_snapshot, estimation.validation_hash), (snapshot, digest))
