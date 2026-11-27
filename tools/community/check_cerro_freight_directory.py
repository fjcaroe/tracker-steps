"""Check the original dispatch directory and its cross-company restrictions with the full freight provider."""
import fcntl
import json

from check_cerro_budget_studio import OPERATIONS
from check_cerro_estimation_profile import BRIDGE, PROFILE as ESTIMATES, snapshot
from check_cerro_packing_categories import PACKING, PRODUCER_LINK, categories
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from restore_cerro_studio_strict import ESTIMATE_ROOT, ESTIMATE_TARGET, SOURCE, module_census, sql

FREIGHT=ROOT/'freight-directory-profile-395103692ed0'
HASHES={'step_operations_ui':'dd721b11083e4add6796e0945961938d6e7bf56fc884693274414eedb3466a62',
        'step_labor_reports':'d0aa59281eca297aac77d70e811aad468991872581b4165255cdc95a1f03225a',
        'step_hr':'8d9e0c2ef51ce0480631046c3766a876ad9d721d96d062ffba0cb6ffdaf2ae1f'}


def directory(db):
    return sql(db,"""SELECT
      (SELECT md5(string_agg((to_jsonb(d)-'write_date')::text,chr(10) ORDER BY id)) FROM step_freight_dispatch_type d),
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
        db=ESTIMATE_TARGET
        assert not any(module_census(db)[k] for k in ('enterprise','non_free','pending'))
        original=(directory(SOURCE),snapshot(SOURCE),categories(SOURCE))
        assert (directory(db),snapshot(db),categories(db))==original
        args=dict(database=db,directory=ESTIMATE_ROOT,roots=[FREIGHT,OPERATIONS,PRODUCER_LINK,PACKING,ESTIMATES,BRIDGE,*addon_roots(db)])
        try:
            run('install-freight-directory',['-i','step_operations_ui'],**args)
        finally:
            assert (directory(db),snapshot(db),categories(db))==original
        assert sql(db,"SELECT state FROM ir_module_module WHERE name='step_operations_ui'")=='installed'
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
print('FREIGHT_DIRECTORY',json.dumps(dict(actor=actor.id,entries=len(entries),partitions=parts)))
env.cr.rollback()
"""
        run('freight-directory-user',[],body,**args)


if __name__=='__main__':
    main()
