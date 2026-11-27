"""Keep the original companies, partner links and external identifiers."""
from odoo.exceptions import ValidationError
from odoo.addons.step_agriculture_farm_directory.hooks import OWNER as DIRECTORY, RULE, SHARED, SINGLE, rule_mode

LEGACY = 'step_agriculture_multicompany'
CURRENT = 'step_agriculture_shared_farms'
IDENTITIES = {
    'field_res_partner__step_contact_group_id': 'ir.model.fields',
    'field_res_users__step_contact_group_id': 'ir.model.fields',
    'field_step_fundo__company_ids': 'ir.model.fields',
    'field_step_fundo__step_contact_group_id': 'ir.model.fields',
    'model_inherit__step_fundo__step_shared_agriculture_master': 'ir.model.inherit',
    'model_step_shared_agriculture_master': 'ir.model',
}


def pre_init_hook(env):
    data = env['ir.model.data']
    for name, model in IDENTITIES.items():
        old = data.search([('module', '=', LEGACY), ('name', '=', name)])
        if not old:
            continue
        if old.model != model or not env[model].browse(old.res_id).exists():
            raise ValidationError('Identidad agrícola de origen incompatible: ' + name)
        for current in data.search([('module', '=', CURRENT), ('name', '=', name)]):
            if (current.model, current.res_id) != (model, old.res_id):
                raise ValidationError('Identidad agrícola de destino incompatible: ' + name)
        data._update_xmlids([{'xml_id': CURRENT + '.' + name, 'record': env[model].browse(old.res_id),
                              'noupdate': True}])


def post_init_hook(env):
    env.cr.execute('SELECT 1 FROM step_fundo WHERE company_id IS NULL LIMIT 1')
    if env.cr.fetchone():
        raise ValidationError('Existe un fundo sin empresa de origen que requiere revisión.')
    env.cr.execute('''INSERT INTO step_fundo_company_rel (master_id, company_id)
                      SELECT id, company_id FROM step_fundo ON CONFLICT DO NOTHING''')
    for name in IDENTITIES:
        old = env.ref(LEGACY + '.' + name, raise_if_not_found=False)
        current = env.ref(CURRENT + '.' + name, raise_if_not_found=False)
        if old and old != current:
            raise ValidationError('La identidad agrícola de origen cambió: ' + name)
    rule = env.ref(DIRECTORY + '.' + RULE)
    if rule_mode(rule) == 'single':
        rule.write({'domain_force': SHARED})
    env.invalidate_all()


def uninstall_hook(env):
    rule = env.ref(DIRECTORY + '.' + RULE, raise_if_not_found=False)
    if rule and rule_mode(rule) == 'shared':
        rule.write({'domain_force': SINGLE})
