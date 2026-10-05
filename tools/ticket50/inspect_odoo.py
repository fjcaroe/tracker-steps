"""Read-only T50 inventory; execute through the instance's Odoo shell."""
import hashlib
import json
from pathlib import Path
from odoo.modules.module import get_module_path

modules = env["ir.module.module"].search([("name", "in", ["step_hr", "step_management_costs", "step_management_costs_agriculture"])])
print("T50_MODULES", json.dumps({m.name: {"state": m.state, "version": m.latest_version, "path": get_module_path(m.name)} for m in modules}))
for model in ["step.temporada", "step.especie", "step.variedad", "step.management.estimation", "step.management.estimation.version", "step.management.estimation.import"]:
    fields = [name for name in ["name", "company_id", "especie_id", "grupo_variedad_id", "season", "species", "variety", "season_id", "species_id", "variety_id"] if name in env[model]._fields]
    print("T50_MODEL", json.dumps({"model": model, "count": env[model].search_count([]), "fields": {n: {"type": env[model]._fields[n].type, "required": env[model]._fields[n].required, "comodel": getattr(env[model]._fields[n], "comodel_name", None)} for n in fields}}))
for relative in ["__manifest__.py", "models/estimation.py", "models/cost_center.py", "models/__init__.py"]:
    path = Path(get_module_path("step_management_costs_agriculture")) / relative
    print("T50_SOURCE", relative, hashlib.sha256(path.read_bytes()).hexdigest())
env.cr.rollback()
