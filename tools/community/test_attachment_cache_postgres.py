"""Prove the operations cache exception against real PostgreSQL, session-local only."""
import argparse
import json
import re
import unittest

from validate_agriculture_core import GENERATED_ASSET_CACHE, sql


class CacheContractCase(unittest.TestCase):
    def test_only_exact_public_generated_bundles_are_cache(self):
        result = json.loads(sql(self.database, """
            SELECT json_agg(coalesce(""" + GENERATED_ASSET_CACHE + """,false) ORDER BY id)
            FROM (VALUES
              (1,'ir.ui.view',NULL,0,'binary',true,'text/css','/web/assets/abc123/web.assets_web.min.css'),
              (2,'ir.ui.view',NULL,42,'binary',true,'text/css','/web/assets/abc123/web.assets_web.min.css'),
              (3,'account.move',NULL,0,'binary',true,'text/css','/web/assets/abc123/web.assets_web.min.css'),
              (4,'ir.ui.view',NULL,0,'binary',false,'text/css','/web/assets/abc123/web.assets_web.min.css'),
              (5,'ir.ui.view',NULL,0,'binary',true,'text/plain','/web/assets/abc123/source.map'),
              (6,'ir.ui.view',NULL,0,'binary',true,'application/javascript','/web/content/contract.js'),
              (7,NULL,NULL,NULL,'binary',true,'text/css',NULL),
              (8,'ir.ui.view',NULL,0,'binary',true,'application/javascript','/web/assets/ab12/web.assets.min.js')
            ) t(id,res_model,res_field,res_id,type,public,mimetype,url)
        """))
        self.assertEqual(result, [True, False, False, False, False, False, False, True])

    def digest(self, body):
        # The changed text belongs to a user attachment, never a cache.
        return sql(self.database, """
            CREATE TEMP TABLE ir_attachment (id int,res_model text,res_field text,res_id int,
                type text,public boolean,mimetype text,url text,body text);
            INSERT INTO ir_attachment VALUES
                (1,'account.move',NULL,20,'binary',false,'text/plain',NULL,'""" + body + """');
            SELECT md5(string_agg(to_jsonb(t)::text,'' ORDER BY id)) FROM ir_attachment t
                WHERE NOT coalesce(""" + GENERATED_ASSET_CACHE + """,false);
        """)

    def test_business_attachment_content_remains_strict(self):
        self.assertNotEqual(self.digest('original'), self.digest('changed'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'COMMUNITY_AGRICULTURE_[A-Za-z0-9_]+', args.database)
    CacheContractCase.database = args.database
    unittest.main(argv=['attachment-cache'], verbosity=2)
