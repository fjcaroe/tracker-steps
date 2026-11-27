"""Mark the tested transport and pricelist closure on an isolated copy of Steps."""
import re


def prepare(cr, database):
    assert re.fullmatch(r'COMMUNITY_STEPS_TRANSPORT_[A-Z0-9_]{1,30}', database)
    cr.execute('SELECT current_database()')
    assert cr.fetchone() == (database,)
    cr.execute("SELECT name, license FROM ir_module_module WHERE state='installed' ORDER BY name FOR UPDATE")
    original = dict(cr.fetchall())
    assert len(original) == 310 and sum(v == 'OEEL-1' for v in original.values()) == 123
    cr.execute("""WITH RECURSIVE keep(name) AS (
                SELECT unnest(ARRAY['steps_transport','fleet','hr','product','base','hr_fleet'])::varchar
                UNION SELECT d.name FROM keep k JOIN ir_module_module m ON m.name=k.name
                      JOIN ir_module_module_dependency d ON d.module_id=m.id)
                SELECT name FROM keep ORDER BY name""")
    keep = {row[0] for row in cr.fetchall()}
    # The original fleet visibility rules use the driver-to-employee relation.
    # Load its genuine provider, so those rules can run under an ordinary user.
    assert len(keep) == 21 and keep <= original.keys() and all(original[k] == 'LGPL-3' for k in keep)
    cr.execute("SELECT count(*) FROM ir_model_data WHERE module='steps_transport'")
    assert cr.fetchone() == (41,)
    cr.execute("SELECT count(*) FROM ir_module_module WHERE state LIKE 'to %'")
    assert cr.fetchone() == (0,)
    omitted = sorted(original.keys() - keep)
    cr.execute("UPDATE ir_module_module SET state='uninstalled' WHERE state='installed' AND name=ANY(%s)",
               [omitted])
    assert cr.rowcount == len(omitted)
    return {'database': database, 'installed_native': len(original), 'enabled': sorted(keep),
            'excluded': omitted, 'enterprise_in_native': 123, 'source_copied': False}
