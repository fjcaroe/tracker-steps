"""Verify source species, field identities and the actual SQL constraint on restored Cerro."""
import hashlib
import json
import re

from psycopg2 import IntegrityError


def capture(env, test=False):
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', env.cr.dbname)
    aliases = ('field_step_especie__base_boxes_per_pallet', 'field_step_especie__sag_code',
               'constraint_step_especie_base_boxes_per_pallet_nonnegative')
    identity = {alias: env.ref('step_producer_fruit_reports.' + alias).id for alias in aliases}
    env.cr.execute('SELECT id,sag_code,base_boxes_per_pallet FROM step_especie ORDER BY id')
    rows = env.cr.fetchall()
    env.cr.execute("""SELECT oid,conrelid::regclass::text,pg_get_constraintdef(oid),convalidated
                      FROM pg_constraint WHERE conrelid='step_especie'::regclass
                      AND conname='step_especie_base_boxes_per_pallet_nonnegative'""")
    check = env.cr.fetchone()
    assert check and check[3] and len(rows) == 7 and sum(x[2] is not None for x in rows) == 2
    result = {'ids': identity, 'rows': len(rows), 'codes': sum(bool(x[1]) for x in rows),
              'values_sha256': hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest(), 'check': check}
    if test:
        operator = env['res.users'].browse(6)
        species = env['step.especie'].with_user(operator).with_context(allowed_company_ids=operator.company_ids.ids)
        records = species.search([])
        assert records and not species.env.su
        values = records.web_read({'sag_code': {}, 'base_boxes_per_pallet': {}})
        assert values
        first = records[0]
        try:
            with env.cr.savepoint():
                first.write({'base_boxes_per_pallet': -1})
                first.flush_recordset(['base_boxes_per_pallet'])
        except IntegrityError as exc:
            assert exc.diag.constraint_name == 'step_especie_base_boxes_per_pallet_nonnegative'
        else:
            raise AssertionError('A negative value passed the original PostgreSQL check')
        result['operator_rows'] = len(values)
    return result
