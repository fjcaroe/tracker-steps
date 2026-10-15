from types import SimpleNamespace
from lxml import etree
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.exceptions import UserError
from odoo.addons.step_producer_contract_report.tests.test_report import ContractReportCase
from odoo.addons.step_producer_estimate_report.tests.test_report import EstimateReportCase

@tagged('post_install', '-at_install')
class PurchaseModeCase(TransactionCase):
    def contract(self):
        return ContractReportCase.sample(SimpleNamespace(env=self.env))

    def estimate(self):
        return EstimateReportCase.sample(SimpleNamespace(env=self.env))[0]

    def test_contract_modes_report_and_revision(self):
        c=self.contract()
        self.assertFalse(c.purchase_mode)
        total=c.amount_total
        for mode in ('firm','consignment'):
            c.purchase_mode=mode
            self.env.flush_all()
            rows=self.env['step.producer.contract.report'].search([('contract_id','=',c.id)])
            rows.invalidate_recordset()
            self.assertEqual(set(rows.mapped('purchase_mode')),{mode})
            group=rows.read_group([('id','in',rows.ids)],['amount_usd:sum'],['purchase_mode'])
            self.assertEqual(len(group),1)
            self.assertEqual(group[0]['purchase_mode'],mode)
            self.assertEqual(group[0]['amount_usd'],200)
            self.assertEqual(c.amount_total,total)
            rows.invalidate_recordset()
        c.action_confirm()
        with self.assertRaises(UserError):
            c.purchase_mode='firm'
        revision=c.browse(c.action_revise()['res_id'])
        self.assertEqual(revision.purchase_mode,'consignment')
        revision.purchase_mode='firm'
        self.assertEqual(c.purchase_mode,'consignment')

    def test_estimate_modes_report_and_version(self):
        e=self.estimate()
        self.assertFalse(e.purchase_mode)
        for mode in ('firm','consignment'):
            e.purchase_mode=mode
            self.env.flush_all()
            rows=self.env['step.producer.estimate.report'].search([('estimate_id','=',e.id)])
            rows.invalidate_recordset()
            rows.invalidate_recordset()
            self.assertEqual(set(rows.mapped('purchase_mode')),{mode})
            group=rows.read_group([('id','in',rows.ids)],['export_kg:sum','amount_usd:sum'],['purchase_mode'])
            self.assertEqual(group[0]['purchase_mode'],mode)
            self.assertEqual(group[0]['export_kg'],100)
            self.assertEqual(group[0]['amount_usd'],200)
        e.action_validate_estimate();e.action_activate_estimate()
        with self.assertRaises(UserError):
            e.purchase_mode='firm'
        revision=e.browse(e.action_new_estimate_version()['res_id'])
        self.assertEqual(revision.purchase_mode,'consignment')
        revision.purchase_mode='firm'
        self.assertEqual(e.purchase_mode,'consignment')

    def test_forms_reports_and_company_rules(self):
        user=new_test_user(self.env,login='qa-t86-mode',groups='base.group_user',company_id=self.env.company.id,
            company_ids=[(6,0,self.env.company.ids)])
        for kind,doc in [('contract',self.contract()),('estimate',self.estimate())]:
            doc.purchase_mode='firm';self.env.flush_all()
            form=etree.fromstring(doc.with_user(user).get_view(view_type='form')['arch'].encode())
            self.assertTrue(form.xpath(".//field[@name='purchase_mode']"))
            report=self.env['step.producer.'+kind+'.report'].with_user(user)
            link='contract_id' if kind=='contract' else 'estimate_id'
            rows=report.search([(link,'=',doc.id)])
            self.assertTrue(rows)
            for typ in ('list','search','gantt'):
                view=self.env.ref('step_producer_'+kind+'_report.report_'+typ)
                arch=etree.fromstring(report.get_view(view_id=view.id,view_type=typ)['arch'].encode())
                self.assertTrue(arch.xpath(".//field[@name='purchase_mode']"))
            action=self.env.ref('step_producer_'+kind+'_report.report_action')
            menu=self.env.ref('step_producer_'+kind+'_report.report_menu')
            self.assertEqual(menu.action,action)
            self.assertIn(menu.id,self.env['ir.ui.menu'].with_user(user)._visible_menu_ids())
            other=self.env['res.company'].create({'name':'QA mode isolation '+kind})
            outsider=new_test_user(self.env,login='qa-mode-other-'+kind,groups='base.group_user',
                company_id=other.id,company_ids=[(6,0,other.ids)])
            self.assertFalse(report.with_user(outsider).with_context(allowed_company_ids=other.ids).search([('id','in',rows.ids)]))

    def test_history_can_be_classified_without_repricing(self):
        c=self.contract();c.action_confirm();before=(c.amount_total,c.quantity_total,c.scheduled_total)
        c.purchase_mode='firm'
        self.assertEqual((c.amount_total,c.quantity_total,c.scheduled_total),before)
        self.assertFalse(c.accounting_move_id)
        e=self.estimate();e.action_validate_estimate();e.action_activate_estimate()
        e.purchase_mode='consignment'
        self.assertEqual(e.export_kg_total,100)
