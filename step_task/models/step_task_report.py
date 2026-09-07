# -*- coding: utf-8 -*-
"""Generador único de los informes de Steps Task.

Devuelve una estructura genérica (``columns`` / ``rows`` / ``meta``) que sirve
tanto para renderizar una tabla en la PWA como para exportar a XLSX. Lo usan:
  * el controlador ``/api/task/report/<key>`` (JSON y descarga XLSX);
  * los asistentes ``report.task.*`` de la consola Odoo.

Informes (anexos del documento 1.1.3):
  data     -> 1.1.3.3  Data Steps Task
  hours    -> 1.1.3.1  Informes Horas diarias
  yield    -> 1.1.3.2  Informes rendimientos diarios
  analysis -> 1.1.3.4  Informes análisis rendimientos
"""

import calendar
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import xlsxwriter

_DAY_ABBR = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']

REPORTS = {
    'data': {
        'name': 'Data Steps Task',
        'kind': 'table',
        'params': ['date_from', 'date_to', 'only_transmitted'],
    },
    'hours': {
        'name': 'Horas diarias',
        'kind': 'matrix',
        'params': ['year', 'month', 'jornada_hours', 'fundo_id', 'crew_id'],
    },
    'yield': {
        'name': 'Rendimientos diarios',
        'kind': 'matrix',
        'params': ['year', 'month', 'fundo_id', 'crew_id'],
    },
    'analysis': {
        'name': 'Análisis de rendimientos',
        'kind': 'table',
        'params': ['date_from', 'date_to', 'fundo_id'],
    },
}


class StepTaskReport(models.AbstractModel):
    _name = 'step.task.report'
    _description = 'Generador de informes Steps Task'

    # ------------------------------------------------------------------ API
    @api.model
    def specs(self):
        return [dict(key=key, **{k: v for k, v in spec.items() if k != 'params'},
                     params=spec['params']) for key, spec in REPORTS.items()]

    @api.model
    def build(self, key, params=None):
        params = params or {}
        if key not in REPORTS:
            raise UserError(_('Informe no soportado: %s', key))
        method = getattr(self, '_build_%s' % key)
        result = method(params)
        result.setdefault('key', key)
        result.setdefault('kind', REPORTS[key]['kind'])
        return result

    @api.model
    def to_xlsx(self, result):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet((result.get('key') or 'informe')[:28])
        title_f = wb.add_format({'bold': True, 'font_size': 13})
        label_f = wb.add_format({'bold': True, 'bg_color': '#E7F3ED'})
        head_f = wb.add_format({'bold': True, 'border': 1, 'align': 'center',
                                'bg_color': '#D7E4BC', 'text_wrap': True})
        text_f = wb.add_format({'border': 1})
        num_f = wb.add_format({'border': 1, 'num_format': '#,##0.##'})
        total_f = wb.add_format({'border': 1, 'bold': True, 'num_format': '#,##0.##',
                                 'bg_color': '#F2F2F2'})
        low_f = wb.add_format({'border': 1, 'num_format': '#,##0.##', 'bg_color': '#FCE4D6'})
        high_f = wb.add_format({'border': 1, 'num_format': '#,##0.##', 'bg_color': '#FFF2CC'})
        flag_fmt = {'low': low_f, 'high': high_f, 'total': total_f}

        row = 0
        if result.get('title'):
            ws.write(row, 0, result['title'], title_f)
            row += 2
        for pair in result.get('meta', []):
            ws.write(row, 0, pair[0], label_f)
            ws.write(row, 1, pair[1])
            row += 1
        if result.get('meta'):
            row += 1

        columns = result['columns']
        for c, name in enumerate(columns):
            ws.write(row, c, name, head_f)
        ws.set_column(0, 0, 26)
        header_row = row
        row += 1

        for line in result['rows']:
            cells = line['cells'] if isinstance(line, dict) else line
            flags = line.get('flags', {}) if isinstance(line, dict) else {}
            for c, value in enumerate(cells):
                fmt = flag_fmt.get(flags.get(str(c)) or flags.get(c), None)
                if isinstance(value, (int, float)):
                    ws.write_number(row, c, value, fmt or num_f)
                else:
                    ws.write(row, c, value if value is not None else '', fmt or text_f)
            row += 1

        if result.get('note'):
            ws.write(row + 1, 0, result['note'], label_f)
        ws.freeze_panes(header_row + 1, 0)
        wb.close()
        output.seek(0)
        return output.getvalue()

    # --------------------------------------------------------------- helpers
    def _p_date(self, params, name, default):
        raw = params.get(name)
        if not raw:
            return default
        try:
            return fields.Date.to_date(raw)
        except (ValueError, TypeError):
            raise UserError(_('Fecha inválida en %s: %s', name, raw))

    def _p_int(self, params, name, default):
        raw = params.get(name)
        try:
            return int(raw) if raw not in (None, '') else default
        except (ValueError, TypeError):
            return default

    def _p_float(self, params, name, default):
        raw = params.get(name)
        try:
            return float(raw) if raw not in (None, '') else default
        except (ValueError, TypeError):
            return default

    def _p_bool(self, params, name, default):
        raw = params.get(name)
        if raw in (None, ''):
            return default
        return str(raw).lower() in ('1', 'true', 't', 'yes', 'on')

    def _registry_domain(self, date_from, date_to, extra=None):
        return [
            ('tarja_id.company_id', '=', self.env.company.id),
            ('tarja_id.date', '>=', fields.Date.to_string(date_from)),
            ('tarja_id.date', '<=', fields.Date.to_string(date_to)),
        ] + (extra or [])

    def _matrix_extra(self, params):
        extra = []
        fundo = self._p_int(params, 'fundo_id', 0)
        crew = self._p_int(params, 'crew_id', 0)
        if fundo:
            extra.append(('tarja_id.fundo_id', '=', fundo))
        if crew:
            extra += ['|', ('tarja_id.salary_id', '=', crew),
                      ('tarja_id.salary_id_contrac', '=', crew)]
        return extra

    def _month_bounds(self, params):
        today = fields.Date.today()
        year = self._p_int(params, 'year', today.year)
        month = self._p_int(params, 'month', today.month)
        month = min(12, max(1, month))
        last = calendar.monthrange(year, month)[1]
        return year, month, last

    def _crew_name(self, params):
        crew = self.env['hr.salary.custom'].browse(self._p_int(params, 'crew_id', 0))
        return crew.display_name if crew.exists() else 'Todas'

    def _fundo_name(self, params):
        fundo = self.env['step.fundo'].browse(self._p_int(params, 'fundo_id', 0))
        return fundo.display_name if fundo.exists() else 'Todos'

    # ----------------------------------------------------------- 1.1.3.3 data
    def _build_data(self, params):
        today = fields.Date.today()
        date_from = self._p_date(params, 'date_from', today.replace(day=1))
        date_to = self._p_date(params, 'date_to', today)
        only_tx = self._p_bool(params, 'only_transmitted', True)
        extra = [('tarja_id.mobile_status', '=', 'sent')] if only_tx \
            else [('tarja_id.mobile_status', '!=', False)]
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(date_from, date_to, extra), order='tarja_id, id')

        status_sel = dict(self.env['step.tarja']._fields['mobile_status'].selection)
        type_sel = dict(self.env['step.tarja']._fields['tarja_type'].selection)
        columns = ['Tipo tarea', 'Cuadrilla', 'N° OP', 'Usuario', 'Contratista', 'Fecha',
                   'N° OT', 'Estado', 'Autorizador', 'Fundo', 'Especie', 'Variedad',
                   'Hr inicio', 'Hora cierre', 'Horas OT', 'Centro de costos', 'Labor', 'UdM',
                   'Trabajador', 'NIP', 'Cantidad', 'Hr ordinarias', 'Hr extras']
        rows = []
        for line in lines:
            t = line.tarja_id
            crew = t.salary_id or t.salary_id_contrac
            especie = t.mobile_especie_id or (t.especie_id if 'especie_id' in t._fields else False)
            rows.append({'cells': [
                type_sel.get(t.tarja_type, ''),
                crew.display_name if crew else '',
                t.op_number or '',
                t.user_id.display_name if t.user_id else '',
                t.partner_id.display_name if t.partner_id else '',
                fields.Date.to_string(t.date) if t.date else '',
                t.mobile_work_order or t.folio or t.name or '',
                status_sel.get(t.mobile_status or '', ''),
                t.auto_id.display_name if t.auto_id else '',
                t.fundo_id.display_name if t.fundo_id else '',
                especie.display_name if especie else '',
                t.mobile_variedad_id.display_name if t.mobile_variedad_id else '',
                fields.Datetime.to_string(t.hora_inicio) if t.hora_inicio else '',
                fields.Datetime.to_string(t.hora_cierre) if t.hora_cierre else '',
                round((t.hr_ordinarias or 0) + (t.hr_extras or 0), 2),
                line.cost_id.display_name if line.cost_id else '',
                line.labor_id.display_name if line.labor_id else '',
                line.uom_id.display_name if line.uom_id else '',
                line.employee_id.display_name if line.employee_id else '',
                line.employee_id.pin or '',
                round(line.quantity or 0.0, 2),
                round(line.hrs or 0.0, 2),
                round(line.hrs_extra or 0.0, 2),
            ]})
        return {
            'title': 'DATA STEPS TASK',
            'filename': 'data_steps_task.xlsx',
            'meta': [['Desde', fields.Date.to_string(date_from)],
                     ['Hasta', fields.Date.to_string(date_to)],
                     ['Solo transmitidas', 'Sí' if only_tx else 'No']],
            'columns': columns,
            'rows': rows,
        }

    # --------------------------------------------------------- 1.1.3.1 hours
    def _build_hours(self, params):
        year, month, last = self._month_bounds(params)
        jornada = self._p_float(params, 'jornada_hours', 8.0)
        date_from = fields.Date.to_date('%04d-%02d-01' % (year, month))
        date_to = fields.Date.to_date('%04d-%02d-%02d' % (year, month, last))
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(date_from, date_to, self._matrix_extra(params)))

        data = {}
        for line in lines:
            emp = line.employee_id
            if not emp:
                continue
            day = line.tarja_id.date.day
            data.setdefault(emp, {})
            data[emp][day] = data[emp].get(day, 0.0) + (line.hrs or 0.0) + (line.hrs_extra or 0.0)

        columns = ['Trabajador', 'NIP'] + [
            '%s %d' % (_DAY_ABBR[calendar.weekday(year, month, d)], d) for d in range(1, last + 1)
        ] + ['TOTAL']
        rows = []
        for emp, per_day in sorted(data.items(), key=lambda kv: kv[0].display_name):
            cells = [emp.display_name, emp.pin or '']
            flags = {}
            total = 0.0
            for d in range(1, last + 1):
                value = round(per_day.get(d, 0.0), 2)
                total += value
                col = 1 + d
                if value and value < jornada:
                    flags[str(col)] = 'low'
                elif value > jornada:
                    flags[str(col)] = 'high'
                cells.append(value)
            cells.append(round(total, 2))
            flags[str(len(columns) - 1)] = 'total'
            rows.append({'cells': cells, 'flags': flags})
        return {
            'title': 'INFORME DE HORAS POR TRABAJADOR',
            'filename': 'horas_diarias.xlsx',
            'meta': [['Mes', '%s %d' % (calendar.month_name[month].capitalize(), year)],
                     ['Cuadrilla', self._crew_name(params)],
                     ['Fundo', self._fundo_name(params)],
                     ['Jornada (h)', jornada]],
            'columns': columns,
            'rows': rows,
            'note': 'Naranja: día bajo la jornada · Amarillo: día con exceso',
        }

    # --------------------------------------------------------- 1.1.3.2 yield
    def _build_yield(self, params):
        year, month, last = self._month_bounds(params)
        date_from = fields.Date.to_date('%04d-%02d-01' % (year, month))
        date_to = fields.Date.to_date('%04d-%02d-%02d' % (year, month, last))
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(date_from, date_to, self._matrix_extra(params)))

        data = {}
        for line in lines:
            emp = line.employee_id
            if not emp or not line.labor_id:
                continue
            key = (emp, line.labor_id, line.uom_id)
            day = line.tarja_id.date.day
            data.setdefault(key, {})
            data[key][day] = data[key].get(day, 0.0) + (line.quantity or 0.0)

        columns = ['Trabajador', 'NIP', 'Labor', 'UdM'] + [
            '%s %d' % (_DAY_ABBR[calendar.weekday(year, month, d)], d) for d in range(1, last + 1)
        ] + ['TOTAL']
        rows = []
        for (emp, labor, uom), per_day in sorted(
                data.items(), key=lambda kv: (kv[0][0].display_name, kv[0][1].display_name)):
            cells = [emp.display_name, emp.pin or '', labor.display_name,
                     uom.display_name if uom else '']
            total = 0.0
            for d in range(1, last + 1):
                value = round(per_day.get(d, 0.0), 2)
                total += value
                cells.append(value)
            cells.append(round(total, 2))
            rows.append({'cells': cells, 'flags': {str(len(columns) - 1): 'total'}})
        return {
            'title': 'INFORME DE RENDIMIENTOS POR TRABAJADOR',
            'filename': 'rendimientos_diarios.xlsx',
            'meta': [['Mes', '%s %d' % (calendar.month_name[month].capitalize(), year)],
                     ['Cuadrilla', self._crew_name(params)],
                     ['Fundo', self._fundo_name(params)]],
            'columns': columns,
            'rows': rows,
        }

    # ------------------------------------------------------ 1.1.3.4 analysis
    def _analysis_master(self, cost, labor):
        rel = (labor.uom_trato.name or '').lower() if labor and labor.uom_trato else ''
        hileras = len(cost.hilera_line) if 'hilera_line' in cost._fields else 0
        if 'planta' in rel:
            return cost.plant_cost or 0.0
        if 'hect' in rel or 'has' in rel:
            return cost.has_cost or 0.0
        if 'hilera' in rel:
            return hileras
        return 0.0

    def _build_analysis(self, params):
        today = fields.Date.today()
        date_from = self._p_date(params, 'date_from', today.replace(day=1))
        date_to = self._p_date(params, 'date_to', today)
        extra = [('tarja_id.mobile_status', 'in', ('reviewed', 'sent'))]
        fundo = self._p_int(params, 'fundo_id', 0)
        if fundo:
            extra.append(('tarja_id.fundo_id', '=', fundo))
        lines = self.env['step.tarja.registry'].search(
            self._registry_domain(date_from, date_to, extra))

        grouped = {}
        for line in lines:
            if not line.cost_id or not line.labor_id:
                continue
            grouped.setdefault((line.cost_id, line.labor_id), 0.0)
            grouped[(line.cost_id, line.labor_id)] += line.quantity or 0.0

        columns = ['Centro Costos', 'Especie', 'Variedad', 'Hectáreas', 'Plantas', 'Hileras',
                   'Labor', 'UdM', 'Cantidad', 'Diferencia']
        rows = []
        for (cost, labor), qty in sorted(
                grouped.items(), key=lambda kv: (kv[0][0].display_name, kv[0][1].display_name)):
            hileras = len(cost.hilera_line) if 'hilera_line' in cost._fields else 0
            master = self._analysis_master(cost, labor)
            rows.append({'cells': [
                cost.display_name,
                cost.especie_id.display_name if 'especie_id' in cost._fields and cost.especie_id else '',
                cost.variedad_id.display_name if 'variedad_id' in cost._fields and cost.variedad_id else '',
                cost.has_cost or 0.0 if 'has_cost' in cost._fields else 0.0,
                cost.plant_cost or 0.0 if 'plant_cost' in cost._fields else 0.0,
                hileras,
                labor.display_name,
                labor.uom_trato.display_name if labor.uom_trato else '',
                round(qty, 2),
                round(master - qty, 2),
            ]})
        return {
            'title': 'ANÁLISIS DE RENDIMIENTOS',
            'filename': 'analisis_rendimientos.xlsx',
            'meta': [['Desde', fields.Date.to_string(date_from)],
                     ['Hasta', fields.Date.to_string(date_to)],
                     ['Fundo', self._fundo_name(params)]],
            'columns': columns,
            'rows': rows,
        }
