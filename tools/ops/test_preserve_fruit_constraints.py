import unittest
from preserve_fruit_constraints import retained_spec,CANONICAL


class CanonicalConstraintCase(unittest.TestCase):
    def test_preserves_only_existing_validated_canonical_relationship(self):
        key=('stock_picking','fruit_category_id')
        spec=('step_packing_fruit_category','id','set null','model','module')
        self.assertEqual(retained_spec(key,spec,[(CANONICAL,True)]),(CANONICAL,*spec[1:]))
        self.assertEqual(retained_spec(key,spec,[]),spec)
        self.assertEqual(retained_spec(key,spec,[('step_packing_fruit_category',True)]),spec)
        self.assertEqual(retained_spec(('other','field'),spec,[(CANONICAL,True)]),spec)

    def test_rejects_weakened_or_ambiguous_constraints(self):
        key=('stock_picking','fruit_category_id')
        spec=('step_packing_fruit_category','id','set null','model','module')
        for existing in ([(CANONICAL,False)],[(CANONICAL,True),('step_packing_fruit_category',True)]):
            with self.assertRaises(AssertionError):retained_spec(key,spec,existing)
        canonical=(CANONICAL,*spec[1:])
        self.assertEqual(retained_spec(key,canonical,[(CANONICAL,True)]),canonical)


if __name__=='__main__':unittest.main()
