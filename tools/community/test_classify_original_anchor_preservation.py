"""Pure preservation classifications and readonly query contracts, no database."""
import json
import unittest

import classify_original_anchor_preservation as classify
from original_anchor_readonly_sql import admit_statement


def row(ident, digest, *, asset=False, icon=False):
    return {'id':ident,'sha256':digest,'generated_asset_cache':asset,'menu_web_icon':icon,'technical_metadata':{}}


class AnchorPreservationClassificationCase(unittest.TestCase):
    def test_menu_subset_is_proven_separately_from_new_visibility_or_permissions(self):
        before=[{'menu_id':1,'gid':10},{'menu_id':2,'gid':20}]
        after=before+[{'menu_id':3,'gid':10},{'menu_id':1,'gid':99}]
        result=classify.classify_menu_rows(before,after,{1,2})
        self.assertTrue(result['all_original_pairs_preserved'])
        self.assertEqual(result['added_pairs_on_original_menus'],[{'menu_id':1,'gid':99}])
        self.assertEqual(result['added_pairs_on_new_menus'],[{'menu_id':3,'gid':10}])
        self.assertFalse(result['membership_equivalence_inferred'])
        self.assertFalse(result['classification_accepted'])
        result=classify.classify_menu_rows(before,after[1:],{1,2})
        self.assertFalse(result['all_original_pairs_preserved'])
        self.assertEqual(result['missing_original_pairs'],[before[0]])

    def test_original_history_mutations_are_not_accepted_as_technical_metadata(self):
        before=[row(1,'a'),row(2,'b',icon=True),row(3,'c',asset=True)]
        after=[row(1,'d'),row(2,'e',icon=True),row(3,'f',asset=True),row(4,'g',asset=True),row(5,'h')]
        result=classify.classify_history_rows(before,after,{1:['body'],2:['write_uid','write_date'],3:['checksum']})
        self.assertEqual([r['classification'] for r in result['original_rows_changed']],
            ['original_history_change_blocker','menu_icon_write_metadata_only','generated_asset_cache_candidate'])
        self.assertFalse(result['original_noncache_nonicon_rows_preserved'])
        self.assertEqual(result['new_rows_by_classification'],{'generated_asset_cache_candidate':1,'unclassified_history_row':1})
        self.assertFalse(result['technical_rows_equivalent_by_classification'])
        self.assertFalse(result['classification_accepted'])

    def test_icon_content_change_and_removed_history_remain_explicit(self):
        result=classify.classify_history_rows([row(1,'a',icon=True),row(2,'b')],[row(1,'c',icon=True)],{1:['checksum']})
        self.assertEqual(result['original_rows_changed'][0]['classification'],'menu_icon_content_or_other_metadata_requires_review')
        self.assertEqual(result['original_rows_removed'][0]['id'],2)
        self.assertFalse(result['all_original_rows_literal_exact'])
        self.assertFalse(result['original_noncache_nonicon_rows_preserved'])

    def test_detail_catalog_and_history_statements_pass_strict_readonly_boundary(self):
        statements=[]
        def sql(database,statement):
            admit_statement(statement);statements.append(statement)
            return '[]'
        self.assertEqual(classify.constraint_catalog(sql,'private',{('hr_salary_rule','field_fk')}),[])
        self.assertIn('pg_get_constraintdef',statements[-1])
        self.assertIn('k.confdeltype',statements[-1]);self.assertIn('k.condeferrable',statements[-1])
        for table in classify.HISTORY:self.assertEqual(classify.history_rows(sql,'private',table),[])
        with self.assertRaises(ValueError):classify.history_rows(sql,'private','unexpected')
        for statement in statements:
            self.assertTrue(statement.startswith('SELECT '));self.assertNotIn('nextval(',statement)


if __name__=='__main__':unittest.main()
