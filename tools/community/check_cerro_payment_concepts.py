"""Admit the payment concept catalogue and qualify its native menu, ACLs, rows and valuation rule."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from audit_cerro_original_schema import capture
from check_cerro_catalog_contracts import DB as SOURCE, DEST as SOURCE_DIR, PACKET as CONTRACTS, clone
from check_cerro_catalog_forms import PROBE
from check_cerro_cold_studio import histories, NATIVE_SOURCE
from check_cerro_combined_budget import PACKAGE,BUDGET,guard
from check_cerro_export_contacts import CONTACTS
from check_cerro_freight_directory import FREIGHT
from record_cerro_concept_reference import BODY, reference, state
from check_cerro_studio_strict import ROOT,addon_roots,run,tree_sha
from compare_cerro_studio_receipts import compare,receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_bom_before_guard import all_guards
from restore_cerro_studio_strict import module_census,sql

DEST=Path('/opt/steps-validation/community-cerro-concepts-20261127U45P')
DB='COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
MODULE='step_cerro_export_payment_concepts'
PACKET=ROOT/'export-payment-concepts-cdba41119f13'
ALIAS='odoo_studio_step_exp_190b5787-3bb7-4f94-b7cb-b1b9a20d75cd'


def rows(db):
    return sql(db,"""SELECT
      (SELECT count(*)||'|'||md5(string_agg(to_jsonb(c)::text,chr(10) ORDER BY id)) FROM step_export_payment_concept c),
      (SELECT md5(string_agg((id::text||'|'||step_export_payment_concept_id::text),chr(10) ORDER BY id)) FROM product_template WHERE step_export_payment_concept_id IS NOT NULL),
      (SELECT md5(string_agg(to_jsonb(a)::text,chr(10) ORDER BY a.id)) FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model='step.export.payment.concept'),
      (SELECT md5(string_agg(to_jsonb(c)::text,chr(10) ORDER BY c.id)) FROM ir_rule c WHERE id=538),
      (SELECT md5(string_agg(to_jsonb(t)::text,chr(10) ORDER BY id)) FROM ir_ui_menu t WHERE id IN(982,984,987,1185)),
      (SELECT md5(string_agg(to_jsonb(v)::text,chr(10) ORDER BY id)) FROM ir_ui_view v WHERE id IN(4372,4373,4548,4845))""")


def verify_original_schema():
    result=capture({'source':SOURCE,'payment':DB},[('source','payment')])
    diff=result['comparisons']['source_payment']
    for section in ('columns','constraints','views','indexes','sequences','relations','types','routines','odoo_access',
                    'odoo_rules','odoo_group_users','odoo_group_inheritance','odoo_view_groups','odoo_menu_groups','triggers'):
        assert not diff[section]['changed'] and not diff[section]['removed'],(section,diff[section]['changed'][:1])
    return {part:result['snapshots']['payment'][part] for part in result['snapshots']['payment']}


def main():
    if sys.argv[1:]==['schema']:
        print(json.dumps(verify_original_schema(),sort_keys=True))
        return
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_EX)
        previous=json.loads((SOURCE_DIR/'accepted-views.json').read_bytes())
        clone(SOURCE,SOURCE_DIR,DB,DEST)
        expected=rows(NATIVE_SOURCE)
        assert rows(SOURCE)==rows(DB)==expected and expected.startswith('6|')
        assert tree_sha(PACKET/MODULE)=='abf7405ec810d37b28596121fecc667ef968ebe018b4103da6a5e89302a250d9'
        plan=json.loads((SOURCE_DIR/'original-required.json').read_bytes())
        assert plan['database']==SOURCE and len(plan['fields'])==29
        plan['database']=DB
        plan_file=DEST/'original-required.json'
        plan_file.write_text(json.dumps(plan,sort_keys=True))
        plan_file.chmod(0o644)
        roots=[PACKET,CONTRACTS,CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(DB)]
        options=dict(database=DB,directory=DEST,roots=roots)
        original_hashes=histories(NATIVE_SOURCE)
        for flag,phase in [('-i','install'),('-u','upgrade')]:
            run(phase+'-payment-concepts',[flag,MODULE],launcher=DEST/'code/load_cerro_catalog_contracts.py',**options)
            assert sql(DB,"SELECT state FROM ir_module_module WHERE name='"+MODULE+"'")=='installed'
            assert rows(DB)==expected and histories(DB)==original_hashes
            assert all_guards(DB)==all_guards(SOURCE) and guard('verify',DB)==guard('verify',SOURCE)

        native_path=DEST/'native-concept-user.json'
        if not native_path.exists():
            reference()
        assert hashlib.sha256(native_path.read_bytes()).hexdigest()=='49fa2ff286f841f0bd25a38700befa33b4f963c83af0b52b32ed0b246fdfa9fc'
        source_user=json.loads(native_path.read_bytes())['user']
        before=state(DB)
        try:
            run('concept-user',[],BODY,**options)
        finally:
            state(DB,before)
            assert state(DB)==before
        actual=receipt(DEST/'concept-user.log','PAYMENT_USER')
        assert actual==source_user
        run('concept-forms',[],PROBE.format(tools=str(ROOT/'tools')),**options)
        raw=receipt(DEST/'concept-forms.log','CORRECTED_CERRO_VIEWS')
        matrix=compare(receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ'),
                       receipt(NATIVE/'upgrade-final-v2/native-postflight.log','CERRO_FULL'),raw)
        for section in ('matching_full_record','matching_studio_values','original_routes'):
            assert set(previous['matrix'][section])<=set(matrix[section])
        assert ALIAS in matrix['matching_full_record'] and ALIAS in matrix['matching_studio_values']
        assert '4845' in matrix['original_routes'] and rows(DB)==expected
        paths=raw['routes']['direct_menu_routes']['4845']
        assert any(route['action']==1378 and 987 in route['menus'] for route in paths)
        path=str(DEST/'code')+':'+str(ROOT/'tools')
        frozen=json.loads(subprocess.check_output(['runuser','-u','postgres','--','env','PYTHONPATH='+path,
            '/usr/bin/python3.10',str(Path(__file__).resolve()),'schema']))
        census=module_census(DB)
        assert census['installed']==189 and not any(census[k] for k in ('enterprise','non_free','pending'))
        record=dict(census=census,scope=actual,view=4845,action=1378,menu=987,matrix=matrix,catalogue=frozen,
                    six_rows_and_access_sha256=hashlib.sha256(expected.encode()).hexdigest())
        (DEST/'accepted-concepts.json').write_text(json.dumps(record,sort_keys=True))


if __name__=='__main__':
    main()
