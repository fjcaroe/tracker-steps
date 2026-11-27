"""Read all four historical fruit directories through the original Cerro user's record rules."""
import hashlib
import json

MODELS = ('step.management.fruit.category','step.management.fruit.class',
          'step.management.caliber.group','step.management.fruit.caliber')


def capture(env):
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    actor=env['res.users'].browse(6)
    groups=[[company] for company in sorted(actor.company_ids.ids)] + [sorted(actor.company_ids.ids)]
    result={}
    for name in MODELS:
        model=env[name].with_user(actor)
        assert not model.env.su
        model.check_access('read')
        partitions={}
        for companies in groups:
            records=model.with_context(allowed_company_ids=companies).search([],order='id')
            ids=[row['id'] for row in records.read(['id'])]
            partitions[','.join(map(str,companies))]=ids
        result[name]=partitions
    env.cr.rollback()
    return result
