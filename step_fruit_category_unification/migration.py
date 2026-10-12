"""Move existing relations using explicit same-company equivalences only."""
from psycopg2 import sql

RELATIONS = {
    'stock_picking': {'fruit_category_id': 'step_packing_fruit_category',
                      'fruit_class_id': 'step_packing_fruit_class'},
    'step_packing_picking_tag_line': {'category_id': 'step_packing_fruit_category'},
    'step_producer_purchase_contract_product': {'category_id': 'step_packing_fruit_category'},
}
PRESERVE = (*RELATIONS, 'step_management_fruit_category')


def foreign_keys(cr, table, column, target):
    cr.execute('SELECT c.conname FROM pg_constraint c JOIN pg_class s ON s.oid=c.conrelid '
               'JOIN pg_class r ON r.oid=c.confrelid JOIN pg_attribute a ON a.attrelid=s.oid '
               'AND a.attnum=ANY(c.conkey) WHERE c.contype=%s AND s.relname=%s '
               'AND r.relname=%s AND a.attname=%s', ('f', table, target, column))
    return [row[0] for row in cr.fetchall()]


def category_mapping(cr, identifiers):
    result = {}
    for identifier in sorted(identifiers):
        cr.execute('SELECT c.id FROM step_management_fruit_category c '
                   'JOIN step_packing_fruit_category old ON old.id=c.step_contract_category_id '
                   'WHERE old.id=%s AND c.company_id IS NOT DISTINCT FROM old.company_id', (identifier,))
        matches = cr.fetchall()
        if len(matches) != 1:
            raise ValueError('A referenced legacy category requires one explicit same-company equivalence')
        result[identifier] = matches[0][0]
    return result


def pre_init_hook(env):
    cr = env.cr
    plan = []; required = set()
    # Validate the entire plan before changing any relation or constraint.
    for table, columns in RELATIONS.items():
        for column, target in columns.items():
            constraints = foreign_keys(cr, table, column, target)
            if not constraints:
                continue  # Already canonical; never remap canonical IDs again.
            cr.execute(sql.SQL('SELECT DISTINCT {} FROM {} WHERE {} IS NOT NULL').format(
                sql.Identifier(column), sql.Identifier(table), sql.Identifier(column)))
            ids = {row[0] for row in cr.fetchall()}
            if target == 'step_packing_fruit_class' and ids:
                raise ValueError('Legacy origin classes are still referenced; review the client decision first')
            required.update(ids)
            plan.append((table, column, constraints))
    mapping = category_mapping(cr, required)
    for table in PRESERVE:
        cr.execute(sql.SQL('CREATE TEMP TABLE {} AS SELECT * FROM {}').format(
            sql.Identifier('fruit_original_'+table), sql.Identifier(table)))
    for table, column, constraints in plan:
        for constraint in constraints:
            cr.execute(sql.SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(
                sql.Identifier(table), sql.Identifier(constraint)))
        # One CASE expression prevents old/new ID collisions between mappings.
        if mapping and RELATIONS[table][column] == 'step_packing_fruit_category':
            cases = sql.SQL(' ').join(sql.SQL('WHEN {} THEN {}').format(sql.Literal(old),sql.Literal(new))
                                      for old,new in mapping.items())
            cr.execute(sql.SQL('UPDATE {} SET {}=CASE {} {} ELSE {} END WHERE {} IS NOT NULL').format(
                sql.Identifier(table),sql.Identifier(column),sql.Identifier(column),cases,
                sql.Identifier(column),sql.Identifier(column)))


def post_init_hook(env):
    env.flush_all()
    for table in PRESERVE:
        # Preserve original audit, nullable flags, amounts and all other columns
        # that Odoo may initialize while registering an inherited model.
        env.cr.execute('SELECT attname FROM pg_attribute WHERE attrelid=%s::regclass '
                       'AND attnum>0 AND NOT attisdropped ORDER BY attnum', ('fruit_original_'+table,))
        columns = [row[0] for row in env.cr.fetchall() if row[0] != 'id' and row[0] not in RELATIONS.get(table,{})]
        assignments = sql.SQL(',').join(sql.SQL('{}=old.{}').format(sql.Identifier(n),sql.Identifier(n)) for n in columns)
        env.cr.execute(sql.SQL('UPDATE {} current SET {} FROM {} old WHERE current.id=old.id').format(
            sql.Identifier(table), assignments, sql.Identifier('fruit_original_'+table)))
        env.cr.execute(sql.SQL('DROP TABLE {}').format(sql.Identifier('fruit_original_'+table)))
    env.invalidate_all()
