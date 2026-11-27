"""Create a classified Steps project task, change its stage, and reopen it in an isolated QA transaction."""
from pathlib import Path

from lxml import etree
from odoo.exceptions import ValidationError
from probe_steps_accounting_history import fingerprint


def run(env):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_PROJECT_20261127U51P',
                                         'COMMUNITY_STEPS_PROJECT_20261127U51Q')
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    try:
        scope = env(user=2, su=False, context={'allowed_company_ids': [1], 'mail_notify_force_send': False})
        model = scope['project.task']
        menu = scope.ref('project.menu_project_management_all_tasks')
        assert menu.id in scope['ir.ui.menu']._visible_menu_ids() and menu.action.res_model == model._name
        original = model.search([('grupo_variedad_id', '!=', False), ('variedad_id', '!=', False)], order='id', limit=1)
        assert original and original.variedad_id.grupo_variedad_id == original.grupo_variedad_id
        project = original.project_id
        stages = scope['project.task.type'].search([('project_ids', 'in', project.ids)], order='sequence,id')
        assert stages
        original_stages = len(stages)
        if original_stages == 1:
            # The stored project has a single column. Add a temporary second column with the project manager's rights.
            stages |= scope['project.task.type'].create({'name': 'Control privado de etapa',
                                                        'project_ids': [(4, project.id)]})
        milestone = scope['project.milestone'].search([('project_id', '=', project.id)], order='id', limit=1)
        assert milestone
        fields = {key: {} for key in ('name', 'project_id', 'stage_id', 'milestone_id', 'user_ids',
                                     'cost_id', 'grupo_variedad_id', 'variedad_id', 'step_agricultural_task')}
        view = model.get_view(view_type='form')
        assert {'grupo_variedad_id', 'variedad_id', 'step_agricultural_task'} <= set(
            etree.fromstring(view['arch']).xpath('//field[not(ancestor::field)]/@name'))
        vals = {'name': 'Control privado de tarea', 'project_id': project.id, 'stage_id': stages[0].id,
                'milestone_id': milestone.id, 'grupo_variedad_id': original.grupo_variedad_id.id,
                'variedad_id': original.variedad_id.id}
        created, = model.web_save(vals, fields)
        task = model.browse(created['id'])
        assert task.milestone_id == milestone and task.variedad_id == original.variedad_id
        task.web_save({'stage_id': stages[1].id}, fields)
        reopened, = task.web_read(fields)
        assert task.stage_id == stages[1] and task in project.task_ids and task.project_id == project
        bad = scope['step.grupo.variedad'].search([('id', '!=', original.grupo_variedad_id.id)], order='id', limit=1)
        rejected = None
        if bad:
            try:
                with env.cr.savepoint():
                    task.write({'grupo_variedad_id': bad.id})
            except ValidationError:
                rejected = True
            else:
                rejected = False
        return {'operator': scope.uid, 'projects': len(project), 'original_stages': original_stages,
                'moved_to_second_stage': task.stage_id == stages[1],
                'linked_milestone': milestone.id, 'checked_alternate_group': bool(bad),
                'mismatched_variety_rejected': rejected,
                'fields': {key: fingerprint(value) for key, value in reopened.items() if key not in ('id','stage_id')}}
    finally:
        env.cr.rollback()
