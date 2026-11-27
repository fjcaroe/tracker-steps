from odoo import _, api, fields, models
from odoo.exceptions import AccessError

ACCOUNT_GROUPS = 'account.group_account_readonly,account.group_account_invoice'
COMPUTED = ['total_due','total_overdue','followup_status','followup_line_id']


class FollowupLevel(models.Model):
    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'
    _order = 'delay asc'

    name = fields.Char('Description',required=True,translate=True)
    delay = fields.Integer('Due Days',required=True,help='The number of days after the due date of the invoice to wait before sending the reminder. Can be negative if you want to send the reminder before the invoice due date.')
    company_id = fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    activity_default_responsible_type=fields.Selection([
        ('followup','Follow-up Responsible'),('salesperson','Salesperson'),('account_manager','Account Manager')
    ],string='Responsible',required=True,default='followup',
        help='Determine who will be assigned to the activity:\n- Follow-up Responsible (default)\n- Salesperson: Sales Person defined on the invoice\n- Account Manager: Sales Person defined on the customer')

    @api.model_create_multi
    def create(self,vals_list):
        raise AccessError(_('La configuración de las etapas requiere el proveedor de gestión de recordatorios.'))

    def write(self,values):
        raise AccessError(_('La configuración de las etapas requiere el proveedor de gestión de recordatorios.'))

    def unlink(self):
        raise AccessError(_('La configuración de las etapas requiere el proveedor de gestión de recordatorios.'))


class Partner(models.Model):
    _inherit = 'res.partner'

    followup_responsible_id = fields.Many2one('res.users',string='Responsible',company_dependent=True,tracking=100,
        groups=ACCOUNT_GROUPS,copy=False,help='The responsible assigned to manual followup activities, if defined in the level.')
    followup_reminder_type = fields.Selection([('automatic','Automatic'),('manual','Manual')],string='Reminders',default='automatic')
    followup_next_action_date = fields.Date(string='Next reminder',company_dependent=True,copy=False,
        help='No follow-up action will be taken before this date.\n                Sending a reminder will set this date depending on the levels configuration, and you can change it manually.')
    followup_status = fields.Selection([('in_need_of_action','In need of action'),('with_overdue_invoices','With overdue invoices'),
        ('no_action_needed','No action needed')],string='Follow-up Status',compute='_compute_contact_followup',search='_search_contact_status',groups=ACCOUNT_GROUPS)
    followup_line_id = fields.Many2one('account_followup.followup.line',string='Follow-up Level',compute='_compute_contact_followup',
        inverse='_set_contact_followup_level',search='_search_contact_level',groups=ACCOUNT_GROUPS)
    total_due = fields.Monetary(string='Total Due',compute='_compute_contact_followup',groups=ACCOUNT_GROUPS)
    total_overdue = fields.Monetary(string='Total Overdue',compute='_compute_contact_followup',groups=ACCOUNT_GROUPS)

    def _open_receivables(self,all_contacts=False):
        company=self.env.company
        selected=self.env.companies.filtered(lambda other:other.parent_path.startswith(company.parent_path))
        return self.env['account.move.line'].search_fetch([
            ('partner_id','!=',False) if all_contacts else ('partner_id','in',self.ids),('company_id','in',selected.ids),('parent_state','=','posted'),
            ('account_id.account_type','=','asset_receivable'),('reconciled','=',False)
        ], ['partner_id','amount_residual','date_maturity','date','followup_line_id'])

    def _contact_levels(self):
        return self.env['account_followup.followup.line'].search([('company_id','=',self.env.company.id)],order='delay,id')

    @api.depends_context('company','allowed_company_ids','uid','tz')
    @api.depends('followup_next_action_date')
    def _compute_contact_followup(self):
        today=fields.Date.context_today(self)
        levels=self._contact_levels()
        first=levels[:1]
        by_contact=self._open_receivables().grouped('partner_id')
        for partner in self:
            lines=by_contact.get(partner,self.env['account.move.line'])
            amount=sum(lines.mapped('amount_residual'))
            overdue=0.0
            unpaid_overdue=False
            requires_action=False
            applied=[]
            for line in lines:
                age=(today-(line.date_maturity or line.date)).days
                if age>0:
                    overdue+=line.amount_residual
                    unpaid_overdue = unpaid_overdue or line.amount_residual>0
                previous=line.followup_line_id
                if previous:
                    applied.append(previous.delay)
                if first and line.amount_residual>0:
                    reached = age>previous.delay if previous else age>=first.delay
                    requires_action = requires_action or reached
            stage=levels.browse()
            if lines:
                stage=first
                if applied:
                    highest=max(applied)
                    stage=levels.filtered(lambda level:level.delay>highest)[:1] or levels[-1:]
            partner.followup_line_id=stage
            partner.total_due=amount
            partner.total_overdue=overdue
            if amount<=0 or not unpaid_overdue:
                partner.followup_status='no_action_needed'
            elif requires_action and (not partner.followup_next_action_date or partner.followup_next_action_date<=today):
                partner.followup_status='in_need_of_action'
            else:
                partner.followup_status='with_overdue_invoices'

    def _contacts_with_open_items(self):
        ids=self._open_receivables(all_contacts=True).partner_id.ids
        return self.with_context(active_test=False).search([('id','in',ids)])

    def _search_contact_status(self,operator,value):
        self.check_field_access_rights('read',['followup_status'])
        # Native contact searches apply a positive status filter to debtors.
        # Odoo's original negative-status filters leave the contact list unchanged.
        if operator not in ('=','in') or not value:
            return []
        wanted=[value] if operator=='=' else value
        matched=self._contacts_with_open_items().filtered(lambda partner:partner.followup_status in wanted)
        return [('id','in',matched.ids)]

    def _search_contact_level(self,operator,value):
        self.check_field_access_rights('read',['followup_line_id'])
        levels=self._contact_levels()
        label=operator in ('like','ilike','not like','not ilike','=ilike','=like')
        eligible=levels.filtered_domain([('name' if label else 'id',operator,value)])
        matched=self._contacts_with_open_items().filtered(lambda partner:partner.followup_line_id in eligible)
        return [('id','in',matched.ids)]

    def _set_contact_followup_level(self):
        for partner in self:
            stage=partner.followup_line_id
            levels=partner._contact_levels()
            if stage and stage not in levels:
                raise AccessError(_('La etapa debe pertenecer a la empresa activa.'))
            earlier=levels.filtered(lambda level:level.delay<stage.delay) if stage else levels.browse()
            partner._open_receivables().write({'followup_line_id':earlier[-1:].id or False})
        self.invalidate_recordset(COMPUTED,flush=False)


class MoveLine(models.Model):
    _inherit = 'account.move.line'

    followup_line_id=fields.Many2one('account_followup.followup.line',string='Follow-up Level',copy=False)

    @api.model_create_multi
    def create(self,values_list):
        lines=super().create(values_list)
        lines.partner_id.invalidate_recordset(COMPUTED,flush=False)
        return lines

    def write(self,values):
        tracked={'partner_id','company_id','parent_state','account_id','reconciled','amount_residual','date_maturity','date','followup_line_id'}
        if not tracked.intersection(values):
            return super().write(values)
        partners=self.partner_id
        result=super().write(values)
        (partners|self.partner_id).invalidate_recordset(COMPUTED,flush=False)
        return result

    def unlink(self):
        partners=self.partner_id
        result=super().unlink()
        partners.invalidate_recordset(COMPUTED,flush=False)
        return result
