"""Verify original Cerro fruit-category links while loading ordinary packing and producer providers."""
import fcntl
import json
import subprocess

from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot as estimate_contract
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from restore_cerro_studio_strict import ESTIMATE_ROOT, ESTIMATE_TARGET, SOURCE, module_census, sql

PRODUCER_LINK = ROOT / 'producer-accounting-89513ee4690f'
PRODUCER_HASHES = {
    'step_management_costs_producers': 'c9a375912acd7ce36050e87ca4f9c1f620aca9af5e1880311f685a4d847dbf03',
    'step_cerro_studio_producers': '60426909e9b86cf2452bb33be0176e018c5d50bf613c553fbd899a159ad4b4eb',
}
PACKING = ROOT / 'canonical-fruit-category-bd6dc32d58ae'
HASHES = {
    'step_packing': 'c969ad2c02494b0aef31636faddd8fa509ccb0370088e673550b415f20707ece',
    'step_producers': 'ed14062ab6758ff2a27e02c73890c47b52e49ef2e24782f0d7a9a3deb98812c0',
}
RELATIONS = [('stock_picking','fruit_category_id',26755),('stock_picking','fruit_class_id',26756),
             ('step_packing_picking_tag_line','category_id',26741),('step_producer_purchase_contract_product','category_id',27366)]


def categories(database):
    result = {}
    for table, column, field_id in RELATIONS:
        original = sql(database, f"""SELECT id,model,name,ttype,relation,on_delete FROM ir_model_fields
            WHERE id={field_id} AND model='{table.replace('_','.')}' AND name='{column}'""")
        assert original.endswith('|many2one|step.management.fruit.category|set null')
        fk = sql(database, f"""SELECT pg_get_constraintdef(c.oid),c.convalidated FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
            WHERE c.contype='f' AND c.conrelid='{table}'::regclass AND a.attname='{column}'""")
        assert fk == f'FOREIGN KEY ({column}) REFERENCES step_management_fruit_category(id) ON DELETE SET NULL|t'
        values = sql(database, f"""SELECT count(*),count(d.{column}),count(*) FILTER(WHERE d.{column} IS NOT NULL AND m.id IS NULL),
            md5(string_agg(jsonb_build_array(d.id,d.{column})::text,chr(10) ORDER BY d.id))
            FROM {table} d LEFT JOIN step_management_fruit_category m ON m.id=d.{column}""")
        assert values.split('|')[2] == '0'
        result[table + '.' + column] = [original, fk, values]
    return result


def main():
    if {p.name: tree_sha(p) for p in PRODUCER_LINK.iterdir() if p.is_dir()} != PRODUCER_HASHES:
        raise ValueError('The analytic producer bridge changed')
    if {p.name: tree_sha(p) for p in PACKING.iterdir() if p.is_dir()} != HASHES:
        raise ValueError('The admitted packing or producer source changed')
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        if sql(ESTIMATE_TARGET,"SELECT state FROM ir_module_module WHERE name='step_management_estimation_entry'") != 'installed':
            raise ValueError('The native plot estimator must complete qualification first')
        reference = categories(SOURCE)
        estimates = estimate_contract(SOURCE)
        assert categories(ESTIMATE_TARGET) == reference and estimate_contract(ESTIMATE_TARGET) == estimates
        opts = dict(database=ESTIMATE_TARGET, directory=ESTIMATE_ROOT, roots=[PRODUCER_LINK, PACKING, ESTIMATES, BRIDGE, *addon_roots(ESTIMATE_TARGET)])
        outcome = {}
        pending = sql(ESTIMATE_TARGET, "SELECT name FROM ir_module_module WHERE state IN ('to install','to remove','to upgrade') ORDER BY name").splitlines()
        if pending:
            if pending != ['step_management_costs_producers']:
                raise ValueError('Unexpected pending module before the packing qualification')
            run('complete-producer-accounting-bridge', ['-i','step_management_costs_producers'], **opts)
            assert not module_census(ESTIMATE_TARGET)['pending']
        for module in ('step_cerro_studio_agriculture','step_packing','step_producers','step_cerro_product_account_views',
                       'step_cerro_studio_companies','step_cerro_studio_species','step_cerro_studio_process_types',
                       'step_cerro_studio_transfers','step_cerro_studio_producers'):
            if module=='step_producers' and not outcome.get('step_packing'):
                continue
            try:
                if sql(ESTIMATE_TARGET, "SELECT state FROM ir_module_module WHERE name='" + module + "'") != 'installed':
                    run('load-' + module, ['-i',module], **opts)
                outcome[module] = sql(ESTIMATE_TARGET,"SELECT state FROM ir_module_module WHERE name='" + module + "'") == 'installed'
            except subprocess.CalledProcessError:
                outcome[module] = False
            assert categories(ESTIMATE_TARGET) == reference and estimate_contract(ESTIMATE_TARGET) == estimates
            census = module_census(ESTIMATE_TARGET)
            assert not any(census[key] for key in ('non_free','enterprise','pending'))
            (ESTIMATE_ROOT/'packing-category-state.json').write_text(json.dumps(dict(outcome=outcome,census=census,categories=reference),sort_keys=True))
        if outcome.get('step_packing'):
            body = """import json
actor=env['res.users'].browse(6)
context={'allowed_company_ids':actor.company_ids.ids}
receipt={}
for model_name,column in [('stock.picking','fruit_category_id'),('stock.picking','fruit_class_id'),('step.packing.picking.tag.line','category_id')]:
    model = env[model_name].with_user(actor).with_context(context)
    assert not model.env.su and model._fields[column].comodel_name=='step.management.fruit.category'
    assert model._fields[column].check_company
    records=model.search([(column,'!=',False)],order='id')
    for record in records:
        assert record[column].exists()
        record[column].check_access('read')
    receipt[model_name+'.'+column]=len(records)
assert receipt['step.packing.picking.tag.line.category_id'] and receipt['stock.picking.fruit_category_id']
print('CERRO_CATEGORY_READ',json.dumps(receipt,sort_keys=True))
env.cr.rollback()
"""
            run('fruit-category-user', [], body, **opts)
            if not any(l.startswith('CERRO_CATEGORY_READ ') for l in (ESTIMATE_ROOT/'fruit-category-user.log').read_text().splitlines()):
                raise ValueError('The inventory user could not read the canonical fruit categories')
        full = 'import json,sys\nsys.path.insert(0,' + repr(str(ROOT/'tools')) + ')\n'
        full += "from probe_cerro_studio_fullread import capture\nfrom probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\n"
        full += "print('PACKING_STUDIO',json.dumps(dict(fullread=capture(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()"
        run('packing-studio', [], full, **opts)
        if not any(l.startswith('PACKING_STUDIO ') for l in (ESTIMATE_ROOT/'packing-studio.log').read_text().splitlines()):
            raise ValueError('Packing views did not produce a user receipt')
        print(json.dumps(outcome,sort_keys=True))


if __name__ == '__main__':
    main()
