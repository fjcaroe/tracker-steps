"""Consolidate the same route columns, refusing ambiguous historical values."""


def migrate(cr, version):
    cr.execute("SELECT to_regclass('x_tramo_de_flete')")
    if not cr.fetchone()[0]:
        return
    cr.execute("""SELECT column_name FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='x_tramo_de_flete'""")
    columns = {row[0] for row in cr.fetchall()}
    for canonical, legacy in (
        ('origin', 'x_studio_lugar_desde'),
        ('destination', 'x_studio_lugar_hasta'),
        ('company_id', 'x_studio_empresa'),
    ):
        if canonical not in columns or legacy not in columns:
            continue
        # Empty text is equivalent to an unfilled field; never resolve two
        # different populated values or companies by guessing.
        empty = "NULLIF(%s, '')" if canonical != 'company_id' else '%s'
        left, right = empty % canonical, empty % legacy
        cr.execute(f'SELECT count(*) FROM x_tramo_de_flete WHERE {left} IS NOT NULL '
                   f'AND {right} IS NOT NULL AND {left}<>{right}')
        if cr.fetchone()[0]:
            raise RuntimeError(f'Ambiguous freight route values: {canonical}/{legacy}; migration refused')
        cr.execute(f'UPDATE x_tramo_de_flete SET {canonical}=COALESCE({left},{right}), '
                   f'{legacy}=COALESCE({left},{right})')
    cr.execute("""UPDATE ir_model_fields SET state='base'
                  WHERE model IN ('x_tramo_de_flete','x_modalidad_de_frio')
                    AND state='manual' AND name IN (
                      'x_studio_empresa','x_studio_fundo','x_studio_lugar_desde',
                      'x_studio_lugar_hasta','x_studio_sequence','x_studio_cdigo')""")
