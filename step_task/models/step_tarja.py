# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StepTarja(models.Model):
    """Campos de sincronización móvil para la app Steps Task.

    ``step.tarja`` ya es la cabecera de la Orden de Trabajo (OT) de labores.
    Steps Task sólo agrega el estado del ciclo móvil, la idempotencia de la
    sincronización y las horas de jornada editables descritas en el documento
    ``1.1.2 App móvil de labores``.
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
        help="Estado del registro dentro del flujo de Steps Task: en proceso, "
             "cerrada en el equipo, revisada en la consola y transmitida a "
             "Actividades.",
    )
    mobile_uid = fields.Char(
        string='UID móvil',
        copy=False,
        index=True,
        help="Identificador único generado por la app. Garantiza que reenviar "
             "una OT no cree duplicados.",
    )
    mobile_work_order = fields.Char(
        string='N° OT móvil',
        copy=False,
        index=True,
        help="Número de OT tal como lo mostró la aplicación móvil.",
    )
    mobile_device = fields.Char(
        string='Equipo móvil',
        copy=False,
        help="Identificación del equipo (tablet/celular) que originó la OT.",
    )
    mobile_user = fields.Char(
        string='Usuario móvil',
        copy=False,
        help="Nombre del operador que registró la OT en terreno.",
    )
    op_number = fields.Char(
        string='N° OP',
        copy=False,
        help="Orden de Producción semanal. Si la app no la informa se usa la "
             "semana ISO en curso con el formato W<semana>.",
    )
    send_type = fields.Selection(
        selection=[
            ('parcial', 'Parcial'),
            ('total', 'Total'),
        ],
        string='Tipo de envío',
        copy=False,
        help="Parcial: se recibieron datos de una OT en proceso. "
             "Total: se recibió una OT cerrada.",
    )

    # --- Horas de la jornada (editables para ajustar al pago) ---------------
    hora_inicio = fields.Datetime(
        string='Hora de inicio OT',
        copy=False,
    )
    hora_cierre = fields.Datetime(
        string='Hora de cierre OT',
        copy=False,
    )
    hr_ordinarias = fields.Float(
        string='Horas ordinarias OT',
        copy=False,
        help="Horas ordinarias de la cuadrilla para esta OT. Se calcula por la "
             "diferencia entre la hora de cierre (tope: cierre de jornada "
             "ordinaria) y la hora de inicio, y es editable.",
    )
    hr_extras = fields.Float(
        string='Horas extras OT',
        copy=False,
        help="Horas por sobre el cierre de la jornada ordinaria. Editable.",
    )

    num_workers = fields.Integer(
        string='N° trabajadores',
        compute='_compute_num_workers',
    )

    @api.depends('tarja_registry.employee_id', 'tarja_line.employee_id')
    def _compute_num_workers(self):
        for record in self:
            workers = record.tarja_registry.employee_id | record.tarja_line.employee_id
            record.num_workers = len(workers)

    @api.model
    def _step_task_week_op(self, when=None):
        """Devuelve la OP por defecto (``W<semana ISO>``) para una fecha."""
        when = when or fields.Date.context_today(self)
        return 'W%02d' % when.isocalendar()[1]
