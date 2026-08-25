from datetime import date
from importlib.util import module_from_spec, spec_from_file_location

path = "/opt/dev_odoo18/odoo_agriculture/step_hr_contract_lifecycle/models/hr_severance_calc.py"
spec = spec_from_file_location("hr_severance_calc", path)
module = module_from_spec(spec)
spec.loader.exec_module(module)

result = module.compute_feriado_proporcional(
    date(2021, 3, 15),
    date(2021, 11, 17),
    10000,
)
print(result)
assert result["months"] == 8
assert result["fraction_days"] == 2
assert result["dias_habiles_entitled"] == 10.08
assert result["final_days"] == 14.08
print("LEGAL_EXAMPLE_OK")
