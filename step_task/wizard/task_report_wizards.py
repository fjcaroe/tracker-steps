# -*- coding: utf-8 -*-
"""Informes de Steps Task (consola).

Cuatro asistentes que generan XLSX, según los anexos:
  * ``report.task.data``          -> Anexo 1.1.3.3 "data Steps Task"
  * ``report.task.hours``         -> Anexo 1.1.3.1 "Informes Horas diarias"
  * ``report.task.yield``         -> Anexo 1.1.3.2 "Informes rendimientos diarios"
  * ``report.task.yield.analysis``-> Anexo 1.1.3.4 "Informes análisis rendimientos"

Trabajan sobre ``step.tarja`` (cabecera OT) y ``step.tarja.registry`` (detalle).
"""

import base64
import calendar
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter

DAY_NAMES = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']


def _formats(workbook):
    return {
        'title': workbook.add_format({'bold': True, 'font_size': 13}),
        'label': workbook.add_format({'bold': True, 'bg_color': '#E7F3ED'}),
        'header': workbook.add_format({'bold': True, 'border': 1, 'align': 'center',
                                       'bg_color': '#D7E4BC', 'text_wrap': True}),
        'text': workbook.add_format({'border': 1}),
        'num': workbook.add_format({'border': 1, 'num_format': '#,##0.0'}),
        'num0': workbook.add_format({'border': 1, 'num_format': '#,##0'}),
        'total': workbook.add_format({'border': 1, 'bold': True, 'num_format': '#,##0.0',
                                      'bg_color': '#F2F2F2'}),
        'low': workbook.add_format({'border': 1, 'num_format': '#,##0.0', 'bg_color': '#FCE4D6'}),
        'high': workbook.add_format({'border': 1, 'num_format': '#,##0.0', 'bg_color': '#FFF2CC'}),
    }


class TaskReportMixin(models.AbstractModel):
    _name = 'task.report.mixin'
    _description = 'Base de informes Steps Task'

    file = fields.Binary(string='Archivo', readonly=True)
    file_name = fields.Char(string='Nombre archivo', readonly=True)

    def _registry_domain(self, date_from, date_to, extra=None):
        domain = [
            ('tarja_id.company_id', '=', self.env.company.id),
            ('tarja_id.date', '>=', fields.Date.to_string(date_from)),
            ('tarja_id.date', '<=', fields.Date.to_string(date_to)),
        ]
        return domain + (extra or [])

    def _deliver(self, output, name):
        self.write({'file': base64.b64encode(output.getvalue()), 'file_name': name})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ReportTaskData(models.TransientModel):
    _name = 'report.task.data'
    _inherit = 'task.report.mixin'
    _description = 'Informe Data Steps Task'

    date_from = fields.Date(string='Desde', required=True,
                            default=lambda s: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    only_transmitted = fields.Boolean(string='Solo transmitidas', default=True)

    def action_generate(self):
        self.ensure_one()
        extra = [('tarja_id.mobile_status', '=', 'sent')] if self.only_transmitted \
            else [('tarja_id.mobile_status', '!=', False)]
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(self.date_from, self.date_to, extra),
            order='tarja_id, id')

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Data Steps Task')
        f = _formats(wb)
        cols = ['Tipo tarea', 'Cuadrilla', 'Número OP', 'Usuario', 'Contratista', 'Fecha',
                'Número OT', 'Estado', 'Autorizador', 'Fundo', 'Especie', 'Variedad',
                'Hr inicio', 'Hora cierre', 'Horas OT', 'Centro de costos', 'Labor', 'UdM',
                'Trabajador', 'NIP', 'Cantidad', 'Hr ordinarias', 'Hr extras']
        for c, name in enumerate(cols):
            ws.write(0, c, name, f['header'])
        ws.set_column(0, len(cols) - 1, 16)

        status_sel = dict(self.env['step.tarja']._fields['mobile_status'].selection)
        row = 1
        for line in lines:
            t = line.tarja_id
            crew = t.salary_id or t.salary_id_contrac
            vals = [
                dict(t._fields['tarja_type'].selection).get(t.tarja_type, ''),
                crew.display_name if crew else '',
                t.op_number or '',
                t.user_id.display_name if t.user_id else '',
                t.partner_id.display_name if t.partner_id else '',
                fields.Date.to_string(t.date) if t.date else '',
                t.mobile_work_order or t.folio or t.name or '',
                status_sel.get(t.mobile_status or '', ''),
                t.auto_id.display_name if t.auto_id else '',
                t.fundo_id.display_name if t.fundo_id else '',
                (t.mobile_especie_id or t.especie_id).display_name if (t.mobile_especie_id or t.especie_id) else '',
                t.mobile_variedad_id.display_name if t.mobile_variedad_id else '',
                fields.Datetime.to_string(t.hora_inicio) if t.hora_inicio else '',
                fields.Datetime.to_string(t.hora_cierre) if t.hora_cierre else '',
                t.hr_ordinarias + t.hr_extras,
                line.cost_id.display_name if line.cost_id else '',
                line.labor_id.display_name if line.labor_id else '',
                line.uom_id.display_name if line.uom_id else '',
                line.employee_id.display_name if line.employee_id else '',
                line.employee_id.pin or '',
                line.quantity or 0.0,
                line.hrs or 0.0,
                line.hrs_extra or 0.0,
            ]
            for c, v in enumerate(vals):
                if isinstance(v, float):
                    ws.write_number(row, c, v, f['num'])
                else:
                    ws.write(row, c, v, f['text'])
            row += 1

        wb.close()
        output.seek(0)
        return self._deliver(output, 'data_steps_task.xlsx')


class _MonthlyMatrixWizard(models.AbstractModel):
    _name = 'report.task.monthly.matrix'
    _inherit = 'task.report.mixin'
    _description = 'Base informe mensual matriz'

    year = fields.Integer(string='Año', required=True, default=lambda s: fields.Date.today().year)
    month = fields.Selection(
        selection=[(str(i), calendar.month_name[i].capitalize()) for i in range(1, 13)],
        string='Mes', required=True, default=lambda s: str(fields.Date.today().month))
    fundo_id = fields.Many2one('step.fundo', string='Fundo')
    crew_id = fields.Many2one('hr.salary.custom', string='Cuadrilla')
    jornada_hours = fields.Float(string='Horas jornada', default=8.0)

    def _month_range(self):
        year, month = int(self.year), int(self.month)
        last = calendar.monthrange(year, month)[1]
        return (fields.Date.to_date('%04d-%02d-01' % (year, month)),
                fields.Date.to_date('%04d-%02d-%02d' % (year, month, last)), last)

    def _matrix_domain(self, date_from, date_to):
        extra = []
        if self.fundo_id:
            extra.append(('tarja_id.fundo_id', '=', self.fundo_id.id))
        if self.crew_id:
            extra += ['|', ('tarja_id.salary_id', '=', self.crew_id.id),
                      ('tarja_id.salary_id_contrac', '=', self.crew_id.id)]
        return self._registry_domain(date_from, date_to, extra)

    def _write_month_header(self, ws, f, first_col, days, year, month):
        for d in range(1, days + 1):
            weekday = DAY_NAMES[calendar.weekday(year, month, d)]
            ws.write(4, first_col + d - 1, weekday, f['header'])
            ws.write(5, first_col + d - 1, d, f['header'])
        ws.write(5, first_col + days, 'TOTAL', f['header'])


class ReportTaskHours(models.TransientModel):
    _name = 'report.task.hours'
    _inherit = 'report.task.monthly.matrix'
    _description = 'Informe de horas diarias por trabajador'

    def action_generate(self):
        self.ensure_one()
        date_from, date_to, days = self._month_range()
        year, month = int(self.year), int(self.month)
        lines = self.env['step.tarja.registry'].search(self._matrix_domain(date_from, date_to))

        data = {}  # employee -> {day: hours}
        for line in lines:
            emp = line.employee_id
            if not emp:
                continue
            day = line.tarja_id.date.day
            data.setdefault(emp, {}).setdefault(day, 0.0)
            data[emp][day] += (line.hrs or 0.0) + (line.hrs_extra or 0.0)

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Horas diarias')
        f = _formats(wb)
        ws.write(0, 0, 'INFORME DE HORAS POR TRABAJADOR', f['title'])
        ws.write(1, 0, 'Mes', f['label'])
        ws.write(1, 1, '%s %s' % (calendar.month_name[month].capitalize(), year))
        ws.write(2, 0, 'Cuadrilla', f['label'])
        ws.write(2, 1, self.crew_id.display_name or 'Todas')
        ws.write(3, 0, 'Fundo', f['label'])
        ws.write(3, 1, self.fundo_id.display_name or 'Todos')
        ws.write(5, 0, 'Trabajador', f['header'])
        ws.write(5, 1, 'NIP', f['header'])
        self._write_month_header(ws, f, 2, days, year, month)
        ws.set_column(0, 0, 26)

        row = 6
        for emp, per_day in sorted(data.items(), key=lambda kv: kv[0].display_name):
            ws.write(row, 0, emp.display_name, f['text'])
            ws.write(row, 1, emp.pin or '', f['text'])
            total = 0.0
            for d in range(1, days + 1):
                value = per_day.get(d, 0.0)
                total += value
                fmt = f['num']
                if value and value < self.jornada_hours:
                    fmt = f['low']
                elif value > self.jornada_hours:
                    fmt = f['high']
                ws.write_number(row, 1 + d, value, fmt)
            ws.write_number(row, 2 + days, total, f['total'])
            row += 1

        ws.write(row + 1, 0, 'Naranja: día bajo la jornada · Amarillo: día con exceso', f['label'])
        wb.close()
        output.seek(0)
        return self._deliver(output, 'horas_diarias.xlsx')


class ReportTaskYield(models.TransientModel):
    _name = 'report.task.yield'
    _inherit = 'report.task.monthly.matrix'
    _description = 'Informe de rendimientos diarios por trabajador'

    def action_generate(self):
        self.ensure_one()
        date_from, date_to, days = self._month_range()
        year, month = int(self.year), int(self.month)
        lines = self.env['step.tarja.registry'].search(self._matrix_domain(date_from, date_to))

        data = {}  # (employee, labor, uom) -> {day: qty}
        for line in lines:
            emp = line.employee_id
            if not emp or not line.labor_id:
                continue
            key = (emp, line.labor_id, line.uom_id)
            day = line.tarja_id.date.day
            data.setdefault(key, {}).setdefault(day, 0.0)
            data[key][day] += line.quantity or 0.0

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Rendimientos diarios')
        f = _formats(wb)
        ws.write(0, 0, 'INFORME DE RENDIMIENTOS POR TRABAJADOR', f['title'])
        ws.write(1, 0, 'Mes', f['label'])
        ws.write(1, 1, '%s %s' % (calendar.month_name[month].capitalize(), year))
        ws.write(2, 0, 'Cuadrilla', f['label'])
        ws.write(2, 1, self.crew_id.display_name or 'Todas')
        ws.write(3, 0, 'Fundo', f['label'])
        ws.write(3, 1, self.fundo_id.display_name or 'Todos')
        for c, name in enumerate(['Trabajador', 'NIP', 'Labor', 'UdM']):
            ws.write(5, c, name, f['header'])
        self._write_month_header(ws, f, 4, days, year, month)
        ws.set_column(0, 0, 24)
        ws.set_column(2, 2, 20)

        row = 6
        for (emp, labor, uom), per_day in sorted(
                data.items(), key=lambda kv: (kv[0][0].display_name, kv[0][1].display_name)):
            ws.write(row, 0, emp.display_name, f['text'])
            ws.write(row, 1, emp.pin or '', f['text'])
            ws.write(row, 2, labor.display_name, f['text'])
            ws.write(row, 3, uom.display_name if uom else '', f['text'])
            total = 0.0
            for d in range(1, days + 1):
                value = per_day.get(d, 0.0)
                total += value
                ws.write_number(row, 3 + d, value, f['num'])
            ws.write_number(row, 4 + days, total, f['total'])
            row += 1

        wb.close()
        output.seek(0)
        return self._deliver(output, 'rendimientos_diarios.xlsx')


class ReportTaskYieldAnalysis(models.TransientModel):
    _name = 'report.task.yield.analysis'
    _inherit = 'task.report.mixin'
    _description = 'Análisis de rendimientos'

    date_from = fields.Date(string='Desde', required=True,
                            default=lambda s: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    fundo_id = fields.Many2one('step.fundo', string='Fundo')

    def _master_value(self, cost, labor):
        """Valor del maestro del centro de costo según la relación de trato de la labor."""
        rel = (labor.uom_trato.name or '').lower() if labor and labor.uom_trato else ''
        hileras = len(cost.hilera_line) if 'hilera_line' in cost._fields else 0
        if 'planta' in rel:
            return cost.plant_cost or 0.0
        if 'hect' in rel or 'has' in rel:
            return cost.has_cost or 0.0
        if 'hilera' in rel:
            return hileras
        return 0.0

    def action_generate(self):
        self.ensure_one()
        extra = [('tarja_id.mobile_status', 'in', ('reviewed', 'sent'))]
        if self.fundo_id:
            extra.append(('tarja_id.fundo_id', '=', self.fundo_id.id))
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(self.date_from, self.date_to, extra))

        grouped = {}  # (cost, labor) -> qty
        for line in lines:
            if not line.cost_id or not line.labor_id:
                continue
            key = (line.cost_id, line.labor_id)
            grouped[key] = grouped.get(key, 0.0) + (line.quantity or 0.0)

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Análisis rendimientos')
        f = _formats(wb)
        ws.write(0, 0, 'ANÁLISIS DE RENDIMIENTOS', f['title'])
        cols = ['Centro Costos', 'Especie', 'Variedad', 'Hectáreas', 'Plantas', 'Hileras',
                'Labor', 'UdM', 'Cantidad', 'Diferencia']
        for c, name in enumerate(cols):
            ws.write(2, c, name, f['header'])
        ws.set_column(0, 0, 26)
        ws.set_column(6, 6, 20)

        row = 3
        for (cost, labor), qty in sorted(
                grouped.items(), key=lambda kv: (kv[0][0].display_name, kv[0][1].display_name)):
            hileras = len(cost.hilera_line) if 'hilera_line' in cost._fields else 0
            master = self._master_value(cost, labor)
            ws.write(row, 0, cost.display_name, f['text'])
            ws.write(row, 1, cost.especie_id.display_name if cost.especie_id else '', f['text'])
            ws.write(row, 2, cost.variedad_id.display_name if cost.variedad_id else '', f['text'])
            ws.write_number(row, 3, cost.has_cost or 0.0, f['num0'])
            ws.write_number(row, 4, cost.plant_cost or 0.0, f['num0'])
            ws.write_number(row, 5, hileras, f['num0'])
            ws.write(row, 6, labor.display_name, f['text'])
            ws.write(row, 7, labor.uom_trato.display_name if labor.uom_trato else '', f['text'])
            ws.write_number(row, 8, qty, f['num'])
            ws.write_number(row, 9, master - qty, f['num'])
            row += 1

        wb.close()
        output.seek(0)
        return self._deliver(output, 'analisis_rendimientos.xlsx')
