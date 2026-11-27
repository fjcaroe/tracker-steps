"""Protect the original external identities during a private Cerro package upgrade."""
import argparse
import json
import re

import psycopg2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--mode', choices=('arm', 'verify'), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', args.database):
        parser.error('Expected a private restored Cerro Studio database')
    with psycopg2.connect(dbname=args.database, host='/var/run/postgresql') as db, db.cursor() as cr:
        cr.execute("SELECT current_database(),current_user,to_regclass('steps_cerro_studio_guard.original_ids')")
        name, role, armed = cr.fetchone()
        assert name == args.database and role == 'postgres'
        if args.mode == 'arm' and not armed:
            cr.execute('CREATE SCHEMA steps_cerro_studio_guard')
            cr.execute('REVOKE ALL ON SCHEMA steps_cerro_studio_guard FROM PUBLIC')
            cr.execute('''CREATE TABLE steps_cerro_studio_guard.original_ids AS
                          SELECT id,module,name,model,res_id FROM public.ir_model_data''')
            cr.execute('ALTER TABLE steps_cerro_studio_guard.original_ids ADD PRIMARY KEY (id)')
            cr.execute("""CREATE FUNCTION steps_cerro_studio_guard.preserve() RETURNS trigger
                          LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
                          BEGIN
                            IF TG_OP='UPDATE' AND (OLD.id,OLD.module,OLD.name,OLD.model,OLD.res_id)
                                IS NOT DISTINCT FROM (NEW.id,NEW.module,NEW.name,NEW.model,NEW.res_id) THEN
                              RETURN NEW;
                            END IF;
                            IF EXISTS (SELECT FROM steps_cerro_studio_guard.original_ids WHERE id=OLD.id) THEN
                              RAISE EXCEPTION 'Protected Cerro XML identity %.%', OLD.module, OLD.name;
                            END IF;
                            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
                            RETURN NEW;
                          END $$""")
            cr.execute('''CREATE TRIGGER steps_cerro_studio_preserve BEFORE UPDATE OR DELETE ON public.ir_model_data
                          FOR EACH ROW EXECUTE FUNCTION steps_cerro_studio_guard.preserve()''')
        elif not armed:
            raise ValueError('Private identity guard has not been armed')
        cr.execute("""SELECT count(*),count(*) FILTER (WHERE d.id IS NULL
                        OR (s.module,s.name,s.model,s.res_id) IS DISTINCT FROM (d.module,d.name,d.model,d.res_id))
                      FROM steps_cerro_studio_guard.original_ids s LEFT JOIN public.ir_model_data d USING(id)""")
        count, changes = cr.fetchone()
        cr.execute("""SELECT tgenabled FROM pg_trigger WHERE tgrelid='public.ir_model_data'::regclass
                      AND tgname='steps_cerro_studio_preserve' AND NOT tgisinternal""")
        assert cr.fetchone() == ('O',) and not changes and count > 10000
        print(json.dumps({'original_xml_ids': count, 'changed': changes, 'guard_enabled': True}))


if __name__ == '__main__':
    main()
