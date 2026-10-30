from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_validated_work_entries(self):
        validated = self.filtered(lambda entry: entry.state == 'validated')
        attendance = self.env.ref('hr_work_entry.work_entry_type_attendance')
        for entry in validated:
            entry.check_access('unlink')
            if entry.work_entry_type_id != attendance or not entry.contract_id:
                raise UserError(_('Solo puede eliminar asistencia validada cubierta por liquidaciones en borrador.'))
            # Serialize with payroll changes; inspect all matching original rows,
            # including records hidden by rules. Hidden rows do not grant access.
            self.env.cr.execute('SELECT id FROM hr_work_entry WHERE id=%s FOR UPDATE', [entry.id])
            zone = entry.employee_id.resource_calendar_id.tz or entry.employee_id.resource_id.tz or 'America/Santiago'
            first = fields.Datetime.context_timestamp(entry.with_context(tz=zone), entry.date_start).date()
            last = fields.Datetime.context_timestamp(entry.with_context(tz=zone), entry.date_stop).date()
            self.env.cr.execute("SELECT id FROM hr_payslip WHERE employee_id=%s AND company_id=%s AND date_from<=%s AND date_to>=%s AND state!='cancel' ORDER BY id FOR UPDATE",
                                [entry.employee_id.id, entry.company_id.id, last, first])
            slips = self.env['hr.payslip'].browse([row[0] for row in self.env.cr.fetchall()])
            slips.invalidate_recordset()
            slips.check_access('read')
            if (not slips or any(slip.state != 'draft' or slip.contract_id != entry.contract_id or
                    slip.date_from > first or slip.date_to < last or
                    ('paid' in slip._fields and slip.paid) or
                    ('step_history_locked' in slip._fields and slip.step_history_locked) or
                    (slip.move_id and slip.move_id.state == 'posted') for slip in slips)):
                raise UserError(_('La asistencia validada solo se puede eliminar si todas sus liquidaciones están en borrador, sin pago ni asiento publicado.'))
        # Keep upstream deletion protection for every entry outside this exception.
        return super(WorkEntry, self - validated)._unlink_except_validated_work_entries()
