"""Compare real catalogue assignment edits, refusals and protected document uses with rollback."""
from odoo import Command
from odoo.exceptions import AccessError, ValidationError

from probe_cerro_fruit_schema import MODELS


class Undo(Exception):
    pass


def outcome(env, fn):
    try:
        with env.cr.savepoint():
            fn()
            env.flush_all()
            raise Undo()
    except Undo:
        return 'allowed'
    except (AccessError, ValidationError) as error:
        return type(error).__name__


def exercise(env):
    actor=env['res.users'].browse(6)
    scopes=sorted(actor.company_ids.ids)
    models={name:env[name].with_user(actor).with_context(allowed_company_ids=scopes) for name in MODELS}
    assert all(not model.env.su for model in models.values())
    result={}
    for name,model in models.items():
        records=model.search([],order='id')
        attempts={}
        for rec in records:
            for company in rec.company_ids:
                attempts[f'{rec.id}/{company.id}']=outcome(env,lambda r=rec,c=company:
                    r.write({'company_ids':[Command.unlink(c.id)]}))
        result[name]=attempts

    def create_catalogue():
        category,fruit_class,group,caliber=models.values()
        base=dict(name='Catálogo de comprobación',code='QA_CERRO_CATALOGO')
        original,other=scopes[:2]
        fixture=category.create(dict(base,company_id=original))
        assert fixture.company_ids.ids==[original]
        fixture.write({'company_ids':[Command.link(other)]})
        assert fixture.company_id.id==original and other in fixture.company_ids.ids
        child=fruit_class.create(dict(base,category_id=fixture.id,company_id=other))
        assert child.company_id.id==other and child.company_ids.ids==[other]
        parent=group.create(dict(base,company_id=original))
        fruit=caliber.create(dict(base,group_id=parent.id,company_id=original))
        fruit.write({'company_ids':[Command.link(other)]})
        assert other in parent.company_ids.ids

    result['create_and_share']=outcome(env,create_catalogue)
    env.cr.rollback()
    env.invalidate_all(flush=False)
    return result
