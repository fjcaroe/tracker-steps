import hashlib
from .models.profiles import APPS, owners


def post_init_hook(env):
    """Native ACLs owned by this module; no membership or existing ACL is changed."""
    for model in env['ir.model'].search([]):
        scope=owners(model.model)
        if not scope or model.model not in env or env[model.model]._abstract:continue
        auto=env[model.model]._auto
        for app in scope:
            for level in ('read','manager'):
                name='access_%s_%s_%s'%(app,level,hashlib.sha1(model.model.encode()).hexdigest()[:12])
                if env.ref('step_application_profiles.'+name,raise_if_not_found=False):continue
                manager=level=='manager' and auto
                acl=env['ir.model.access'].create({'name':'Steps %s %s %s'%(app,level,model.model),
                    'model_id':model.id,'group_id':env.ref('step_application_profiles.%s_%s'%(app,level)).id,
                    'perm_read':True,'perm_write':manager,'perm_create':manager,'perm_unlink':manager})
                env['ir.model.data'].create({'module':'step_application_profiles','name':name,
                    'model':'ir.model.access','res_id':acl.id,'noupdate':True})
