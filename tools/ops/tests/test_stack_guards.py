"""Operational guards: immutable archive and original-column preservation."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import manage_stack


class StackGuards(unittest.TestCase):
    def archive(self, path, corrupt=False, extra=None):
        data=b'approved source'
        name='step_export/__init__.py'
        proof={'commit':'a'*40,'versions':{name:'18.0.1.0.0' for name in manage_stack.MODULES},
               'files':{name:hashlib.sha256(data).hexdigest()}}
        with tarfile.open(path,'w:gz') as archive:
            entries=[(name,b'changed source' if corrupt else data),('release.json',json.dumps(proof).encode())]
            if extra: entries.append((extra,b'escape'))
            for filename, content in entries:
                member=tarfile.TarInfo(filename); member.size=len(content)
                archive.addfile(member,io.BytesIO(content))

    def test_exact_archive_and_reject_corruption_or_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); archive=root/'release.tar.gz'; destination=root/'addons'; destination.mkdir()
            self.archive(archive)
            manage_stack.extract(archive,destination)
            self.assertEqual((destination/'step_export/__init__.py').read_bytes(),b'approved source')
            for options in ({'corrupt':True},{'extra':'../escape'},{'extra':'unknown/file.py'}):
                self.archive(archive,**options)
                with self.assertRaises(AssertionError): manage_stack.extract(archive,destination)
            self.assertFalse((root/'escape').exists())

    def test_snapshot_projects_original_columns_through_native_rename(self):
        seen=[]
        def query(database, sql):
            seen.append(sql)
            if 'SELECT tablename' in sql: return 'x_orden_de_flete'
            if 'json_agg(column_name' in sql: return json.dumps(['id','x_name','write_date'])
            if 'to_regclass' in sql: return ''
            if 'SELECT column_name' in sql: return 'id\nname\nwrite_date\nnew_column'
            if 'string_agg' in sql: return 'x_orden_de_flete|{"count":2,"digest":"original"}'
            raise AssertionError(sql)
        native=SimpleNamespace(MODELS={'x_orden_de_flete':'step.freight.order'},FIELDS={'x_name':'name'})
        with patch.object(manage_stack,'query',query):
            before=manage_stack.business_snapshot('CLONE',native)
            after=manage_stack.business_snapshot('CLONE',native,before['schema'])
        self.assertEqual(before,after)
        self.assertTrue(any("LIKE 'step_%'" in sql for sql in seen))
        projection=next(sql for sql in seen if 'string_agg' in sql)
        self.assertIn("'x_name',to_jsonb(t)->'name'",projection)
        self.assertNotIn('new_column',projection)
        self.assertNotIn('write_date',projection)


if __name__=='__main__': unittest.main()
