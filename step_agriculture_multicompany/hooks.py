"""Add only membership relations; preserve original masters and documents."""
from psycopg2 import sql

MASTERS = {
    'step.fundo': 'step_fundo_company_rel',
    'step.management.fruit.category': 'step_fruit_category_company_rel',
    'step.management.fruit.class': 'step_fruit_class_company_rel',
    'step.management.fruit.quality': 'step_fruit_quality_company_rel',
    'step.fruit.color': 'step_fruit_color_company_rel',
}


def post_init_hook(env):
    for model, relation in MASTERS.items():
        table = env[model]._table
        env.cr.execute(sql.SQL("SELECT id FROM {} WHERE company_id IS NULL LIMIT 1").format(sql.Identifier(table)))
        if env.cr.fetchone():
            raise ValueError('A master without an original company needs an explicit migration decision: ' + model)
        env.cr.execute(sql.SQL("""INSERT INTO {} (master_id, company_id)
            SELECT id, company_id FROM {} ON CONFLICT DO NOTHING""").format(sql.Identifier(relation), sql.Identifier(table)))
    env.invalidate_all()
