"""Real engine/ORM and actual supplier execution; only the HTTP context is local."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from odoo import Command, http
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
from odoo.addons.step_payroll_contracts.history import stored_line_total
from odoo.addons.step_hr_previred.tools import previred
from odoo.addons.l10n_cl_simpledigital_payroll.controllers import previred_txt as vendor
from ..controllers import previred_secure as secured
from ..models.previred_engine import SimpleDigitalAdapter


@tagged('post_install','-at_install')
class CommunityBridgeContracts(PayrollContractMixin,TransactionCase):
    payroll_group='payroll.group_payroll_manager'

    def exporter(self):
        self.scope.user.sudo().write({'groups_id':[Command.link(self.env.ref('step_hr_previred.group_previred_generate').id)]})
        return SimpleNamespace(env=self.scope,make_response=lambda data,headers=None,**kw:http.Response(data,headers=headers))

    def test_community_manager_guard_uses_real_role(self):
        with patch.object(secured,'request',self.exporter()):
            secured.SecuredPreviredExportController()._previred_guard('092026',str(self.company.id))
        self.assertFalse(self.scope.su)

    def test_community_foreign_and_hidden_salary_are_denied(self):
        slip=self.slip();slip.compute_sheet();self.env.flush_all()
        period=slip.date_from.strftime('%m%Y')
        request=self.exporter()
        with patch.object(secured,'request',request):
            with self.assertRaises(AccessError):
                secured.SecuredPreviredExportController()._previred_guard(period,str(self.env.company.id))
        self.env['ir.rule'].create({'name':'Private hidden corporate salary',
            'model_id':self.env['ir.model']._get_id('hr.payslip'),
            'domain_force':repr([('id','!=',slip.id)]),'perm_read':True,
            'perm_create':False,'perm_write':False,'perm_unlink':False})
        # The actual vendor also selects partial periods, including this month-to-date slip.
        with patch.object(secured,'request',request):
            with self.assertRaises(AccessError):
                secured.SecuredPreviredExportController()._previred_guard(period,str(self.company.id))

    def test_community_real_vendor_empty_is_an_error(self):
        request=self.exporter()
        with patch.object(http,'request',request),patch.object(vendor,'request',request):
            rows,issues=SimpleDigitalAdapter.generate_rows(self.scope,self.company,date(2026,9,1),date(2026,9,30),self.scope['hr.payslip'])
        self.assertEqual(rows,[])
        self.assertTrue(any(issue.code=='engine_empty' and issue.is_error for issue in issues))

    def closed_imported_zero(self,code):
        (self.structure.rule_ids-self.rule).unlink()
        self.rule.write({'code':code,'amount_python_compute':'result = 0'})
        slip=self.slip();slip.compute_sheet();self.env.flush_all()
        line=slip.line_ids
        # Import a legacy draft override, then close normally. Never derive a paid value.
        self.env.cr.execute('UPDATE hr_payslip_line SET amount=100,total=0 WHERE id=%s',(line.id,))
        line.invalidate_recordset();slip.state='done';self.env.flush_all()
        return slip,line

    def enrich(self,slip,afp):
        row=['0']*previred.FIELD_COUNT
        row[previred.F_WORKER_TYPE-1]='3';row[previred.F_AFP_CONTRIBUTION-1]=str(afp)
        record=previred.PreviredRecord(rut='',dv='',principal=row)
        dataset=previred.Dataset(period=slip.date_from.strftime('%Y%m'),spec_version='98')
        self.scope['step.previred.extractor']._enrich_official_fields(record,slip,dataset)
        return row

    def test_community_closed_zero_total_is_authoritative(self):
        slip,line=self.closed_imported_zero('AFP')
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE id=%s',(line.id,));before=self.env.cr.fetchone()
        self.assertEqual(stored_line_total(line),0)
        self.assertEqual(self.enrich(slip,100)[previred.F_AFP_CONTRIBUTION-1],'0')
        self.env.cr.execute('SELECT to_jsonb(l) FROM hr_payslip_line l WHERE id=%s',(line.id,));self.assertEqual(self.env.cr.fetchone(),before)

    def test_community_missing_total_is_rejected(self):
        slip,line=self.closed_imported_zero('AFP')
        with self.assertRaises(UserError),self.env.cr.savepoint():
            self.env.cr.execute('UPDATE hr_payslip_line SET total=NULL WHERE id=%s',(line.id,))
            stored_line_total(line)
        self.env.cr.execute('SELECT total FROM hr_payslip_line WHERE id=%s',(line.id,));self.assertEqual(self.env.cr.fetchone()[0],0)

    def test_community_employer_zero_does_not_reconstruct_deduction(self):
        slip,line=self.closed_imported_zero('AFP_EMP')
        self.assertEqual(self.enrich(slip,12)[previred.F_AFP_CONTRIBUTION-1],'12')
        self.env.cr.execute('SELECT amount,total FROM hr_payslip_line WHERE id=%s',(line.id,));self.assertEqual(self.env.cr.fetchone(),(100,0))

    def test_community_paid_state_keeps_original_totals(self):
        slip=self.slip();slip.compute_sheet();self.env.flush_all()
        before=stored_line_total(slip.line_ids)
        slip.write({'state':'paid','paid':True});self.env.flush_all()
        self.contract.wage=1200000
        self.assertEqual(stored_line_total(slip.line_ids),before)
        self.assertIn('paid',self.env.ref('step_hr_previred_simpledigital.profile_simpledigital_v98').state_list())
        with self.assertRaises(UserError):slip.compute_sheet()
        if self.env['ir.module.module'].search_count([('name','=','payroll'),('state','=','installed')]):
            from odoo.addons.step_payroll_oca_api.models.payroll import preserve_paid_state
            with self.assertRaises(UserError):preserve_paid_state(slip)
        self.assertEqual(stored_line_total(slip.line_ids),before)
