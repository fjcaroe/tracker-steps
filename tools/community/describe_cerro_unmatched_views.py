"""Map failed complete Studio reads to original view, field and model owners in the sealed Cerro source."""
import json
import re

from compare_cerro_studio_receipts import receipt
from compare_cerro_studio_strict import NATIVE
from restore_cerro_studio_strict import ESTIMATE_ROOT, sql

SOURCE = 'MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q'


def owners(kind, model, field=None):
    if not re.fullmatch('[a-z_][a-z0-9_.]+',model) or field and not re.fullmatch('[a-z_][a-z0-9_]+',field):
        raise ValueError('Unexpected model or field in the user receipt')
    table,where=('ir_model_fields',f"r.model='{model}' AND r.name='{field}'") if field else ('ir_model',f"r.model='{model}'")
    query=f"""SELECT string_agg(DISTINCT d.module,',' ORDER BY d.module) FROM {table} r
                JOIN ir_model_data d ON d.res_id=r.id AND d.model='{kind}' WHERE {where}"""
    return list(filter(None,sql(SOURCE,query).split(',')))


def matrix():
    rows=receipt(ESTIMATE_ROOT/'packing-studio.log','PACKING_STUDIO')['fullread']
    original=receipt(NATIVE/'fullread/native.log','CERRO_FULL_READ')
    catalog=json.loads(sql(SOURCE,"""SELECT json_object_agg(d.name,json_build_object('id',v.id,'model',v.model,
                   'parent',v.inherit_id,'parent_owners',(SELECT string_agg(DISTINCT p.module,',' ORDER BY p.module)
                   FROM ir_model_data p WHERE p.res_id=v.inherit_id AND p.model='ir.ui.view')))
                  FROM ir_ui_view v JOIN ir_model_data d ON d.res_id=v.id AND d.model='ir.ui.view'
                  WHERE d.module='studio_customization' AND v.active"""))
    assert set(rows)==set(original)==set(catalog) and len(rows)==23
    details={}
    for alias,actual in rows.items():
        if actual==original[alias]:
            continue
        identity=catalog[alias]
        note=actual.get('detail','The full row or field set differs from the native customer record')
        name=note.removeprefix('Missing client description: ')
        if name!=note:
            model,field=name.rsplit('.',1)
            missing=owners('ir.model.fields',model,field)
        elif actual.get('error')=='KeyError':
            model=note.strip("'")
            missing=owners('ir.model',model)
        else:
            missing=[]
        details[alias]=dict(identity,first_failed_read=note,source_namespaces=missing)
    return details


if __name__=='__main__':
    print(json.dumps(matrix(),sort_keys=True))
