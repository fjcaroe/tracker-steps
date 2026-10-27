"""Read-only T127 product/aptitude metadata and preservation inventory.

Output contains private historical catalog rows and belongs outside Git.
Never edits Studio, products, classifications, permissions or credentials.
"""
import argparse
import json
from pathlib import Path
import subprocess


def query(database, statement):
    result = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-At', '-v',
        'ON_ERROR_STOP=1', '-d', database], input=statement, text=True,
        capture_output=True, check=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=('LAB_TAREAS', 'CERRO_EL_PLOMO', 'QA-CERROELPLOMO'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assert not (root / '.git').exists() or not args.output.resolve().is_relative_to(root)
    database = args.database
    fields = query(database, "SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM ("
        "SELECT id,model,name,field_description,ttype,relation,related,depends,state,required,translate "
        "FROM ir_model_fields WHERE model='x_aptitud_plaguicidas' OR (model='product.template' "
        "AND (state='manual' OR name LIKE 'agriculture_%' OR name IN ('dia_carencia','hrs_reingreso'))) "
        "ORDER BY model,name) t")
    views = query(database, "SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM ("
        "SELECT id,name,model,inherit_id,arch_db,active FROM ir_ui_view WHERE "
        "model='x_aptitud_plaguicidas' OR (model='product.template' AND "
        "(arch_db::text ILIKE '%x_studio_concentracin%' OR arch_db::text ILIKE '%bpa%' "
        "OR arch_db::text ILIKE '%agriculture_%')) ORDER BY id) t")
    references = query(database, "SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM ("
        "SELECT module,name,model,res_id,noupdate FROM ir_model_data WHERE "
        "(model='ir.model' AND res_id IN (SELECT id FROM ir_model WHERE model='x_aptitud_plaguicidas')) "
        "OR (model='ir.model.fields' AND res_id IN (SELECT id FROM ir_model_fields WHERE "
        "model='x_aptitud_plaguicidas' OR (model='product.template' AND name LIKE 'x_studio_%'))) "
        "ORDER BY module,name) t")
    exists = query(database, "SELECT to_regclass('public.x_aptitud_plaguicidas') IS NOT NULL")
    catalog = query(database, 'SELECT coalesce(json_agg(to_jsonb(t)),\'[]\'::json) FROM x_aptitud_plaguicidas t') if exists else []
    permissions = query(database, "SELECT coalesce(json_agg(row_to_json(t)),'[]'::json) FROM ("
        "SELECT * FROM ir_model_access WHERE model_id IN "
        "(SELECT id FROM ir_model WHERE model='x_aptitud_plaguicidas') ORDER BY id) t")
    proof = {'database': database, 'read_only': True, 'fields': fields, 'views': views,
             'xmlids': references, 'aptitude_catalog': catalog, 'aptitude_access': permissions}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PRODUCT_BPA_INVENTORY_SAVED ' + json.dumps({'database': database,
        'fields': len(fields), 'views': len(views), 'aptitude_rows': len(catalog), 'writes': False}))


if __name__ == '__main__':
    main()
