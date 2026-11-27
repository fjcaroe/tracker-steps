"""Check the original dispatch directory and its cross-company restrictions with the full freight provider."""
import fcntl
import json

from check_cerro_budget_studio import OPERATIONS
from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot
from check_cerro_packing_categories import PACKING, PRODUCER_LINK, categories
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from restore_cerro_bom_before_guard import PRODUCT_DEST, PRODUCT_TARGET
from restore_cerro_studio_strict import SOURCE, module_census, sql
from check_cerro_combined_budget import PACKAGE
from compare_cerro_studio_receipts import receipt,compare
from compare_cerro_studio_strict import NATIVE

FREIGHT=ROOT/'freight-operational-providers-f6a8b14fb0f8'
HASHES={'step_operations_ui':'a3d7d18eef315c017acb55a5d1bf35e6824520726c2350872eaa4d0e90a3aebe'}


def directory(db):
    return sql(db,"""SELECT
      (SELECT md5(string_agg(to_jsonb(d)::text,chr(10) ORDER BY id)) FROM step_freight_dispatch_type d),
      (SELECT md5(string_agg(to_jsonb(d)::text,chr(10) ORDER BY dispatch_type_id,company_id)) FROM step_freight_dispatch_type_company_rel d),
      (SELECT md5(string_agg(jsonb_build_array(id,company_id,dispatch_type_id)::text,chr(10) ORDER BY id)) FROM step_dispatch_guide),
      (SELECT md5(string_agg((to_jsonb(a)-'write_date')::text,chr(10) ORDER BY id)) FROM ir_model_access a WHERE model_id=1320),
      (SELECT md5(string_agg((to_jsonb(r)-'write_date')::text,chr(10) ORDER BY id)) FROM ir_rule r WHERE model_id=1320),
      (SELECT md5(string_agg(jsonb_build_array(id,field_id,value)::text,chr(10) ORDER BY id)) FROM ir_model_fields_selection WHERE field_id IN(25040,30980))""")


def main():
    if {p.name:tree_sha(p) for p in FREIGHT.iterdir() if p.is_dir()}!=HASHES:
        raise ValueError('Incomplete or modified Cerro freight package')
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        db=PRODUCT_TARGET
        assert (PRODUCT_DEST/'qualified-archive.json').is_file()
        assert sql(db,"SELECT state FROM ir_module_module WHERE name='step_hr'")=='uninstalled'
        assert not any(module_census(db)[k] for k in ('enterprise','non_free','pending'))
        original=(directory(SOURCE),snapshot(SOURCE),categories(SOURCE))
        assert (directory(db),snapshot(db),categories(db))==original
        args=dict(database=db,directory=PRODUCT_DEST,roots=[FREIGHT,OPERATIONS,PACKAGE,*addon_roots(db)])
        try:
            run('install-freight-directory',['-i','step_operations_ui'],**args)
        finally:
            assert (directory(db),snapshot(db),categories(db))==original
        assert sql(db,"SELECT state FROM ir_module_module WHERE name='step_operations_ui'")=='installed'
        assert sql(db,"SELECT state FROM ir_module_module WHERE name='step_hr'")=='uninstalled'
        assert not any(module_census(db)[k] for k in ('enterprise','non_free','pending'))
        body="""from odoo.exceptions import ValidationError
import json
actor=env['res.users'].browse(6)
model=env['step.freight.dispatch.type'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids)
assert not model.env.su
fields=('name','paga_flete','company_id','company_ids','step_recipient_kind','active')
entries=model.search([],order='id')
assert len(entries)==7
assert env.ref('step_operations_ui.access_freight_dispatch_type_user').id==2014
assert env.ref('step_operations_ui.action_freight_dispatch_type').id==1367
assert env.ref('studio_customization.odoo_studio_x_tipo_d_3250512b-69a9-4adb-bfed-cfaab2ff993e').id==5267
values=entries.read(fields)
parts={}
for company in actor.company_ids:
    actual=model.with_context(allowed_company_ids=[company.id]).search([],order='id').ids
    expected=[r['id'] for r in values if not r['company_ids'] or company.id in r['company_ids']]
    assert actual==expected
    parts[company.id]=len(actual)
env.cr.execute('SELECT dispatch_type_id,company_id FROM step_dispatch_guide WHERE dispatch_type_id IS NOT NULL ORDER BY id LIMIT 1')
dispatch, linked = env.cr.fetchone()
other_company = next(c for c in actor.company_ids if c.id!=linked)
try:
    with env.cr.savepoint():
        model.browse(dispatch).write({'company_ids':[(6,0,[other_company.id])]})
except ValidationError:
    pass
else:
    raise AssertionError('The historical guide lost its company restriction')
print('FREIGHT_DIRECTORY',json.dumps(dict(actor=actor.id,entries=len(entries),partitions=parts)))
env.cr.rollback()
"""
        run('freight-directory-user',[],body,**args)
        result=receipt(PRODUCT_DEST/'freight-directory-user.log','FREIGHT_DIRECTORY')
        code='import json,sys\nsys.path.insert(0,'+repr(str(ROOT/'tools'))+')\n'
        code+="from probe_cerro_studio_fullread import capture as fullread\nfrom probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\n"
        code+="print('FREIGHT_STUDIO',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()"
        run('freight-studio',[],code,**args)
        full=receipt(PRODUCT_DEST/'freight-studio.log','FREIGHT_STUDIO')
        result['matrix']=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),full)
        alias='odoo_studio_x_tipo_d_3250512b-69a9-4adb-bfed-cfaab2ff993e'
        assert alias in result['matrix']['matching_full_record']
        assert '5267' in result['matrix']['original_routes']
        result['census']=module_census(db)
        (PRODUCT_DEST/'qualified-freight.json').write_text(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
