"""Classify only exact historical relations, without guessing contacts or programs."""
from .models.revision import ROLES
import re


def ensure_shipment_sequences(env):
    for transport in ('sea','air','land'):
        code='step.export.shipment.'+transport
        template=env['ir.sequence'].search([('code','=',code)],limit=1)
        assert template, 'Missing canonical shipment sequence '+code
        for company in env['res.company'].search([]):
            if env['ir.sequence'].search_count([('code','=',code),('company_id','in',[False,company.id])]):
                continue
            names=env['step.export.export'].search([('company_id','=',company.id),('transport_type','=',transport)]).mapped('shipment_number')
            suffixes=[int(match.group(1)) for name in names if name and (match:=re.search(r'(\d+)$',name))]
            template.copy({'company_id':company.id,'number_next':max(suffixes,default=0)+1})


def pre_init_hook(env):
    # Adding stored related fields uses ORM writes during registry initialization.
    # Keep the original audit in a transaction-local table, never a second master.
    env.cr.execute('''CREATE TEMPORARY TABLE step_client_revision_week_audit ON COMMIT DROP AS
        SELECT id,write_uid,write_date FROM step_export_sales_program_line''')


def post_init_hook(env):
    ensure_shipment_sequences(env)
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
    env.flush_all()
    env.cr.execute('''UPDATE step_export_sales_program_line l
        SET write_uid=a.write_uid,write_date=a.write_date
        FROM step_client_revision_week_audit a WHERE l.id=a.id''')
    env.invalidate_all(flush=False)
