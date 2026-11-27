"""Preserve the same producer/farm inverse and the original company rule."""
import ast

from odoo.exceptions import ValidationError

ORIGINAL = 'step_producers'
OWNER = 'step_agriculture_farm_directory'
RULE = 'rule_step_producer_fundo_company'
NAMES = ('field_res_partner__step_export_fundo_ids', 'field_res_users__step_export_fundo_ids', RULE)
SINGLE = "[('company_id', 'in', company_ids)]"
SHARED = '[("company_ids", "in", company_ids)]'


def rule_mode(rule):
    expression = ast.dump(ast.parse(rule.domain_force, mode='eval'), include_attributes=False)
    for name, value in [('single', SINGLE), ('shared', SHARED)]:
        if expression == ast.dump(ast.parse(value, mode='eval'), include_attributes=False):
            return name
    raise ValidationError('Cambió el dominio de empresas de la regla original de fundos.')


def mirror(env, namespace, name, record):
    xml_id = namespace + '.' + name
    current = env.ref(xml_id, raise_if_not_found=False)
    if current and current != record:
        raise ValidationError('Conflicto en el identificador del directorio: ' + xml_id)
    if not current:
        env['ir.model.data']._update_xmlids([{'xml_id': xml_id, 'record': record, 'noupdate': True}])


def pre_init_hook(env):
    for name in NAMES[:-1]:
        field = env.ref(ORIGINAL + '.' + name, raise_if_not_found=False)
        if not field:
            continue
        model = 'res.partner' if name.startswith('field_res_partner__') else 'res.users'
        if (field._name != 'ir.model.fields' or field.model != model or field.name != 'step_export_fundo_ids'
                or field.ttype != 'one2many' or field.relation != 'step.fundo'):
            raise ValidationError('La relación original entre productor y fundos cambió.')
        if model == 'res.partner' and field.relation_field != 'partner_id':
            raise ValidationError('Cambió el inverso de la relación original del productor.')
        if model == 'res.users' and field.related != 'partner_id.step_export_fundo_ids':
            raise ValidationError('Cambió la delegación original del campo de usuario.')
        mirror(env, OWNER, name, field)
    rule = env.ref(ORIGINAL + '.' + RULE, raise_if_not_found=False)
    if rule:
        if (rule._name != 'ir.rule' or rule.model_id.model != 'step.fundo' or not rule.active
                or rule.groups != env.ref('base.group_user')
                or not all((rule.perm_read, rule.perm_write, rule.perm_create, rule.perm_unlink))):
            raise ValidationError('La regla original de fundos tiene otra configuración de acceso.')
        rule_mode(rule)
        mirror(env, OWNER, RULE, rule)


def post_init_hook(env):
    rule = env.ref(OWNER + '.' + RULE, raise_if_not_found=False)
    if not rule:
        rule = env['ir.rule'].create({'name': 'Productores: fundos por empresa',
            'model_id': env['ir.model']._get_id('step.fundo'), 'domain_force': SINGLE,
            'groups': [(4, env.ref('base.group_user').id)]})
        mirror(env, OWNER, RULE, rule)
    for name in NAMES:
        mirror(env, ORIGINAL, name, env.ref(OWNER + '.' + name))
    mirror(env, 'step_export', NAMES[0], env.ref(OWNER + '.' + NAMES[0]))
