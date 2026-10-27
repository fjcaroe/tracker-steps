"""Native operations checks appended to the producer verifier; rollback only."""
from odoo.addons.step_operations_core.ownership import RECORDS

try:
    for name in RECORDS:
        assert env.ref('step_hr.' + name) == env.ref('step_operations_core.' + name)
    if MODE == 'community':
        assert not env['ir.module.module'].search_count([('state', '=', 'installed'), ('license', '=', 'OEEL-1')])
    # Preserve existing business profiles. Find one authorized for the operation;
    # no group grants and no credentials are changed for this verification.
    candidates = env['res.users'].search([('active', '=', True), ('share', '=', False),
        ('company_ids', 'in', company.ids), ('id', '>', 1)], order='id')
    operator = candidates.filtered(lambda u: env['step.hrs.machinery'].with_user(u).has_access('create') and
                                   u.has_group('fleet.fleet_group_user'))[:1]
    if MODE == 'community':
        operator = env.ref('base.user_admin')
    assert operator, 'No authorized existing machinery operator'
    operations = api.Environment(env.cr, operator.id, dict(env.context, allowed_company_ids=company.ids), su=False)
    assert not operations.su
    usage_model = operations['step.hrs.machinery']
    spec = {'name': {}, 'ot_number': {}, 'folio': {}, 'date': {}, 'state': {}}
    usage = usage_model.web_save({'date': '2026-10-27', 'folio': 'COMMUNITY-OPS'}, spec)
    assert usage[0]['ot_number'] and usage[0]['name']
    usage_model.get_view(operations.ref('step_machinery.view_step_hrs_machinery_form').id, 'form')
    operations['fleet.vehicle'].get_view(operations.ref('step_operations_core.step_view_fleet_vehicle_form').id, 'form')
    tasks = operations['project.task']
    task_user = candidates.filtered(lambda u: tasks.with_user(u).has_access('create'))[:1]
    if MODE == 'community':
        task_user = operator
    assert task_user, 'No authorized existing project task user'
    with Form(tasks.with_user(task_user), view='step_hr.step_project_task_view_inherit') as task:
        task.name = 'Private Community operational task'
        task.num_op = 'COMMUNITY-OPS'
    assert task.record.id and not task.record.variedad_id
    print('OPERATIONS_NATIVE_OK ' + json.dumps({'uid': operator.id, 'task_uid': task_user.id,
        'company_id': company.id, 'su': False, 'web_save': True, 'task_form': True,
        'legacy_xmlids': len(RECORDS)}))
finally:
    env.cr.rollback()
