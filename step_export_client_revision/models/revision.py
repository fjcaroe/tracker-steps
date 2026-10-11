from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

ROLES = {'carrier_id': 'step_export_carrier', 'consignee_id': 'step_export_consignee',
         'notify_id': 'step_export_notify', 'freight_forwarder_id': 'step_export_forwarder',
         'customs_agent_id': 'step_export_customs_agent'}


class FruitColor(models.Model):
    _name = 'step.fruit.color'
    _description = 'Color de fruta'
    _order = 'sequence, code, name'
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    _sql_constraints = [('code_company_unique', 'unique(code,company_id)', 'El código del color debe ser único por empresa.')]


class Partner(models.Model):
    _inherit = 'res.partner'
    step_export_carrier = fields.Boolean(string='Naviera o aerolínea')
    step_export_consignee = fields.Boolean(string='Consignatario')
    step_export_notify = fields.Boolean(string='Notify')
    step_export_forwarder = fields.Boolean(string='Agencia de carga')
    step_export_customs_agent = fields.Boolean(string='Agente de aduana')

    @api.onchange(*ROLES.values())
    def _onchange_export_roles(self):
        for partner in self:
            if any(partner[name] for name in ROLES.values()):
                partner.step_export = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(name) for name in ROLES.values()):
                vals['step_export'] = True
        return super().create(vals_list)

    def write(self, vals):
        if any(vals.get(name) for name in ROLES.values()):
            vals = dict(vals, step_export=True)
        return super().write(vals)


class Shipment(models.Model):
    _inherit = 'step.export.export'
    carrier_id = fields.Many2one(domain=[('step_export_carrier', '=', True)])
    consignee_id = fields.Many2one(domain=[('step_export_consignee', '=', True)])
    notify_id = fields.Many2one(domain=[('step_export_notify', '=', True)])
    freight_forwarder_id = fields.Many2one(domain=[('step_export_forwarder', '=', True)])
    customs_agent_id = fields.Many2one(domain=[('step_export_customs_agent', '=', True)])


class Program(models.Model):
    _inherit = 'step.export.sales.program'
    transport_type = fields.Selection(selection=lambda self: self.env['step.export.export']._fields['transport_type']._description_selection(self.env), string='Tipo de embarque')

    @api.model_create_multi
    def create(self, vals_list):
        # A default for new programs must not label all historical programs as sea.
        for vals in vals_list:
            vals.setdefault('transport_type', 'sea')
        return super().create(vals_list)

    def write(self, vals):
        if 'transport_type' in vals and any(p.state in ('current', 'replaced') for p in self):
            raise UserError(_('Cree una versión nueva para modificar el tipo de embarque.'))
        return super().write(vals)


class ProgramWeek(models.Model):
    _inherit = 'step.export.sales.program.line'
    week_end = fields.Date(compute='_compute_week_end', store=True, string='Semana hasta')
    company_id = fields.Many2one(related='program_id.company_id', store=True)
    species_id = fields.Many2one(related='program_id.species_id', store=True, string='Especie')
    season_id = fields.Many2one(related='program_id.season_id', store=True, string='Temporada')
    transport_type = fields.Selection(related='program_id.transport_type', store=True, string='Tipo de embarque')
    program_state = fields.Selection(related='program_id.state', store=True, string='Estado del programa')

    @api.depends('week_start')
    def _compute_week_end(self):
        for line in self:
            line.week_end = line.week_start + timedelta(days=7) if line.week_start else False

    @api.depends('program_id.name', 'week_start', 'container_qty', 'amount_usd')
    def _compute_display_name(self):
        for line in self:
            line.display_name = '%s | %s cont. | USD %.2f' % (line.program_id.name, line.container_qty, line.amount_usd)


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    step_export_sale_mode_id = fields.Many2one('step.export.sale.mode', string='Modalidad de venta', check_company=True)

    def _step_export_report_title(self, proforma=False):
        return 'Invoice' if proforma else 'Sales Order'

    @api.onchange('step_export_shipment_id')
    def _onchange_shipment_sale_mode(self):
        for order in self:
            if order.step_export_shipment_id and not order.step_export_sale_mode_id:
                order.step_export_sale_mode_id = order.step_export_shipment_id.sale_mode_id
