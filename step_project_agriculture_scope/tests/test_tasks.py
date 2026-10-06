from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install','-at_install')
class TestTaskScope(TransactionCase):
    def test_generic_task_needs_no_crop_and_schema_is_nullable(self):
        task=self.env['project.task'].create({'name':'Consulta de soporte QA'})
        self.assertFalse(task.variedad_id);self.assertFalse(task.grupo_variedad_id)
        self.env.cr.execute("SELECT is_nullable FROM information_schema.columns WHERE table_name='project_task' AND column_name IN ('variedad_id','grupo_variedad_id')")
        self.assertEqual(self.env.cr.fetchall(),[('YES',),('YES',)])

    def test_agricultural_task_still_requires_real_classification(self):
        crop=self.env['step.especie'].new({'name':'Especie QA'})
        center=self.env['account.analytic.account'].new({'name':'Centro QA','especie_id':crop})
        task=self.env['project.task'].new({'name':'Labor QA','cost_id':center})
        self.assertTrue(task.step_agricultural_task)
        with self.assertRaises(ValidationError):task._check_agricultural_classification()
