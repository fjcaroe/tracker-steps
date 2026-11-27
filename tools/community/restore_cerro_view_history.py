"""Restore the six unchanged original view rows whose history an earlier private XML upgrade rewrote."""
import json

import psycopg2
from psycopg2.extras import Json

SOURCE = 'COMMUNITY_CERRO_BOM_STRICT_20261126U42C'
TARGET = 'COMMUNITY_CERRO_BOM_ADOPTED_20261126U42B'
AFFECTED = {4505,4803,4834,4835,4844,5119}


def views(cursor):
    cursor.execute("""SELECT DISTINCT v.id,to_jsonb(v) FROM ir_ui_view v JOIN ir_model_data d
                        ON d.module='studio_customization' AND d.model='ir.ui.view' AND d.res_id=v.id
                       WHERE v.active ORDER BY v.id""")
    rows=dict(cursor.fetchall())
    assert len(rows)==23
    return rows


def main():
    with psycopg2.connect(dbname=SOURCE,host='/var/run/postgresql') as reference:
        reference.set_session(readonly=True)
        with reference.cursor() as cr:
            pristine=views(cr)
    with psycopg2.connect(dbname=TARGET,host='/var/run/postgresql') as trial,trial.cursor() as cr:
        cr.execute("SELECT current_database(),current_user")
        assert cr.fetchone()==(TARGET,'postgres')
        cr.execute('LOCK TABLE ir_ui_view IN ROW EXCLUSIVE MODE')
        existing=views(cr)
        assert pristine.keys()==existing.keys()
        modified={view for view in pristine if pristine[view]!=existing[view]}
        if modified and modified != AFFECTED:
            raise ValueError('The exact six previously recorded view-history changes were not found')
        for view in modified:
            changed={key for key in pristine[view] if pristine[view][key]!=existing[view][key]}
            if changed != {'arch_prev','write_date'}:
                raise ValueError('The current view or its owner changed')
            cr.execute("""UPDATE ir_ui_view v SET arch_prev=r.arch_prev,write_date=r.write_date
                           FROM jsonb_populate_record(NULL::ir_ui_view,%s) r WHERE v.id=r.id""",
                       (Json(pristine[view]),))
            assert cr.rowcount==1
        assert views(cr)==pristine
        print(json.dumps({'restored':sorted(modified),'same_whole_rows':len(pristine)}))


if __name__=='__main__':
    main()
