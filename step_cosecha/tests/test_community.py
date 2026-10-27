from odoo.tests import TransactionCase,tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import UserError

@tagged('post_install','-at_install')
class HarvestCommunityCase(TransactionCase):
    def test_no_unknown_relations_in_harvest_models(self):
        models=self.env['ir.model'].search([('model','=like','step.cosecha.%')])
        self.assertTrue(models)
        for meta in models:
            for name,field in self.env[meta.model]._fields.items():
                if field.relational:
                    self.assertNotEqual(field.comodel_name,'_unknown',(meta.model,name))
                    self.assertIn(field.comodel_name,self.env.registry.models)

    def test_preserve_custom_sequence_parameters_on_repeated_upgrade_protection(self):
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('harvest_pre',Path(__file__).parents[1]/'migrations/18.0.1.7.0/pre-migration.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        seq=self.env.ref('step_cosecha.seq_step_cosecha_propio')
        seq.write({'prefix':'PRIVATE/','padding':9,'number_increment':3})
        before=seq.read(['prefix','padding','number_increment','number_next','company_id'])
        migration.migrate(self.env.cr,'18.0.1.6.1');migration.migrate(self.env.cr,'18.0.1.6.1')
        seq.invalidate_recordset()
        self.assertEqual(seq.read(['prefix','padding','number_increment','number_next','company_id']),before)
        data=self.env['ir.model.data'].search([('module','=','step_cosecha'),('name','=','seq_step_cosecha_propio')])
        self.assertTrue(data.noupdate)

    def test_portal_denied_and_posted_harvest_guard(self):
        portal=new_test_user(self.env,login='private_harvest_portal',groups='base.group_portal')
        for model in ('step.cosecha.registry','step.cosecha.registry.line','step.history.cosecha'):
            self.assertFalse(self.env[model].with_user(portal).has_access('read'))
        harvest=self.env['step.cosecha.registry'].with_context(default_type_tarea='contratista').create({'name':'Private protected harvest','product_uom_id':self.env.ref('uom.product_uom_kgm').id})
        harvest.write({'state':'cont'})
        with self.assertRaises(UserError):harvest.unlink()
