"""Compare fields, backing providers and action buttons of the six remaining agricultural screens."""
from lxml import etree


VIEWS=(5187,5244,5245,5193,5189,5194)


def capture(env):
    actor=env['res.users'].browse(6)
    context={'allowed_company_ids':actor.company_ids.ids,'lang':'en_US'}
    out={}
    for pk in VIEWS:
        view=env['ir.ui.view'].browse(pk)
        field_refs={}
        buttons={}
        key=str(pk)
        if view.model not in env:
            out[key]=dict(model=view.model,model_available=False)
            continue
        model=env[view.model].with_user(actor).with_context(**context)
        res=model.get_views([(view.inherit_id.id,view.type)],options={'toolbar':True,'load_filters':True})
        xml=etree.fromstring(res['views'][view.type]['arch'].encode())
        for tag in xml.xpath('.//field[@name] | .//button[@name and @type="object"]'):
            owner=view.model
            for ancestor in reversed(list(tag.iterancestors('field'))):
                if owner not in env:
                    break
                nested=env[owner]._fields.get(ancestor.get('name'))
                if not nested or not nested.comodel_name:
                    owner=None
                    break
                owner=nested.comodel_name
            field=tag.get('name')
            ident=str(owner)+'.'+field
            if tag.tag=='button':
                buttons[ident]=bool(owner and owner in env and hasattr(env[owner],field))
                continue
            descriptor=env[owner]._fields.get(field) if owner and owner in env else None
            if descriptor:
                field_refs[ident]=dict(model=owner,name=field,ttype=descriptor.type,stored=descriptor.store,
                                       comodel=descriptor.comodel_name,related=descriptor.related)
            else:
                field_refs[ident]=dict(model=owner,name=field,absent=True)
        out[key]=dict(model=view.model,model_available=True,fields=field_refs,buttons=buttons)
    env.cr.rollback()
    return out
