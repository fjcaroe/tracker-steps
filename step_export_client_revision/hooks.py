"""Classify only exact historical relations, without guessing contacts or programs."""
from .models.revision import ROLES


def post_init_hook(env):
    for relation, flag in ROLES.items():
        env.cr.execute('UPDATE res_partner p SET '+flag+'=true WHERE EXISTS '
            '(SELECT 1 FROM step_export_export s WHERE s.'+relation+'=p.id)')
    env.cr.execute('''UPDATE step_export_sales_program p SET transport_type=t.transport_type
        FROM (SELECT sales_program_id, min(transport_type) AS transport_type
              FROM step_export_export WHERE sales_program_id IS NOT NULL
              GROUP BY sales_program_id HAVING count(DISTINCT transport_type)=1) t
        WHERE p.id=t.sales_program_id AND p.transport_type IS NULL''')
    env.cr.execute('''UPDATE sale_order o SET step_export_sale_mode_id=s.sale_mode_id
        FROM step_export_export s WHERE o.step_export_shipment_id=s.id
        AND o.step_export_sale_mode_id IS NULL AND s.sale_mode_id IS NOT NULL''')
    # Populate only the new related column. ORM recomputation here would stamp
    # historical weeks as edited by the installing user, changing their audit.
    env.cr.execute('''UPDATE step_export_sales_program_line l SET transport_type=p.transport_type
        FROM step_export_sales_program p WHERE l.program_id=p.id''')
    env.invalidate_all()
