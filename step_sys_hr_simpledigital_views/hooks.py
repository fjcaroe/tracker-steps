from odoo.exceptions import ValidationError


MODULE = 'step_sys_hr_simpledigital_views'
VIEWS = (
    ('employee_list', 'odoo_studio_hr_emplo_aa91d14a-7c7f-466b-b42c-8014ce64e71f',
     'hr.employee', 'hr.view_employee_tree', 'list'),
    ('contract_pension', 'odoo_studio_hr_contr_7a505bc3-cc15-497b-b648-378673a9915e',
     'hr.contract', 'hr_contract.hr_contract_view_form', 'form'),
)


def adopt_views(env):
    aliases = []
    for name, legacy, model, parent, view_type in VIEWS:
        original = env.ref('studio_customization.' + legacy, raise_if_not_found=False)
        candidate = env.ref(MODULE + '.' + name, raise_if_not_found=False)
        if candidate and candidate != original:
            raise ValidationError(f'El identificador de la vista {name} ya está ocupado.')
        if not original:
            continue
        if (original._name != 'ir.ui.view' or original.model != model or original.type != view_type
                or original.inherit_id != env.ref(parent) or original.mode != 'extension'):
            raise ValidationError(f'La vista de origen {name} cambió. Revise la migración.')
        aliases.append({'xml_id': MODULE + '.' + name, 'record': original, 'noupdate': False})
    if aliases:
        if len(aliases) != len(VIEWS):
            raise ValidationError('Las vistas originales de empleados y contratos están incompletas.')
        env['ir.model.data']._update_xmlids(aliases)
