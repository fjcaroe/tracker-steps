"""Freight contact roles across cumulative upgrades and native table renames."""


def mark_freight_carriers(cr):
    sources = (
        ('x_tarifa_de_fletes', 'x_studio_transportista'),
        ('x_orden_de_flete', 'x_studio_transportista'),
        ('step_freight_tariff', 'freight_carrier_id'),
        ('step_freight_order', 'freight_carrier_id'),
        ('res_partner', 'transpor_id'),
    )
    queries=[]
    for table,column in sources:
        cr.execute('SELECT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid=to_regclass(%s) '
                   'AND attname=%s AND NOT attisdropped)',(table,column))
        if cr.fetchone()[0]:
            # Identifiers are fixed, versioned constants, never contact text.
            queries.append('SELECT "%s" FROM "%s" WHERE "%s" IS NOT NULL'%(column,table,column))
    if queries:
        cr.execute('UPDATE res_partner SET is_freight_carrier=TRUE WHERE '
                   'is_freight_carrier IS DISTINCT FROM TRUE AND id IN ('+' UNION '.join(queries)+')')
    return cr.rowcount if queries else 0
