"""Qualify the complete native contact and market directory on the protected Cerro freight copy."""
import fcntl
import hashlib
import json

from check_cerro_combined_budget import guard, BUDGET, PACKAGE
from check_cerro_cold_studio import histories, NATIVE_SOURCE
from check_cerro_studio_strict import ROOT, addon_roots, run, tree_sha
from compare_cerro_studio_receipts import receipt, compare
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import PRODUCT_DEST, PRODUCT_TARGET
from restore_cerro_studio_strict import SOURCE, module_census, sql

FREIGHT = ROOT / 'freight-operational-providers-f6a8b14fb0f8'
CONTACTS = ROOT / 'directory-export-contacts-576fba5fa799'


def directory(db):
    return sql(db, """SELECT
      (SELECT count(*)||'|'||md5(string_agg(to_jsonb(p)::text,chr(10) ORDER BY id)) FROM res_partner p),
      (SELECT count(*)||'|'||md5(string_agg(to_jsonb(m)::text,chr(10) ORDER BY id)) FROM step_fruit_market m),
      (SELECT md5(string_agg(to_jsonb(a)::text,chr(10) ORDER BY id)) FROM ir_model_access a
         WHERE a.model_id=(SELECT id FROM ir_model WHERE model='step.fruit.market')),
      (SELECT md5(string_agg(to_jsonb(r)::text,chr(10) ORDER BY id)) FROM ir_rule r
         WHERE r.model_id=(SELECT id FROM ir_model WHERE model='step.fruit.market')),
      (SELECT md5(string_agg((to_jsonb(f)-'write_date')::text,chr(10) ORDER BY f.id))
         FROM ir_model_fields f WHERE f.model='step.fruit.market' OR (f.model IN ('res.partner','res.users')
           AND f.name IN ('step_export','step_export_market_id','step_export_receiver','step_export_generic_receiver',
            'step_export_carrier','step_export_consignee','step_export_notify','step_export_forwarder',
            'step_export_customs_agent','step_export_default_notify_id','step_export_default_consignee_id'))),
      (SELECT md5(string_agg(c.conname||pg_get_constraintdef(c.oid)||c.convalidated::text,chr(10) ORDER BY c.conname))
         FROM pg_constraint c WHERE c.conrelid='step_fruit_market'::regclass OR
           (c.conrelid='res_partner'::regclass AND c.conname IN
            ('res_partner_step_export_default_notify_id_fkey','res_partner_step_export_default_consignee_id_fkey',
             'res_partner_step_export_market_id_fkey')))""")


def main():
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        assert tree_sha(CONTACTS/'step_cerro_export_contacts')=='c75f27147836381f32269043e9dd2ee5699a978314273edbca28a30b2585aa33'
        assert tree_sha(FREIGHT/'step_operations_ui')=='a3d7d18eef315c017acb55a5d1bf35e6824520726c2350872eaa4d0e90a3aebe'
        seed=json.loads((PRODUCT_DEST/'qualified-freight.json').read_text())
        assert seed['census']['installed']==186
        db=PRODUCT_TARGET
        opts=dict(database=db,directory=PRODUCT_DEST,roots=[CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(db)])
        source=directory(SOURCE)
        assert directory(db)==source
        original=json.loads((PRODUCT_DEST/'qualified-archive.json').read_text())['protected']
        for flag,label in [('-i','install'),('-u','upgrade')]:
            try:
                run(label+'-export-contacts',[flag,'step_cerro_export_contacts'],**opts)
            finally:
                assert guard('verify',db)==original and directory(db)==source
                assert histories(db)==histories(NATIVE_SOURCE)
            assert sql(db,"SELECT state FROM ir_module_module WHERE name='step_cerro_export_contacts'")=='installed'
        actor = """import json,sys
from odoo.exceptions import ValidationError,AccessError
from odoo.addons.step_cerro_export_contacts.hooks import bindings, OWNER
sys.path.insert(0,'/opt/steps-validation/community-cerro-studio-strict-20261126U42C/tools')
from probe_cerro_studio_fullread import capture as read
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as client
u=env['res.users'].browse(6)
ctx=dict(allowed_company_ids=u.company_ids.ids)
partners=env['res.partner'].with_user(u).with_context(**ctx)
markets=env['step.fruit.market'].with_user(u).with_context(**ctx)
assert not partners.env.su and markets.search_count([])==4
for module,name,kind in bindings():
    assert env.ref(OWNER+'.'+name)==env.ref(module+'.'+name)
assert env.ref(OWNER+'.export_partners').id==5192
assert env.ref('step_producer_daily_estimate.market_read').id==2220
assert env.ref('step_producer_daily_estimate.market_manage').id==2221
try:
    markets.with_user(env.ref('base.public_user')).check_access('read')
except AccessError:
    pass
else:
    raise AssertionError('Public access to the market catalogue changed')
market=markets.search([],limit=1)
fixture=partners.create({'name':'Prueba privada directorio exportación','step_export_notify':True})
assert fixture.step_export
target=partners.create({'name':'Prueba privada roles de exportación'})
for invalid in [{'step_export_generic_receiver':True},{'step_export_default_consignee_id':fixture.id}]:
    try:
        with env.cr.savepoint():
            target.write(invalid)
    except ValidationError:
        pass
    else:
        raise AssertionError('Invalid native receiver role was accepted')
target.write({'step_export_market_id':market.id,'step_export_generic_receiver':True,
              'step_export_default_notify_id':fixture.id,'step_export_forwarder':True})
assert target.step_export and target.step_export_default_notify_id==fixture and target.step_export_market_id==market
env.cr.rollback()
env.invalidate_all(flush=False)
print('CONTACT_STUDIO',json.dumps(dict(fullread=read(env),routes=routes(env),client=client(env)),sort_keys=True))
env.cr.rollback()
"""
        run('contacts-user',[],actor,**opts)
        current=receipt(PRODUCT_DEST/'contacts-user.log','CONTACT_STUDIO')
        matrix=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),
                       receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),current)
        alias='odoo_studio_res_part_47b48baf-5b77-4192-857b-fed73051f3c7'
        assert alias in matrix['matching_full_record'] and '5192' in matrix['original_routes']
        assert directory(db)==source
        census=module_census(db)
        assert not any(census[k] for k in ('pending','enterprise','non_free'))
        result=dict(census=census,matrix=matrix,actor=6,partners=229,markets=4,market_grants=4,
                    original_xmlids=original,checked_partners_and_markets=hashlib.sha256(source.encode()).hexdigest())
        (PRODUCT_DEST/'qualified-export-contacts.json').write_text(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
