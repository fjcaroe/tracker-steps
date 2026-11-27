"""Mark the tested transport and pricelist closure on an isolated copy of Steps."""
import re


def prepare(cr, database):
    if not re.fullmatch(r'COMMUNITY_STEPS_TRANSPORT_[A-Z0-9_]{1,30}', database):
        raise ValueError('Expected an isolated Steps transport restore')
    cr.execute('SELECT current_database()')
    if cr.fetchone() != (database,):
        raise ValueError('The connected database differs from the private target')
    cr.execute("SELECT name, license FROM ir_module_module WHERE state='installed' ORDER BY name FOR UPDATE")
    original = dict(cr.fetchall())
    if len(original) != 310 or sum(v == 'OEEL-1' for v in original.values()) != 123:
        raise ValueError('The original Steps inventory changed')
    cr.execute("""WITH RECURSIVE keep(name) AS (
                SELECT unnest(ARRAY['steps_transport','fleet','hr','product','base','hr_fleet'])::varchar
                UNION SELECT d.name FROM keep k JOIN ir_module_module m ON m.name=k.name
                      JOIN ir_module_module_dependency d ON d.module_id=m.id)
                SELECT name FROM keep ORDER BY name""")
    keep = {row[0] for row in cr.fetchall()}
    # The original fleet visibility rules use the driver-to-employee relation.
    # Load its genuine provider, so those rules can run under an ordinary user.
    if len(keep) != 21 or not keep <= original.keys() or any(original[k] != 'LGPL-3' for k in keep):
        raise ValueError('Unexpected transport dependency or license in the proposed closure')
    cr.execute("SELECT count(*) FROM ir_model_data WHERE module='steps_transport'")
    if cr.fetchone() != (41,):
        raise ValueError('Original transport identifiers changed')
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %'")
    if cr.fetchone() != (0,):
        raise ValueError('A module operation is pending')
    omitted = sorted(original.keys() - keep)
    cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE state='installed' AND name=ANY(%s)",
               [omitted])
    if cr.rowcount != len(omitted):
        raise ValueError('The scoped module update differs from the original inventory')
    return {'database': database, 'installed_native': len(original), 'enabled': sorted(keep),
            'excluded': omitted, 'enterprise_in_native': 123, 'source_copied': False}
