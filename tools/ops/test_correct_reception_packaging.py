"""Synthetic offline checks for destination and explicit packaging-repair scope."""
import copy
import unittest
from correct_reception_packaging import validate_plan


def fixture():
    names=['SYNTHETIC/'+str(n) for n in range(14)]
    return {'ticket':241,'database':'CERRO_EL_PLOMO','user_id':8,'company_id':98,
        'requested_receipts':names,'missing_receipts':names[2:],
        'old_packaging':{'id':91},'new_packaging':{'id':92},
        'receipts':[{'id':n+1,'name':names[n],'move_ids':[n+1],
                     'tags':[{'id':n+1,'row_id':n+1}]} for n in range(2)]}


class ScopeTests(unittest.TestCase):
    def test_complete_scope_with_explicit_missing_references(self):
        validate_plan(fixture())

    def test_cannot_change_ticket_destination_or_use_superuser(self):
        for key,value in [('ticket',240),('database','LAB_TAREAS'),('user_id',1)]:
            plan=fixture();plan[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_plan(plan)

    def test_no_silent_omission_duplicate_or_ambiguous_reference(self):
        for case in ('missing','duplicate_tag','duplicate_receipt','overlap','operation'):
            plan=copy.deepcopy(fixture())
            if case=='missing':plan['missing_receipts'].pop()
            elif case=='duplicate_tag':plan['receipts'][1]['tags'][0]['id']=1
            elif case=='duplicate_receipt':plan['receipts'][1]['id']=1
            elif case=='overlap':plan['missing_receipts'].append(plan['receipts'][0]['name'])
            else:plan['receipts'][0]['move_ids']=[False]
            with self.subTest(case=case),self.assertRaises(ValueError):validate_plan(plan)


if __name__=='__main__':unittest.main()
