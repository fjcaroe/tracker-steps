from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Lo importado de Tracker: solo el asistente (contexto step_tracker_import) puede escribirlo.
PROTECTED_FIELDS = {
    'usage_id', 'source', 'vehicle_id', 'imported_at', 'imported_by_id', 'driver_employee_id',
    'analytic_account_id', 'liters_source', 'src_date', 'src_distance_km', 'src_distance_known',
    'src_started_at', 'src_ended_at', 'src_duration_hours', 'src_hourmeter_initial',
    'src_hourmeter_final', 'src_hourmeter_known', 'src_liters', 'src_estimated_fuel_liters',
    'src_work_order_code',
}
IMPORT_CONTEXT = 'step_tracker_import'


class StepExpenseVehicleLine(models.Model):
    _inherit = 'step.expense.vehicle.line'
    _check_company_auto = True

    # Los km de una sesión GPS necesitan 3 decimales (12.345 m = 12,345 km); el modelo base los
    # redondeaba a 1 decimal. Solo cambia la precisión, no el tipo de columna.
    distance = fields.Float(digits=(16, 3))
    start_reading = fields.Float(digits=(12, 2))
    end_reading = fields.Float(digits=(12, 2))
    company_id = fields.Many2one(related='sheet_id.company_id', store=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', check_company=True, index=True)
    driver_employee_id = fields.Many2one('hr.employee', string='Conductor (Tracker)', check_company=True, readonly=True)
    source = fields.Selection([('manual', 'Manual'), ('tracker', 'Tracker')], string='Origen',
                              default='manual', required=True, readonly=True, copy=False)
    usage_id = fields.Many2one('step.tracker.usage', string='Sesión de Tracker', ondelete='restrict',
                               index=True, readonly=True, copy=False, check_company=True)
    imported_at = fields.Datetime(string='Importado', readonly=True, copy=False)
    imported_by_id = fields.Many2one('res.users', string='Importado por', readonly=True, copy=False)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Centro de costo (cuenta analítica)',
                                          readonly=True, copy=False, check_company=True)
    liters_source = fields.Selection(
        [('manual', 'Comprobante / ingreso manual'), ('work_order_refill', 'Recarga registrada en el parte')],
        string='Origen de los litros', default='manual', readonly=True, copy=False)
    # Instantánea de lo importado: los cambios posteriores en Tracker no la alteran.
    src_date = fields.Date(string='Fecha importada', readonly=True, copy=False)
    src_distance_km = fields.Float(string='Km importados', digits=(16, 3), readonly=True, copy=False)
    src_distance_known = fields.Boolean(string='Distancia GPS disponible al importar', readonly=True, copy=False)
    src_started_at = fields.Datetime(string='Inicio de la sesión', readonly=True, copy=False)
    src_ended_at = fields.Datetime(string='Término de la sesión', readonly=True, copy=False)
    src_duration_hours = fields.Float(string='Duración de la sesión (h)', readonly=True, copy=False)
    src_hourmeter_initial = fields.Float(string='Horómetro inicial importado', digits=(12, 2), readonly=True, copy=False)
    src_hourmeter_final = fields.Float(string='Horómetro final importado', digits=(12, 2), readonly=True, copy=False)
    src_hourmeter_known = fields.Boolean(string='Horómetro importado', readonly=True, copy=False)
    src_liters = fields.Float(string='Litros importados', digits=(16, 2), readonly=True, copy=False)
    src_estimated_fuel_liters = fields.Float(string='Combustible estimado por Tracker (no cuenta)', digits=(16, 2),
                                             readonly=True, copy=False)
    src_work_order_code = fields.Char(string='Parte diario de origen', readonly=True, copy=False)
    is_modified = fields.Boolean(string='Corregida manualmente', compute='_compute_is_modified')
    sheet_state = fields.Selection(related='sheet_id.state', string='Estado de la rendición')

    _sql_constraints = [
        ('sheet_usage_uniq', 'unique(sheet_id, usage_id)',
         'Esta sesión de Tracker ya está incorporada en esta rendición.'),
    ]

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends('usage_id', 'date', 'distance', 'start_reading', 'end_reading', 'liters',
                 'src_date', 'src_distance_km', 'src_hourmeter_initial', 'src_hourmeter_final', 'src_liters')
    def _compute_is_modified(self):
        for line in self:
            if not line.usage_id:
                line.is_modified = False
                continue
            line.is_modified = (
                line.date != line.src_date
                or abs(line.distance - line.src_distance_km) > 0.00005
                or abs(line.start_reading - line.src_hourmeter_initial) > 0.005
                or abs(line.end_reading - line.src_hourmeter_final) > 0.005
                or abs(line.liters - line.src_liters) > 0.005
            )

    @api.depends('start_reading', 'end_reading')
    def _compute_distance(self):
        # Para una línea importada los km son la distancia GPS, no la diferencia entre lecturas
        # (que son horas de horómetro): solo se recalcula en las líneas manuales.
        manual = self.filtered(lambda line: not line.usage_id)
        super(StepExpenseVehicleLine, manual)._compute_distance()

    @api.constrains('usage_id', 'vehicle_id', 'sheet_id')
    def _check_usage_consistency(self):
        for line in self.filtered('usage_id'):
            if line.usage_id.company_id != line.sheet_id.company_id:
                raise ValidationError(_('La sesión de Tracker pertenece a otra empresa que la rendición.'))
            if not line.vehicle_id or line.usage_id.vehicle_id != line.vehicle_id:
                raise ValidationError(_('El vehículo de la línea no coincide con el de la sesión de Tracker.'))

    # ------------------------------------------------------------------
    # Protección de lo importado
    # ------------------------------------------------------------------
    def _assert_tracker_edit_allowed(self):
        locked = self.filtered(lambda line: line.usage_id and line.sheet_id.state != 'draft')
        if locked:
            raise UserError(_(
                'La rendición %s ya no está en borrador: los recorridos traídos desde Tracker no pueden '
                'modificarse ni eliminarse.'
            ) % ', '.join(locked.mapped('sheet_id.display_name')))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('usage_id') or vals.get('source') == 'tracker':
                if not self.env.context.get(IMPORT_CONTEXT):
                    raise UserError(_('Las líneas de Tracker solo se crean con el asistente «Traer desde Tracker».'))
                sheet = self.env['hr.expense.sheet'].browse(vals.get('sheet_id'))
                if sheet.state != 'draft':
                    raise UserError(_('Solo se pueden traer recorridos a una rendición en borrador.'))
        return super().create(vals_list)

    def write(self, vals):
        tracked = self.filtered('usage_id')
        if tracked:
            if PROTECTED_FIELDS & set(vals) and not self.env.context.get(IMPORT_CONTEXT):
                raise UserError(_('Los datos de origen de un recorrido de Tracker no se pueden editar.'))
            tracked._assert_tracker_edit_allowed()
        elif 'usage_id' in vals and vals['usage_id'] and not self.env.context.get(IMPORT_CONTEXT):
            raise UserError(_('Las líneas de Tracker solo se crean con el asistente «Traer desde Tracker».'))
        return super().write(vals)

    def unlink(self):
        self._assert_tracker_edit_allowed()
        return super().unlink()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def action_open_usage(self):
        self.ensure_one()
        if not self.usage_id:
            raise UserError(_('Esta línea se ingresó manualmente: no tiene sesión de origen.'))
        return {
            'type': 'ir.actions.act_window', 'res_model': 'step.tracker.usage', 'view_mode': 'form',
            'res_id': self.usage_id.id, 'target': 'current',
        }
