"""Check the SyS HR fields and exercise ordinary ORM access in a disposable restore."""
import hashlib
import json
import re
from uuid import uuid4

from lxml import etree
from odoo import fields
from odoo.exceptions import AccessError


EMPLOYEE = ('x_studio_categora_empleado', 'x_studio_tipo_contrato')
CONTRIBUTION = 'x_studio_cotizacin_obligatoria_adicional'


def snapshot(env):
    cr = env.cr
    assert re.fullmatch(r'(?:(?:MANAGEMENT_QA_SYS|MANAGEMENT_QA_CERRO|COMMUNITY)_HR_FIELDS_'
                        r'|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', cr.dbname)
    cr.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' "
               "AND column_name=ANY(%s)", [[*EMPLOYEE, CONTRIBUTION]])
    columns = cr.fetchall()
    values = {}
    for table in ('hr_employee', 'hr_contract'):
        names = [name for t, name in columns if t == table]
        projection = ','.join(['id', *sorted(names)])
        cr.execute(f'SELECT {projection} FROM {table} ORDER BY id')
        rows = cr.fetchall()
        values[table] = {'rows': len(rows), 'columns': sorted(names),
                         'digest': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
    cr.execute("""SELECT d.module,d.name,d.model,d.res_id FROM ir_model_data d
                  JOIN ir_model_fields f ON d.res_id=f.id AND d.model='ir.model.fields'
                  WHERE f.name=ANY(%s) ORDER BY d.id""", [[*EMPLOYEE, CONTRIBUTION]])
    aliases = cr.fetchall()
    cr.execute("""SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint
                  WHERE conrelid='hr_employee'::regclass AND
                  (pg_get_constraintdef(oid) LIKE %s OR pg_get_constraintdef(oid) LIKE %s) ORDER BY conname""",
               ['%' + name + '%' for name in EMPLOYEE])
    foreign_keys = cr.fetchall()
    cr.execute("""SELECT a.id,a.model_id,a.group_id,a.active,a.perm_read,a.perm_write,a.perm_create,a.perm_unlink
                  FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id WHERE m.model=ANY(%s) ORDER BY a.id""",
               [['hr.contract','hr.employee','hr.contract.type','hr.employee.category']])
    access = cr.fetchall()
    cr.execute("""SELECT d.name,v.id,v.inherit_id,v.active,v.priority FROM ir_model_data d
                  JOIN ir_ui_view v ON v.id=d.res_id WHERE d.model='ir.ui.view' AND d.module='studio_customization'
                  AND d.name=ANY(%s) ORDER BY d.id""",
               [['odoo_studio_hr_emplo_aa91d14a-7c7f-466b-b42c-8014ce64e71f',
                 'odoo_studio_hr_contr_7a505bc3-cc15-497b-b648-378673a9915e']])
    return {'values':values, 'aliases':aliases, 'foreign_keys':foreign_keys, 'access':access, 'views':cr.fetchall()}


def exercise(env, baseline):
    from odoo.addons.step_sys_hr_fields.hooks import FIELDS

    before = snapshot(env)
    assert [list(row) for row in before['access']] == baseline['access']
    assert [list(row) for row in before['views']] == baseline['views']
    if baseline['values']['hr_contract']['columns']:
        assert before['values'] == baseline['values']
        assert [list(r) for r in before['foreign_keys']] == baseline['foreign_keys']
        assert set(map(tuple, baseline['aliases'])) <= set(before['aliases'])
    for model, name, relation, alias in FIELDS:
        field = env[model]._fields[name]
        assert not field.manual and field.store and not field.required and not field.readonly
        reflected = env['ir.model.fields']._get(model,name)
        assert reflected.state == 'base'
        assert env.ref('step_sys_hr_fields.field_' + model.replace('.', '_') + '__' + name) == reflected
        if baseline['values']['hr_contract']['columns']:
            assert env.ref('studio_customization.' + alias) == reflected
        if relation:
            assert field.comodel_name == relation and field.ondelete == 'set null'
    company = env['res.company'].browse(37) if baseline['views'] else env.company
    managers = env['res.users'].search([('active','=',True),('share','=',False),('company_ids','in',[company.id])])
    actor = next(user for user in managers.sorted(lambda u: (u.id != 2, u.id))
                 if user.id != 1 and user.has_group('hr.group_hr_manager'))
    staff = env['hr.employee'].with_user(actor).with_context(allowed_company_ids=[company.id], tracking_disable=True)
    assert not staff.env.su and staff.env.company == company
    forms = {}
    migrated_views = env['ir.module.module'].search([('name','=','step_sys_hr_simpledigital_views'),
                                                     ('state','=','installed')])
    for model, kind, xmlid, names in (
            ('hr.employee', 'list', 'hr.view_employee_tree', EMPLOYEE),
            ('hr.contract', 'form', 'hr_contract.hr_contract_view_form', [CONTRIBUTION])):
        rendered = staff.env[model].get_view(view_id=env.ref(xmlid).id, view_type=kind)
        arch = etree.fromstring(rendered['arch'].encode())
        forms[model] = [name for name in names if arch.xpath('.//field[@name=$name]', name=name)]
        if migrated_views:
            assert all(len(arch.xpath('.//field[@name=$name]', name=name)) == 1 for name in names)
            if model == 'hr.contract':
                assert arch.xpath('.//page[@name="AFP"]//field[@name=$n and @widget="percentage"]',n=CONTRIBUTION)
    if migrated_views and baseline['views']:
        from odoo.addons.step_sys_hr_simpledigital_views.hooks import MODULE, VIEWS
        for name, old, *_ in VIEWS:
            assert env.ref(MODULE + '.' + name) == env.ref('studio_customization.' + old)
    tag = 'STEPS_PRIVATE_' + uuid4().hex
    try:
        cat = staff.env['hr.employee.category'].search([],limit=1) or staff.env['hr.employee.category'].create({'name':tag})
        kind = staff.env['hr.contract.type'].search([],limit=1) or staff.env['hr.contract.type'].create({'name':tag})
        employee = staff.create({'name':tag, 'company_id':company.id, EMPLOYEE[0]:cat.id, EMPLOYEE[1]:kind.id})
        contract = staff.env['hr.contract'].create({'name':tag, 'employee_id':employee.id, 'company_id':company.id,
            'date_start':fields.Date.today(), 'wage':1, CONTRIBUTION:1.25})
        assert employee[EMPLOYEE[0]] == cat and employee[EMPLOYEE[1]] == kind and contract[CONTRIBUTION] == 1.25
        employee.write(dict.fromkeys(EMPLOYEE,False))
        contract.write({CONTRIBUTION:0})
        assert all(not employee[name] for name in EMPLOYEE) and contract[CONTRIBUTION] == 0
        try:
            contract.with_user(env.ref('base.public_user')).write({CONTRIBUTION:1})
        except AccessError:
            pass
        else:
            raise AssertionError('Public user modified a payroll contract.')
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {'actor':actor.id, 'company':company.id, 'visible':forms, 'relations':2,
            'original_roles_enforced':True,'original_rows_preserved':True,'fixtures_rolled_back':True}
