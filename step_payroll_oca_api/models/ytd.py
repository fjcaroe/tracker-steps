"""Stored YTD on the real OCA engine, limited to the observed calendar-year scope."""
from collections import Counter, defaultdict
from datetime import date
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.addons.step_payroll_contracts.history import assert_mutable


class Company(models.Model):
    _inherit='res.company'
    ytd_reset_day=fields.Integer(default=1)
    ytd_reset_month=fields.Selection([(str(month),str(month)) for month in range(1,13)],default='1')


class Structure(models.Model):
    _inherit='hr.payroll.structure'
    ytd_computation=fields.Boolean(default=False)


class Payslip(models.Model):
    _inherit='hr.payslip'
    ytd_computation=fields.Boolean(related='struct_id.ytd_computation')

    def _step_ytd_previous_lines(self):
        self.ensure_one()
        # This explicitly supports calendar years only. Fiscal reset settings and
        # cross-contract accumulation require their own native parity evidence.
        if self.company_id.ytd_reset_day!=1 or self.company_id.ytd_reset_month!='1':
            raise UserError(_('Custom YTD resets require separate native parity validation.'))
        domain=[('employee_id','=',self.employee_id.id),('company_id','=',self.company_id.id),
            ('struct_id','=',self.struct_id.id),('date_from','>=',date(self.date_to.year,1,1)),
            ('date_to','<=',self.date_to),('state','in',('done','paid')),('credit_note','=',False),('id','!=',self.id)]
        slips=self.search(domain)
        if len(slips)!=self.sudo().search_count(domain):
            raise AccessError(_('The complete payroll history must be readable for YTD.'))
        if any(slip.contract_id!=self.contract_id for slip in slips):
            raise UserError(_('Cross-contract YTD requires a separately validated conversion.'))
        lines=slips.mapped('line_ids');lines.check_access('read')
        if len(lines)!=self.env['hr.payslip.line'].sudo().search_count([('slip_id','in',slips.ids)]):
            raise AccessError(_('The complete concept history must be readable for YTD.'))
        return lines

    def compute_sheet(self):
        assert_mutable(self)
        with self.env.cr.savepoint():
            previous={}
            for slip in self:
                if slip.ytd_computation:
                    if slip.credit_note or slip.date_from.year!=slip.date_to.year:
                        raise UserError(_('Credit notes and year-spanning YTD require separate validation.'))
                    previous[slip.id]=slip._step_ytd_previous_lines()
            result=super().compute_sheet()
            for slip in self:
                totals=defaultdict(float)
                if slip.ytd_computation:
                    if any(count>1 for count in Counter(slip.line_ids.mapped('code')).values()):
                        raise UserError(_('YTD for repeated concept lines requires separate validation.'))
                    for line in previous[slip.id]:totals[line.code]+=line.total
                for line in slip.line_ids:
                    line.ytd=totals[line.code]+line.total
            return result


class Line(models.Model):
    _inherit='hr.payslip.line'
    # Deliberately not computed on read: original closed values remain authoritative.
    ytd=fields.Monetary(currency_field='currency_id',readonly=True,copy=False)
