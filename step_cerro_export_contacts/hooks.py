"""Bind the restored native market, contact fields and view to their existing records."""
from odoo.exceptions import ValidationError
from odoo.addons.step_cerro_studio_adoption.ownership import adopt

OWNER = 'step_cerro_export_contacts'
MARKET = 'step_producer_daily_estimate'
VIEW = 'odoo_studio_res_part_47b48baf-5b77-4192-857b-fed73051f3c7'
PARTNER_FIELDS = {
    'step_export': ('step_export_receiver',),
    'step_export_client_revision': (
        'step_export_carrier', 'step_export_consignee', 'step_export_notify',
        'step_export_forwarder', 'step_export_customs_agent'),
    'step_export_receiver_profile': (
        'step_export_market_id', 'step_export_generic_receiver',
        'step_export_default_notify_id', 'step_export_default_consignee_id'),
}
MARKET_FIELDS = ('name','code','abbreviation','active','display_name',
                 'id','create_uid','create_date','write_uid','write_date')


def bindings():
    yield MARKET, 'model_step_fruit_market', 'ir.model'
    for field in MARKET_FIELDS:
        yield MARKET, 'field_step_fruit_market__' + field, 'ir.model.fields'
    for key in ('market_read','market_manage'):
        yield MARKET, key, 'ir.model.access'
    for owner, fields in PARTNER_FIELDS.items():
        for field in fields:
            for tag in ('res_partner', 'res_users'):
                yield owner, 'field_' + tag + '__' + field, 'ir.model.fields'


def adopt_directory(env):
    # The full native suppliers are the alternate graph for this scoped product.
    full = set(PARTNER_FIELDS) | {MARKET}
    if env['ir.module.module'].search_count([('name','in',list(full)),
                                             ('state','in',['installed','to install','to upgrade'])]):
        raise ValidationError('El directorio separado requiere el perfil Community de Cerro.')
    updates = []
    for module, name, model in bindings():
        item = env.ref(module + '.' + name)
        current = env.ref(OWNER + '.' + name, raise_if_not_found=False)
        if item._name != model or (current and current != item):
            raise ValidationError('La referencia histórica cambió: ' + module + '.' + name)
        updates.append(dict(xml_id=OWNER + '.' + name, record=item, noupdate=True))
    env['ir.model.data']._update_xmlids(updates)
    adopt(env, OWNER, __file__, {'export_partners':VIEW})


def verify_directory(env):
    for module, name, model in bindings():
        if env.ref(OWNER + '.' + name) != env.ref(module + '.' + name):
            raise ValidationError('El directorio perdió la referencia original: ' + name)
    market = env.ref(OWNER + '.model_step_fruit_market')
    for key, group, expected in (('market_read','base.group_user',(True,False,False,False)),
                                 ('market_manage','stock.group_stock_manager',(True,True,True,True))):
        acl = env.ref(OWNER + '.' + key)
        if (not acl.active or acl.model_id != market or acl.group_id != env.ref(group)
                or (acl.perm_read,acl.perm_write,acl.perm_create,acl.perm_unlink) != expected):
            raise ValidationError('Los permisos del catálogo de mercados cambiaron: ' + key)
    if env.ref(OWNER + '.export_partners') != env.ref('studio_customization.' + VIEW):
        raise ValidationError('El directorio de Cerro usa una vista distinta de la original.')
