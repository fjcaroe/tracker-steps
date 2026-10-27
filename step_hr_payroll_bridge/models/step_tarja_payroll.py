from datetime import datetime, time, timedelta
from odoo import models


class StepTarjaPayroll(models.Model):
    _inherit = 'step.tarja'

    def envio_nomina(self):
        for salary in self:
            specific_time = time(hour=12, minute=00)
            combined_datetime = datetime.combine(salary.date, specific_time)
            salary.write({'remunera': True})
            if salary.tarja_type == 'propio':
                for line in salary.tarja_line:
                    if line.hrs > 0:
                        fecha_hora = salary.date
                        hora_extra = combined_datetime + timedelta(hours=int(line.hrs))
                        work_id = self.env['hr.work.entry'].create([{
                            'name': salary.name + ' - ' + line.labor_id.name,
                            'employee_id': line.employee_id.id,
                            'work_entry_type_id': 1,
                            'date_start': combined_datetime,
                            'date_stop': combined_datetime + timedelta(hours=int(line.hrs)),
                            'duration': line.hrs,
                        }])
                    if line.hrs_extra > 0:
                        work_extra_id = self.env['hr.work.entry'].create([{
                            'name': salary.name + ' - ' + line.labor_id.name,
                            'employee_id': line.employee_id.id,
                            'work_entry_type_id': 2,
                            'date_start': hora_extra,
                            'date_stop': hora_extra + timedelta(hours=int(line.hrs_extra)),
                            'duration': line.hrs_extra,
                        }])

