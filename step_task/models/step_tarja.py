# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StepTarja(models.Model):
    """Capa Steps Task sobre la cabecera de OT de labores (``step.tarja``).

    Aporta el ciclo del canal móvil, las horas de jornada editables descritas
    en ``1.1.2 App móvil de labores``, la consolidación / transmisión a
    Actividades de la consola (``1.1.3``) y las alertas de validación diaria.
    """

    _inherit = 'step.tarja'

    # --- Ciclo de vida en el canal móvil -------------------------------------
    mobile_status = fields.Selection(
        selection=[
            ('progress', 'En proceso'),
            ('closed', 'Cerrada'),
            ('reviewed', 'Revisada'),
            ('sent', 'Transmitida'),
        ],
        string='Estado móvil',
        copy=False,
        index=True,
        tracking=True,
        help="Estado del registro dentro del flujo de Steps Task: en proceso, "
             "cerrada en el equipo, revisada en la consola y transmitida a "
             "Actividades.",
    )
    mobile_uid = fields.Char(
        string='UID móvil', copy=False, index=True,
        help="Identificador único generado por la app. Garantiza que reenviar "
             "una OT no cree duplicados.",
    )
    mobile_work_order = fields.Char(
        string='N° OT móvil', copy=False, index=True,
        help="Número de OT tal como lo mostró la aplicación móvil.",
    )
    mobile_device = fields.Char(string='Equipo móvil', copy=False)
    mobile_user = fields.Char(string='Usuario móvil', copy=False)
    op_number = fields.Char(
        string='N° OP', copy=False,
        help="Orden de Producción semanal. Si la app no la informa se usa la "
             "semana ISO en curso con el formato W<semana>.",
    )
    send_type = fields.Selection(
        selection=[('parcial', 'Parcial'), ('total', 'Total')],
        string='Tipo de envío', copy=False,
    )

    # --- Encabezado adicional que la consola "Crear OT" necesita -----------
    mobile_especie_id = fields.Many2one(
        'step.especie', string='Especie (Task)', copy=False,
        help="Especie de la OT en el flujo Steps Task. Independiente de la que "
             "deriva la tarifa.",
    )
    mobile_variedad_id = fields.Many2one(
        'step.variedad', string='Variedad (Task)', copy=False,
    )

    # --- Horas de la jornada (editables para ajustar al pago) --------------
    hora_inicio = fields.Datetime(string='Hora de inicio OT', copy=False)
    hora_cierre = fields.Datetime(string='Hora de cierre OT', copy=False)
    hr_ordinarias = fields.Float(
        string='Horas ordinarias OT', copy=False,
        help="Horas ordinarias de la cuadrilla para esta OT (editable).",
    )
    hr_extras = fields.Float(
        string='Horas extras OT', copy=False,
        help="Horas por sobre el cierre de la jornada ordinaria (editable).",
    )

    num_workers = fields.Integer(string='N° trabajadores', compute='_compute_num_workers')
    task_alert_count = fields.Integer(
        string='Alertas Task', compute='_compute_task_alerts', store=True)
    task_alert_html = fields.Html(
        string='Detalle de alertas', compute='_compute_task_alerts', sanitize=False)

    @api.depends('tarja_registry.employee_id', 'tarja_line.employee_id')
    def _compute_num_workers(self):
        for record in self:
            workers = record.tarja_registry.employee_id | record.tarja_line.employee_id
            record.num_workers = len(workers)

    # ------------------------------------------------------------------ utils
    @api.model
    def _step_task_week_op(self, when=None):
        when = when or fields.Date.context_today(self)
        return 'W%02d' % when.isocalendar()[1]

    def _task_pricelist_bounds(self, labor):
        """(mínimo, máximo) por jornada para una labor, desde la tarifa de la OT."""
        self.ensure_one()
        if not self.pricelist_id or not labor:
            return (0.0, 0.0)
        for item in self.pricelist_id.item_ids:
            if item.product_tmpl_id == labor or getattr(item, 'labor_id', False) == labor:
                return (item.can_std or 0.0, item.can_max or 0.0)
        return (0.0, 0.0)

    def _task_alerts(self):
        """Lista de alertas de validación diaria (doc 1.1.3)."""
        self.ensure_one()
        alerts = []
        jornada = self.hr_ordinarias or 0.0
        by_worker = {}
        by_worker_labor = {}
        for line in self.tarja_registry:
            emp = line.employee_id
            if not emp:
                continue
            acc = by_worker.setdefault(emp, {'hrs': 0.0, 'hrs_extra': 0.0})
            acc['hrs'] += line.hrs or 0.0
            acc['hrs_extra'] += line.hrs_extra or 0.0
            if line.labor_id:
                key = (emp, line.labor_id)
                by_worker_labor[key] = by_worker_labor.get(key, 0.0) + (line.quantity or 0.0)

        for emp, acc in by_worker.items():
            if jornada and acc['hrs'] < jornada:
                alerts.append({
                    'type': 'hours_low', 'level': 'warning', 'employee': emp.display_name,
                    'text': _('%(name)s: %(h).1f h ordinarias, bajo la jornada de %(j).1f h',
                              name=emp.display_name, h=acc['hrs'], j=jornada),
                })
            if not acc['hrs'] and not acc['hrs_extra']:
                alerts.append({
                    'type': 'hours_zero', 'level': 'danger', 'employee': emp.display_name,
                    'text': _('%(name)s: sin horas registradas', name=emp.display_name),
                })
            if jornada and acc['hrs'] > jornada:
                alerts.append({
                    'type': 'hours_high', 'level': 'warning', 'employee': emp.display_name,
                    'text': _('%(name)s: %(h).1f h ordinarias, sobre la jornada de %(j).1f h',
                              name=emp.display_name, h=acc['hrs'], j=jornada),
                })

        for (emp, labor), qty in by_worker_labor.items():
            low, high = self._task_pricelist_bounds(labor)
            if low and qty < low:
                alerts.append({
                    'type': 'prod_low', 'level': 'warning', 'employee': emp.display_name,
                    'text': _('%(name)s · %(labor)s: %(q).1f bajo el mínimo de %(m).1f',
                              name=emp.display_name, labor=labor.display_name, q=qty, m=low),
                })
            if high and qty > high:
                alerts.append({
                    'type': 'prod_high', 'level': 'warning', 'employee': emp.display_name,
                    'text': _('%(name)s · %(labor)s: %(q).1f sobre el máximo de %(m).1f',
                              name=emp.display_name, labor=labor.display_name, q=qty, m=high),
                })
        return alerts

    @api.depends('tarja_registry.employee_id', 'tarja_registry.hrs', 'tarja_registry.hrs_extra',
                 'tarja_registry.quantity', 'tarja_registry.labor_id', 'hr_ordinarias', 'pricelist_id')
    def _compute_task_alerts(self):
        for record in self:
            alerts = record._task_alerts()
            record.task_alert_count = len(alerts)
            if alerts:
                rows = ''.join(
                    '<li class="text-%s">%s</li>' % (a['level'], a['text']) for a in alerts
                )
                record.task_alert_html = '<ul class="mb-0">%s</ul>' % rows
            else:
                record.task_alert_html = '<span class="text-success">Sin alertas.</span>'

    # ------------------------------------------------------------ acciones
    def action_task_review(self):
        for record in self:
            if record.mobile_status not in ('closed', 'progress'):
                raise UserError(_('Solo se pueden revisar OT recibidas de la app.'))
            record.mobile_status = 'reviewed'

    def action_task_reset_mobile(self):
        for record in self:
            record.mobile_status = 'progress'

    def _task_consolidate_lines(self):
        """Suma en una sola línea los registros del mismo trabajador + centro de
        costos + labor (doc 1.1.3)."""
        self.ensure_one()
        grouped = {}
        for line in self.tarja_registry:
            key = (line.employee_id.id, line.cost_id.id, line.labor_id.id)
            grouped.setdefault(key, self.env['step.tarja.registry'])
            grouped[key] |= line
        for lines in grouped.values():
            if len(lines) <= 1:
                continue
            keeper = lines[0]
            keeper.write({
                'quantity': sum(lines.mapped('quantity')),
                'hrs': sum(lines.mapped('hrs')),
                'hrs_extra': sum(lines.mapped('hrs_extra')),
            })
            (lines - keeper).unlink()

    def _task_sync_attendance(self):
        """Vuelca la asistencia de la OT (entrada = hora inicio, salida = hora
        cierre) a ``hr.attendance``."""
        self.ensure_one()
        if not self.hora_inicio:
            return
        check_out = self.hora_cierre or fields.Datetime.now()
        Attendance = self.env['hr.attendance'].sudo()
        for employee in self.tarja_registry.employee_id:
            exists = Attendance.search([
                ('employee_id', '=', employee.id),
                ('check_in', '=', self.hora_inicio),
            ], limit=1)
            if exists:
                continue
            Attendance.create({
                'employee_id': employee.id,
                'check_in': self.hora_inicio,
                'check_out': check_out,
            })

    def action_task_transmit(self):
        for record in self:
            if record.mobile_status == 'sent':
                continue
            if not record.tarja_registry:
                raise UserError(_('La OT %s no tiene líneas para transmitir.', record.display_name))
            record._task_consolidate_lines()
            try:
                record._task_sync_attendance()
            except Exception:  # noqa: BLE001 - la asistencia no debe bloquear la transmisión
                pass
            record.mobile_status = 'sent'
            record.send_type = 'total' if record.hora_cierre else 'parcial'
        return True

    # -------------------------------------------------- datos para el tablero
    @api.model
    def get_task_dashboard_data(self, days=30):
        days = int(30 if days is None else days)
        domain = []
        if days:
            days = max(7, min(days, 365))
            since = fields.Date.today() - timedelta(days=days)
            domain = [('date', '>=', fields.Date.to_string(since))]

        def count(extra):
            return self.search_count(domain + extra)

        states = {
            'progress': count([('mobile_status', '=', 'progress')]),
            'closed': count([('mobile_status', '=', 'closed')]),
            'reviewed': count([('mobile_status', '=', 'reviewed')]),
            'sent': count([('mobile_status', '=', 'sent')]),
        }
        recent = self.search(domain, order='date desc, id desc', limit=8)
        recent_rows = [{
            'id': r.id,
            'name': r.mobile_work_order or r.folio or r.name or _('OT %s') % r.id,
            'crew': (r.salary_id or r.salary_id_contrac).display_name if (r.salary_id or r.salary_id_contrac) else '',
            'farm': r.fundo_id.display_name if r.fundo_id else '',
            'type_label': dict(r._fields['tarja_type'].selection).get(r.tarja_type, ''),
            'status': r.mobile_status or 'progress',
            'status_label': dict(r._fields['mobile_status'].selection).get(r.mobile_status or 'progress', ''),
            'workers': r.num_workers,
            'alerts': r.task_alert_count,
            'date': r.date and fields.Date.to_string(r.date) or '',
        } for r in recent]

        alert_records = self.search(
            domain + [('mobile_status', 'in', ('closed', 'reviewed', 'progress'))],
            order='date desc, id desc', limit=40)
        alert_total = sum(r.task_alert_count for r in alert_records)

        return {
            'company_name': self.env.company.display_name,
            'days': days,
            'period_label': _('Todo el histórico') if not days else _('Últimos %s días') % days,
            'states': states,
            'kpis': {
                'received': states['progress'] + states['closed'],
                'to_review': states['closed'],
                'to_transmit': states['reviewed'],
                'transmitted': states['sent'],
                'alerts': alert_total,
            },
            'recent': recent_rows,
        }
