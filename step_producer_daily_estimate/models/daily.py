"""T78: one shared market master and daily distribution of native weekly plans."""
from datetime import timedelta
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

FRUIT_TYPES = [('conventional', 'Convencional'), ('organic', 'Orgánico')]


class Market(models.Model):
    _name = 'step.fruit.market'
    _description = 'Mercado de fruta'
    _order = 'code, name'

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    abbreviation = fields.Char(string='Abreviatura', required=True)
    active = fields.Boolean(default=True)
    _sql_constraints = [('market_code_unique', 'unique(code)', 'El código de mercado ya existe.')]


class Estimate(models.Model):
    _inherit = 'step.export.estimate'

    user_id = fields.Many2one(string='Agrónomo')
    fruit_type = fields.Selection(FRUIT_TYPES, string='Tipo fruta')

    def write(self, vals):
        if {'user_id', 'approved_by_id', 'fruit_type'}.intersection(vals) and any(r.state in ('current', 'replaced') for r in self):
            raise UserError(_('Cree una nueva versión para cambiar agrónomo, autoriza o tipo de fruta.'))
        return super().write(vals)


class EstimateLine(models.Model):
    _inherit = 'step.export.estimate.line'

    market_id = fields.Many2one('step.fruit.market', string='Mercado')


class EstimateWeek(models.Model):
    _inherit = 'step.export.estimate.week'

    week_number = fields.Integer(string='Semana ISO', compute='_compute_week_number')
    day_ids = fields.One2many('step.export.estimate.day', 'week_id', string='Estimación diaria')

    @api.depends('week_start')
    def _compute_week_number(self):
        for row in self:
            row.week_number = row.week_start.isocalendar().week if row.week_start else 0


class DailyEstimate(models.Model):
    _name = 'step.export.estimate.day'
    _description = 'Estimación diaria de cosecha'
    _order = 'date, week_id, id'
    _rec_name = 'date'

    week_id = fields.Many2one('step.export.estimate.week', string='Estimación semanal', required=True, ondelete='restrict', index=True)
    date = fields.Date(string='Día', required=True, index=True)
    process_kg = fields.Float(string='Kilos proceso', digits=(16, 3))
    export_kg = fields.Float(string='Kilos exportación', digits=(16, 3))
    estimate_id = fields.Many2one(related='week_id.line_id.estimate_id', store=True)
    line_id = fields.Many2one(related='week_id.line_id', store=True)
    company_id = fields.Many2one(related='estimate_id.company_id', store=True)
    season_id = fields.Many2one(related='estimate_id.season_id', store=True, string='Temporada')
    species_id = fields.Many2one(related='line_id.species_id', store=True, string='Especie')
    variety_id = fields.Many2one(related='line_id.variety_id', store=True, string='Variedad')
    agronomist_id = fields.Many2one(related='estimate_id.user_id', store=True, string='Agrónomo')
    fruit_type = fields.Selection(related='estimate_id.fruit_type', store=True, string='Tipo fruta')
    delivery_kind = fields.Selection(related='line_id.delivery_kind', store=True, string='Delivery Kind')
    producer_id = fields.Many2one(related='estimate_id.producer_id', store=True, string='Productor')
    market_id = fields.Many2one(related='line_id.market_id', store=True, string='Mercado')
    state = fields.Selection(related='estimate_id.state', store=True, string='Estado estimación')
    week_number = fields.Integer(related='week_id.week_number')
    six_week_period = fields.Char(string='Período de seis semanas', compute='_compute_six_week_period', store=True,
        help='Bloques consecutivos de 42 días, desde el lunes 05-01-1970. El filtro próximas seis semanas es móvil.')

    _sql_constraints = [('daily_week_date_unique', 'unique(week_id,date)', 'Ya hay una distribución para esta semana y día.'),
        ('daily_nonnegative', 'check(process_kg>=0 AND export_kg>=0)', 'Los kilos no pueden ser negativos.')]

    @api.depends('date')
    def _compute_six_week_period(self):
        anchor = fields.Date.to_date('1970-01-05')
        for row in self:
            start = anchor + timedelta(days=((row.date-anchor).days // 42)*42) if row.date else False
            row.six_week_period = '%s / %s' % (start, start+timedelta(days=41)) if start else False

    @api.constrains('week_id', 'date', 'process_kg', 'export_kg')
    def _check_distribution(self):
        for row in self:
            if not row.week_id.week_start <= row.date < row.week_id.week_start + timedelta(days=7):
                raise ValidationError(_('El día debe pertenecer a la semana seleccionada.'))
            if row.estimate_id.state != 'current':
                raise ValidationError(_('La distribución diaria requiere una estimación vigente.'))
        for week in self.mapped('week_id'):
            process = week.export_kg / week.line_id.export_percentage if week.line_id.delivery_kind == 'process' and week.line_id.export_percentage > 0 else 0
            if float_compare(sum(week.day_ids.mapped('export_kg')), week.export_kg, precision_digits=3) > 0 or float_compare(sum(week.day_ids.mapped('process_kg')), process, precision_digits=3) > 0:
                raise ValidationError(_('La distribución diaria no puede superar los kilos de la semana.'))

    def write(self, vals):
        if vals and any(r.estimate_id.state != 'current' for r in self):
            raise UserError(_('La planificación de una versión reemplazada queda conservada.'))
        old = self.mapped('week_id')
        result = super().write(vals)
        old.mapped('day_ids')._check_distribution()
        return result

    def unlink(self):
        if any(r.estimate_id.state != 'current' for r in self):
            raise UserError(_('La planificación de una versión reemplazada queda conservada.'))
        return super().unlink()


class DailyWizard(models.TransientModel):
    _name = 'step.export.estimate.daily.wizard'
    _description = 'Distribución lineal de estimaciones: próximas tres semanas'

    @api.model
    def _default_start(self):
        today = fields.Date.context_today(self)
        return today - timedelta(days=today.weekday())

    start_date = fields.Date(string='Lunes inicial', required=True, default=_default_start)
    working_days = fields.Selection([('5', 'Lunes a viernes'), ('6', 'Lunes a sábado'), ('7', 'Lunes a domingo')], string='Distribución', required=True, default='5')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def action_distribute(self):
        self.ensure_one()
        if self.start_date.weekday() != 0:
            raise ValidationError(_('La fecha inicial debe ser lunes.'))
        if self.company_id not in self.env.companies:
            raise UserError(_('Seleccione una empresa habilitada.'))
        weeks = self.env['step.export.estimate.week'].search([
            ('line_id.estimate_id.company_id', '=', self.company_id.id), ('line_id.estimate_id.state', '=', 'current'),
            ('week_start', '>=', self.start_date), ('week_start', '<', self.start_date + timedelta(days=21))])
        days = int(self.working_days)
        created = skipped = 0
        for week in weeks:
            if week.day_ids:
                skipped += 1
                continue
            process = week.export_kg / week.line_id.export_percentage if week.line_id.delivery_kind == 'process' and week.line_id.export_percentage > 0 else 0
            self.env['step.export.estimate.day'].create([{
                'week_id': week.id, 'date': week.week_start + timedelta(days=i),
                'process_kg': process/days, 'export_kg': week.export_kg/days,
            } for i in range(days)])
            created += 1
        action = self.env.ref('step_producer_daily_estimate.daily_action').read()[0]
        action['domain'] = [('company_id', '=', self.company_id.id), ('date', '>=', self.start_date), ('date', '<', self.start_date + timedelta(days=21))]
        action['name'] = _('Estimación diaria: %(created)s semanas nuevas; %(skipped)s conservadas', created=created, skipped=skipped)
        return action


class EstimateReport(models.Model):
    _inherit = 'step.producer.estimate.report'

    agronomist_id = fields.Many2one('res.users', string='Agrónomo', readonly=True)
    fruit_type = fields.Selection(FRUIT_TYPES, string='Tipo fruta', readonly=True)
    market_id = fields.Many2one('step.fruit.market', string='Mercado', readonly=True)

    def init(self):
        super().init()
        self.env.cr.execute('SELECT pg_get_viewdef(%s::regclass, true)', (self._table,))
        original = self.env.cr.fetchone()[0].rstrip().rstrip(';')
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute('CREATE VIEW step_producer_estimate_report AS SELECT r.*,e.user_id AS agronomist_id,e.fruit_type,l.market_id FROM (' + original + ') r JOIN step_export_estimate e ON e.id=r.estimate_id JOIN step_export_estimate_line l ON l.id=r.line_id')
