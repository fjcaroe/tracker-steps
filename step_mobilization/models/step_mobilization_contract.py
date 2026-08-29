# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

TEMPLATE_VAR_RE = re.compile(r'\{\{\s*(\w+)\s*\}\}')
DIRECTION_LABELS = {'ida': 'Ida', 'vuelta': 'Regreso', 'ida_vuelta': 'Ida y regreso'}


class StepMobilizationContractTemplate(models.Model):
    """Plantilla de contrato versionada. El texto legal fijo del anexo 1
    fuente se traduce a variables ({{ }}) resueltas en el QWeb del reporte;
    nada de razón social/ciudad/multas queda hardcodeado aquí. Requiere
    revisión legal/prevención antes de poder usarse para emitir (is_validated)."""
    _name = 'step.mobilization.contract.template'
    _description = 'Plantilla de contrato de movilización'
    _order = 'version desc'

    name = fields.Char(string='Nombre', required=True)
    version = fields.Integer(string='Versión', required=True, default=1)
    active = fields.Boolean(default=True)
    body = fields.Html(string='Cuerpo del contrato', required=True,
                        help='Usa variables como {{company_name}}, {{transporter_name}}, etc. '
                             'La tabla de tarifas se agrega automáticamente al final.')
    is_validated = fields.Boolean(
        string='Revisada por legal/prevención', default=False,
        help='No se puede emitir un contrato con una plantilla no validada.')
    validated_by_id = fields.Many2one('res.users', string='Validada por', readonly=True)
    validated_date = fields.Datetime(string='Fecha de validación', readonly=True)
    notes = fields.Text(string='Notas de la revisión')

    def action_validate(self):
        for template in self:
            template.write({
                'is_validated': True,
                'validated_by_id': self.env.user.id,
                'validated_date': fields.Datetime.now(),
            })


class StepMobilizationContractRateSnapshot(models.Model):
    """Fila congelada de tarifa al momento de emitir el contrato. No se
    recalcula ni se referencia en vivo a product.pricelist.move.line: si la
    tarifa cambia después, este registro no se altera."""
    _name = 'step.mobilization.contract.rate.snapshot'
    _description = 'Tarifa congelada en un contrato de movilización'

    contract_id = fields.Many2one('step.mobilization.contract', required=True,
                                   ondelete='cascade', index=True)
    route_name = fields.Char(string='Recorrido', required=True)
    direction = fields.Char(string='Sentido', required=True)
    min_passengers = fields.Integer(string='Mínimo de pasajeros')
    amount = fields.Float(string='Valor', required=True)
    currency_id = fields.Many2one('res.currency', required=True)
    valid_from = fields.Date(string='Vigente desde')
    valid_to = fields.Date(string='Vigente hasta')


class StepMobilizationContract(models.Model):
    _name = 'step.mobilization.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Contrato de prestación de servicio de movilización'
    _order = 'contract_date desc, id desc'

    name = fields.Char(string='Número', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    partner_id = fields.Many2one('res.partner', string='Transportista', required=True, tracking=True,
                                  domain=[('step_trans_person', '=', True)])
    company_representative_name = fields.Char(string='Representante empresa')
    company_representative_id_number = fields.Char(string='RUT/ID representante empresa')
    company_representative_role = fields.Char(string='Cargo representante empresa')
    transporter_representative_name = fields.Char(string='Representante transportista')
    transporter_representative_id_number = fields.Char(string='RUT/ID representante transportista')
    city = fields.Char(string='Ciudad')
    contract_date = fields.Date(string='Fecha', default=fields.Date.context_today)
    season_label = fields.Char(string='Temporada/período')
    service_name = fields.Char(string='Faena/servicio')
    date_start = fields.Date(string='Vigencia desde', required=True)
    date_end = fields.Date(string='Vigencia hasta', required=True)
    currency_id = fields.Many2one('res.currency', string='Moneda',
                                   default=lambda self: self.env.company.currency_id)
    route_ids = fields.Many2many('hr.route', string='Recorridos')
    vehicle_ids = fields.Many2many('fleet.vehicle', string='Vehículos')
    driver_partner_ids = fields.Many2many(
        'res.partner', 'step_mobilization_contract_driver_rel', 'contract_id', 'partner_id',
        string='Choferes', domain=[('step_chofer', '=', True)])
    responsible_user_id = fields.Many2one('res.users', string='Responsable',
                                           default=lambda self: self.env.user)
    inspector_name = fields.Char(string='Fiscalizador')
    arbitrator_name = fields.Char(string='Árbitro')
    template_id = fields.Many2one('step.mobilization.contract.template', string='Plantilla', required=True)
    rate_snapshot_ids = fields.One2many('step.mobilization.contract.rate.snapshot', 'contract_id',
                                         string='Tarifas congeladas', copy=False, readonly=True)
    pdf_generated = fields.Boolean(string='PDF emitido', copy=False, default=False, readonly=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('review', 'En revisión'),
            ('approved', 'Aprobado'),
            ('active', 'Vigente'),
            ('expired', 'Vencido'),
            ('terminated', 'Terminado'),
            ('cancelled', 'Cancelado'),
        ],
        string='Estado', default='draft', required=True, tracking=True, copy=False)

    @api.model
    def _next_sequence(self, company_id):
        Sequence = self.env['ir.sequence'].sudo()
        seq = Sequence.search([('code', '=', 'step_mobilization_contract_seq'),
                                ('company_id', '=', company_id)], limit=1)
        if not seq:
            seq = Sequence.create({
                'name': _('Contratos de movilización (%s)') % self.env['res.company'].browse(company_id).name,
                'code': 'step_mobilization_contract_seq',
                'prefix': 'CTM',
                'padding': 4,
                'company_id': company_id,
            })
        return seq.next_by_id()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('Nuevo'):
                company_id = vals.get('company_id') or self.env.company.id
                vals['name'] = self._next_sequence(company_id) or _('Nuevo')
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'review'})

    def action_approve(self):
        if not self.env.user.has_group('step_mobilization.group_mobilization_approver'):
            raise UserError(_('No tiene permiso para aprobar contratos de movilización.'))
        for contract in self:
            if not contract.template_id.is_validated:
                raise UserError(_('La plantilla "%s" no ha sido revisada por legal/prevención.')
                                 % contract.template_id.name)
            contract.write({'state': 'approved'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_terminate(self):
        self.write({'state': 'terminated'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _freeze_rate_snapshot(self):
        """Congela las tarifas asociadas a los recorridos del contrato la
        primera vez que se emite el PDF. Idempotente: no vuelve a congelar si
        ya existe una instantánea."""
        self.ensure_one()
        if self.rate_snapshot_ids:
            return
        pricelists = self.env['product.pricelist'].search([
            ('moviliza', '=', True), ('transporte_id', '=', self.partner_id.id)])
        lines = pricelists.mapped('move_item').filtered(lambda l: l.recorrido_id in self.route_ids)
        vals = []
        for line in lines:
            vals.append((0, 0, {
                'route_name': line.recorrido_id.display_name,
                'direction': DIRECTION_LABELS.get(line.cobro_type, line.cobro_type or ''),
                'min_passengers': line.min_quantity,
                'amount': line.tarifa,
                'currency_id': line.currency_id.id or self.currency_id.id,
                'valid_from': line.date_start,
                'valid_to': line.date_end,
            }))
        self.rate_snapshot_ids = vals

    def _template_variables(self):
        self.ensure_one()
        return {
            'company_name': self.company_id.name or '',
            'company_vat': self.company_id.vat or '',
            'company_address': self.company_id.partner_id.contact_address or '',
            'company_representative_name': self.company_representative_name or '',
            'company_representative_id_number': self.company_representative_id_number or '',
            'company_representative_role': self.company_representative_role or '',
            'transporter_name': self.partner_id.name or '',
            'transporter_vat': self.partner_id.vat or '',
            'transporter_address': self.partner_id.contact_address or '',
            'transporter_representative_name': self.transporter_representative_name or '',
            'transporter_representative_id_number': self.transporter_representative_id_number or '',
            'city': self.city or '',
            'contract_date': self.contract_date and self.contract_date.strftime('%d-%m-%Y') or '',
            'season_label': self.season_label or '',
            'service_name': self.service_name or '',
            'date_start': self.date_start and self.date_start.strftime('%d-%m-%Y') or '',
            'date_end': self.date_end and self.date_end.strftime('%d-%m-%Y') or '',
            'inspector_name': self.inspector_name or '',
            'arbitrator_name': self.arbitrator_name or '',
        }

    def render_body(self):
        """Sustituye las variables {{ }} de la plantilla por los datos reales
        del contrato. Ninguna razón social/ciudad/representante queda
        hardcodeada en la plantilla; todo viene de estos campos."""
        self.ensure_one()
        variables = self._template_variables()
        body = self.template_id.body or ''
        return TEMPLATE_VAR_RE.sub(lambda m: variables.get(m.group(1), m.group(0)), body)

    def action_generate_pdf(self):
        self.ensure_one()
        if not self.template_id.is_validated:
            raise UserError(_('No se puede emitir un contrato con una plantilla sin validar.'))
        self._freeze_rate_snapshot()
        self.pdf_generated = True
        return self.env.ref('step_mobilization.action_report_step_mobilization_contract').report_action(self)
