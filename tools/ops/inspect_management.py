"""Read metadata for recent management tickets, excluding business record values."""
import json
import subprocess


def query(database, sql):
    result = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-d', database, '-Atc', sql], text=True).strip()
    return json.loads(result)


for database in ('LAB_TAREAS', 'CERRO_EL_PLOMO', 'STEPS_DEMO'):
    print(json.dumps({'database': database,
        'schema': query(database, "SELECT json_agg(t) FROM (SELECT column_name,data_type FROM information_schema.columns WHERE table_name='account_analytic_account' AND column_name IN ('name','code','root_plan_id','plan_id')) t"),
        'legacy_centers': query(database, "SELECT json_build_object('total',count(*),'linked',count(analytic_account_id)) FROM step_management_cost_center"),
        'catalogs': query(database, "SELECT json_agg(t) FROM (SELECT model,name,ttype,relation,required FROM ir_model_fields WHERE (model IN ('step.management.estimation','step.management.estimation.version') AND name IN ('season','species','variety','season_id','species_id','variety_id','center_id')) OR (model IN ('step.temporada','step.especie','step.variedad','step.grupo.variedad') AND name='company_id') ORDER BY model,name) t"),
        'views': query(database, "SELECT json_agg(t) FROM (SELECT v.id,v.model,v.name,v.active,v.priority,v.inherit_id,d.module,d.name AS xmlid FROM ir_ui_view v LEFT JOIN ir_model_data d ON d.model='ir.ui.view' AND d.res_id=v.id WHERE v.model IN ('step.management.estimation','step.management.estimation.version','step.management.cost.center','account.analytic.account') AND v.type='form' ORDER BY v.model,v.priority,v.id) t")}, ensure_ascii=False))
