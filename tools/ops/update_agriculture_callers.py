"""Apply the reviewed model/field names to versioned agricultural callers."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / 'step_agriculture_records'
schema = runpy.run_path(str(ADDON / 'schema.py'))
field_maps = runpy.run_path(str(ADDON / 'field_names.py'))['FIELDS']
names = dict(schema['COMMON_FIELDS'])
for mapping in field_maps.values():
    for old, new in mapping.items():
        names.setdefault(old, new)
replace = schema['replace_tokens']
for module in ('step_bpa_irrigation', 'step_bpa_inventory', 'step_agro_traceability',
               'step_cosecha', 'step_qa', 'step_budget_design'):
    for path in (ROOT / module).rglob('*'):
        if not path.is_file() or path.suffix not in ('.py', '.xml', '.js', '.csv'):
            continue
        # Preserve the old migration scripts as records of their own versions.
        if any(part in ('migrations', 'upgrades', '__pycache__') for part in path.parts):
            continue
        if module == 'step_bpa_irrigation' and path.name == 'bpa_native.py':
            path.write_text('"""Native agricultural document definitions live in step_agriculture_records."""\n', encoding='utf-8')
            continue
        original = path.read_text(encoding='utf-8')
        updated = replace(replace(original, schema['MODELS']), names)
        if path.suffix == '.csv':
            for old, new in schema['MODELS'].items():
                updated = updated.replace('model_' + old + ',',
                    'step_agriculture_records.model_' + new.replace('.', '_') + ',')
        if path.name == 'phyto_restriction.py':
            # These two accesses refer to the product master, not to application lines.
            updated = updated.replace('p["active_ingredient_id"]', 'p["agriculture_active_ingredient_id"]')
            updated = updated.replace('"active_ingredient_id" in p._fields', '"agriculture_active_ingredient_id" in p._fields')
        if module == 'step_bpa_inventory' and path.name == 'x_aplicacion_foliar_views.xml':
            updated = updated.replace('ref="step_bpa_irrigation.view_application_form"',
                                      'ref="step_agriculture_records.view_application_form"')
            updated = updated.replace('<field name="inherit_id"', '<field name="active" eval="True"/>\n        <field name="inherit_id"')
        if updated != original:
            path.write_text(updated, encoding='utf-8')
            print(path.relative_to(ROOT))
