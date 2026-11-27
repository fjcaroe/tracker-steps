from odoo.exceptions import ValidationError
from odoo.addons.step_cerro_studio_adoption.ownership import adopt

OWNER = 'step_cerro_export_payment_concepts'
SOURCE = 'step_export'
STUDIO = 'odoo_studio_step_exp_190b5787-3bb7-4f94-b7cb-b1b9a20d75cd'
FIELDS = ('name','company_id','sequence','code','notes','date','id','display_name',
          'create_uid','create_date','write_uid','write_date',
          'standard_cost_per_kg','standard_cost_per_box','standard_cost_per_pallet')
GRANTS = (
    (SOURCE,'access_step_export_payment_concept_user',(True,True,True,False)),
    ('step_application_profiles','access_export_read_a85a49cd7f5c',(True,False,False,False)),
    ('step_application_profiles','access_export_manager_a85a49cd7f5c',(True,True,True,True)),
)


def bindings():
    yield SOURCE,'model_step_export_payment_concept','ir.model'
    for name in FIELDS:
        yield SOURCE,'field_step_export_payment_concept__'+name,'ir.model.fields'
    for suffix in ('product_template','product_product'):
        yield SOURCE,'field_'+suffix+'__step_export_payment_concept_id','ir.model.fields'
    for source,name,_ in GRANTS:
        yield source,name,'ir.model.access'


def adopt_concepts(env):
    if env['ir.module.module'].search_count([('name','=',SOURCE),('state','in',['installed','to install','to upgrade'])]):
        raise ValidationError('El catálogo independiente de Cerro requiere el perfil Community de exportación.')
    updates=[]
    for source,name,model in bindings():
        record=env.ref(source+'.'+name)
        current=env.ref(OWNER+'.'+name,raise_if_not_found=False)
        if record._name!=model or (current and current!=record):
            raise ValidationError('La identidad original del catálogo cambió: '+name)
        updates.append(dict(xml_id=OWNER+'.'+name,record=record,noupdate=True))
    env['ir.model.data']._update_xmlids(updates)
    adopt(env,OWNER,__file__,{'export_payment_concepts':STUDIO})


def verify_concepts(env):
    for source,name,_ in bindings():
        if env.ref(source+'.'+name)!=env.ref(OWNER+'.'+name):
            raise ValidationError('El catálogo usa una referencia distinta del original: '+name)
    for source,name,flags in GRANTS:
        acl=env.ref(source+'.'+name)
        if not acl.active or (acl.perm_read,acl.perm_write,acl.perm_create,acl.perm_unlink)!=flags:
            raise ValidationError('Los permisos del catálogo cambiaron: '+name)
    if env.ref(OWNER+'.export_payment_concepts')!=env.ref('studio_customization.'+STUDIO):
        raise ValidationError('La vista de conceptos debe conservar su identidad original.')
