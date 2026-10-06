"""Read production views and exercise catalog selections; roll all test writes back."""
import json
from lxml import etree
from odoo.tests import Form
from odoo.exceptions import ValidationError

try:
    model = env["step.management.estimation"]
    for name, catalog in [("season_id", "step.temporada"), ("species_id", "step.especie"), ("variety_id", "step.variedad")]:
        assert model._fields[name].type == "many2one"
        assert model._fields[name].comodel_name == catalog
    view = model.get_view(view_id=env.ref("step_management_costs.view_estimation_form").id, view_type="form")
    arch = etree.fromstring(view["arch"])
    for name in ("season_id", "species_id", "variety_id"):
        assert arch.xpath("//sheet/group/group/field[@name='%s']" % name), name
    company = env.company
    season = env["step.temporada"].search([("company_id", "=", company.id)], limit=1)
    species = env["step.especie"].search([("company_id", "=", company.id)], limit=1)
    assert season and species, "Expected existing client catalogs"
    variety = env["step.variedad"].search([("company_id", "=", company.id), ("especie_id", "=", species.id)], limit=1)
    version = env["step.management.estimation.version"].create({"name": "T50 rollback verification", "code": "T50-VERIFY-ROLLBACK", "season_id": season.id})
    unit = env["step.management.estimation.unit"].search([("company_id", "=", company.id)], limit=1)
    assert unit, "Expected estimation units"
    with Form(model) as form:
        form.version_id = version
        assert form.season_id == season
        form.unit_id = unit
        form.species_id = species
        if variety:
            form.variety_id = variety
    estimation = form.record
    estimation.flush_recordset()
    estimation.invalidate_recordset()
    assert estimation.season_id == season and estimation.season == season.name
    assert estimation.species_id == species and estimation.species == species.name
    if variety:
        assert estimation.variety_id == variety and estimation.variety == variety.name
    result = {"database": env.cr.dbname, "catalogs": ["step.temporada", "step.especie", "step.variedad"], "form_onchanges": True, "persisted": True, "variety_checked": bool(variety)}
    print("T50_VERIFY_OK " + json.dumps(result))
finally:
    env.cr.rollback()
