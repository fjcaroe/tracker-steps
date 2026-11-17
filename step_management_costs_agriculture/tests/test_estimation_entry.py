from lxml import etree
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


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
    centers_field = arch.xpath(".//field[@name='center_ids']")[0]
    scope = {name: estimation[name].id for name in ("company_id", "farm_id", "species_id", "variety_id")}
    domain = safe_eval(centers_field.get("domain"), scope)
    choices = env["account.analytic.account"].search(domain)
    assert center in choices and other not in choices

    with Form(estimation) as form:
        with form.line_ids.new() as line_form:
            line_form.center_id = center
            assert line_form.plants == 1200 and line_form.hectares == 2
            assert line_form.yield_ue == 4 and line_form.total_kg == 4800
    assert estimation.center_ids == center
    line = estimation.line_ids
    assert line.cuartel_ids == plots and line.plot == "QA Cuartel A, QA Cuartel B"
    estimation.action_compute_lines()
    assert estimation.total_kg == 4800 and len(estimation.line_ids) == 1
    line.yield_ue = 5
    estimation.action_compute_lines()
    assert estimation.total_kg == 6000
    assert line.yield_ue == 5
    estimation.method = "hectares"
    assert estimation.total_kg == 10
    estimation.method = "kilos"
    line.total_kg_input = 3200
    assert estimation.total_kg == 3200
    line.unlink()
    assert not estimation.center_ids
    estimation.web_save({"center_ids": [Command.set(center.ids)]}, {"center_ids": {}})
    estimation.method = "plants"
    estimation.action_compute_lines()
    assert estimation.total_kg == 4800
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
