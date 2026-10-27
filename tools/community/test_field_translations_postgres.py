"""Real PostgreSQL regressions for translation retention; temporary metadata only."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
from preserve_field_translations import capture,restore
import psycopg2
from psycopg2.extras import Json

class FieldTranslationsCase(unittest.TestCase):
    def test_retains_missing_locales_without_overwriting_new_source_or_explicit_translation(self):
        with psycopg2.connect(dbname='postgres') as conn,conn.cursor() as cr:
            cr.execute('CREATE TEMP TABLE ir_model_fields(id integer,model text,field_description jsonb,help jsonb) ON COMMIT DROP')
            for identity in (1,2,3):
                cr.execute('INSERT INTO ir_model_fields VALUES (%s,%s,%s,%s)',(identity,'hr.contract',
                    Json({'en_US':'Schedule','es_CL':'Horario'}),Json({'en_US':'Original source','es_CL':'Ayuda original'})))
            cr.execute('INSERT INTO ir_model_fields VALUES (4,%s,%s,NULL)',('hr.contract',Json({'en_US':'Untranslated'})))
            before=capture(cr,['hr.contract']);self.assertEqual(len(before),3)
            self.assertEqual(capture(cr),before)
            cr.execute('UPDATE ir_model_fields SET help=%s WHERE id=1',(Json({'en_US':'Original source'}),))
            cr.execute('UPDATE ir_model_fields SET help=%s WHERE id=2',(Json({'en_US':'Changed source'}),))
            cr.execute('UPDATE ir_model_fields SET help=%s WHERE id=3',(Json({'en_US':'Original source','es_CL':'Explicit replacement'}),))
            self.assertEqual(restore(cr,before),1)
            cr.execute('SELECT id,help FROM ir_model_fields ORDER BY id');rows=dict(cr.fetchall())
            self.assertEqual(rows[1],{'en_US':'Original source','es_CL':'Ayuda original'})
            self.assertEqual(rows[2],{'en_US':'Changed source'})
            self.assertEqual(rows[3],{'en_US':'Original source','es_CL':'Explicit replacement'})
            self.assertIsNone(rows[4]);self.assertEqual(restore(cr,before),0)

if __name__=='__main__':unittest.main()
