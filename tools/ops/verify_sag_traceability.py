"""Run both approved functional flows in the same registry, rolling back fixtures."""
from pathlib import Path

for filename in ('verify_sag_lot.py', 'verify_traceability.py'):
    exec(compile((Path(PROBE_TOOLS) / filename).read_text(), filename, 'exec'))

from preserve_fruit_constraints import LEGACY,CANONICAL
for (table,column) in LEGACY:
    model=next(model for model in env.registry.models.values() if model._table==table and column in model._fields)
    assert model._fields[column].comodel_name=='step.management.fruit.category'
    env.cr.execute('SELECT target.relname,c.convalidated FROM pg_constraint c '
        'JOIN pg_class source ON source.oid=c.conrelid JOIN pg_class target ON target.oid=c.confrelid '
        'JOIN pg_attribute a ON a.attrelid=source.oid AND a.attnum=ANY(c.conkey) '
        "WHERE c.contype='f' AND source.relname=%s AND a.attname=%s",(table,column))
    assert env.cr.fetchall()==[(CANONICAL,True)]
print('MANAGEMENT_CANONICAL_FRUIT_FKS_OK')
