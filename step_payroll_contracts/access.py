"""Resolve existing payroll role identities without manufacturing engine groups."""
from odoo import _
from odoo.exceptions import UserError

ROLES={'user':('hr_payroll.group_hr_payroll_user','payroll.group_payroll_user'),
       'manager':('hr_payroll.group_hr_payroll_manager','payroll.group_payroll_manager')}


def payroll_role_group(env,role):
    groups=env['res.groups']
    for xmlid in ROLES[role]:
        record=env.ref(xmlid,raise_if_not_found=False)
        if record:
            if record._name!='res.groups':raise UserError(_('Invalid payroll role identity.'))
            groups|=record
    if len(groups)>1:raise UserError(_('Conflicting payroll role identities require audited adoption.'))
    return groups


def has_payroll_role(env,role):
    group=payroll_role_group(env,role)
    return bool(group and group in env.user.groups_id)
