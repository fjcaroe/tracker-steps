"""T50: select agricultural masters while retaining reproducible text snapshots.

The portable core's text fields remain available to imports and historical
plans. Changing a catalog's name never rewrites an existing estimate's snapshot.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.step_management_costs.models.estimation import PROTECTED_HEADER_FIELDS

PROTECTED_HEADER_FIELDS.update({"season_id", "species_id", "variety_id"})
CATALOGS = {
    "season": ("step.temporada", "code"),
    "species": ("step.especie", "cod_especie"),
    "variety": ("step.variedad", "cod_variedad"),
}


def find_master(env, key, text, company_id, species_id=False):
    """Only unique exact names/codes within the company; never invent masters."""
    model, code = CATALOGS[key]
    if not text:
        return env[model]
    domain = env[model]._check_company_domain([company_id])
    if key == "variety" and species_id:
        domain.append(("especie_id", "=", species_id))
    token = str(text).strip().casefold()
    matches = env[model].search(domain).filtered(
        lambda row: token in {(row.name or "").strip().casefold(), (row[code] or "").strip().casefold()}
    )
    return matches if len(matches) == 1 else env[model]


def catalog_values(record, values, keys):
    values = dict(values)
    company_id = values.get("company_id") or (record.company_id.id if record else record.env.company.id)
    selected = {}
    for key in keys:
        field = key + "_id"
        model = CATALOGS[key][0]
        if field in values:
            master = record.env[model].browse(values[field]).exists()
            values[key] = master.name if master else False
        elif key in values:
            master = find_master(record.env, key, values[key], company_id, selected.get("species"))
            values[field] = master.id or False
        else:
            master = record[field] if record else record.env[model]
        selected[key] = master.id or False
    if "variety" in keys and selected["variety"]:
        variety = record.env["step.variedad"].browse(selected["variety"])
        if selected["species"] and variety.especie_id.id != selected["species"]:
            if "variety_id" in values or "variety" in values:
                raise ValidationError(_("La variedad debe pertenecer a la especie seleccionada."))
            values.update({"variety_id": False, "variety": False})
        elif not selected["species"]:
            if "variety_id" in values or "variety" in values:
                if values.get("species"):
                    # An unmatched import label must not be silently replaced.
                    values["variety_id"] = False
                else:
                    values.update({"species_id": variety.especie_id.id, "species": variety.especie_id.name})
            elif "species_id" in values or "species" in values:
                values.update({"variety_id": False, "variety": False})
    return values


class EstimationVersion(models.Model):
    _inherit = "step.management.estimation.version"

    season_id = fields.Many2one(
        "step.temporada", string="Temporada", check_company=True, ondelete="restrict",
        domain="['|', ('company_ids', '=', False), ('company_ids', 'in', [company_id])]",
    )

    @api.onchange("season_id")
    def _onchange_catalog_season(self):
        self.season = self.season_id.name

    @api.model_create_multi
    def create(self, values_list):
        return super().create([catalog_values(self.browse(), values, ["season"]) for values in values_list])

    def write(self, values):
        for record in self:
            super(EstimationVersion, record).write(catalog_values(record, values, ["season"]))
        return True


class Estimation(models.Model):
    _inherit = "step.management.estimation"

    season_id = fields.Many2one(
        "step.temporada", string="Temporada", check_company=True, ondelete="restrict",
        domain="['|', ('company_ids', '=', False), ('company_ids', 'in', [company_id])]", tracking=True,
    )
    species_id = fields.Many2one(
        "step.especie", string="Especie", check_company=True, ondelete="restrict",
        domain="['|', ('company_ids', '=', False), ('company_ids', 'in', [company_id])]", tracking=True,
    )
    variety_id = fields.Many2one(
        "step.variedad", string="Variedad", check_company=True, ondelete="restrict",
        domain="['|', ('company_ids', '=', False), ('company_ids', 'in', [company_id]), ('especie_id', '=', species_id)]", tracking=True,
    )

    @api.onchange("version_id")
    def _onchange_version_id(self):
        super()._onchange_version_id()
        self.season_id = self.version_id.season_id

    @api.onchange("season_id")
    def _onchange_catalog_season(self):
        self.season = self.season_id.name

    @api.onchange("species_id")
    def _onchange_catalog_species(self):
        self.species = self.species_id.name
        if self.variety_id.especie_id != self.species_id:
            self.variety_id = False
            self.variety = False

    @api.onchange("variety_id")
    def _onchange_catalog_variety(self):
        self.variety = self.variety_id.name

    @api.constrains("species_id", "variety_id")
    def _check_catalog_variety(self):
        for record in self:
            if record.variety_id and record.variety_id.especie_id != record.species_id:
                raise ValidationError(_("La variedad debe pertenecer a la especie seleccionada."))

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            values = dict(values)
            if "season" not in values and "season_id" not in values and values.get("version_id"):
                version = self.env["step.management.estimation.version"].browse(values["version_id"])
                if version.season_id:
                    values["season_id"] = version.season_id.id
                else:
                    values["season"] = version.season
            prepared.append(catalog_values(self.browse(), values, ["season", "species", "variety"]))
        return super().create(prepared)

    def write(self, values):
        for record in self:
            prepared = dict(values)
            if "version_id" in values and "season" not in values and "season_id" not in values:
                version = self.env["step.management.estimation.version"].browse(values["version_id"])
                prepared.update({"season_id": version.season_id.id, "season": version.season})
            super(Estimation, record).write(catalog_values(record, prepared, ["season", "species", "variety"]))
        return True


def backfill_catalog_links(env):
    """Migration: link unambiguous old texts, preserving every text and snapshot."""
    counts = {}
    for model, keys in [("step.management.estimation.version", ["season"]),
                        ("step.management.estimation", ["season", "species", "variety"])]:
        linked = 0
        for record in env[model].with_context(active_test=False).search([]):
            links = {}
            species_id = record.species_id.id if "species" in keys else False
            for key in keys:
                if record[key + "_id"]:
                    continue
                master = find_master(env, key, record[key], record.company_id.id, species_id)
                if key == "variety" and master and not species_id:
                    # Do not infer a contradictory species from an old variety label.
                    continue
                if master:
                    links[key + "_id"] = master.id
                    if key == "species":
                        species_id = master.id
            if links:
                columns = ", ".join(name + " = %s" for name in links)
                env.cr.execute("UPDATE " + record._table + " SET " + columns + " WHERE id = %s", [*links.values(), record.id])
                linked += 1
        env[model].invalidate_model()
        counts[model] = linked
    return counts
