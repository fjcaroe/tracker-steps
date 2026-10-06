import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.step_tracker_portal.signing import sign_identity

_logger = logging.getLogger(__name__)

GPS_TIMEOUT = 20
SOURCE_PREFIX = 'odoo:fleet.vehicle:'


class StepTrackerAssetLink(models.Model):
    """Correspondencia servidor a servidor: base Odoo + compañía + activo GPS ↔ vehículo de flota.

    Un ``asset_id`` UUID, un ``machine_id`` entero de Tracker y un ``fleet.vehicle.id`` no son
    intercambiables, y el activo nunca se asocia por nombre o patente. Se crea de dos formas:

    * ``odoo_import``: Tracker informa ``source_id = odoo:fleet.vehicle:<id>`` (activos importados desde
      Flota) y se valida que el vehículo exista y sea de la misma compañía;
    * ``manual``: un administrador de Tracker indica el activo y el vehículo; el activo se verifica contra
      Tracker con la identidad firmada de la compañía (un activo ajeno responde 404).
    """
    _name = 'step.tracker.asset.link'
    _description = 'Activo de Tracker ↔ vehículo de Odoo'
    _inherit = ['mail.thread']
    _order = 'company_id, vehicle_id'
    _check_company_auto = True

    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True,
                                 default=lambda self: self.env.company, tracking=True)
    asset_id = fields.Char(string='Activo en Tracker', required=True, index=True, tracking=True)
    asset_name = fields.Char(string='Nombre del activo (informativo)', readonly=True)
    asset_plate = fields.Char(string='Patente del activo (informativa)', readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True, index=True,
                                 check_company=True, tracking=True)
    source = fields.Selection([('odoo_import', 'Importado desde Flota'), ('manual', 'Manual')],
                              string='Origen del vínculo', required=True, default='manual', readonly=True)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Char(string='Observación')

    _sql_constraints = [
        ('asset_company_uniq', 'unique(company_id, asset_id)',
         'Este activo de Tracker ya está vinculado a un vehículo en esta empresa.'),
    ]

    def init(self):
        # Un vehículo tiene a lo más un activo vigente por compañía (los archivados conservan el historial).
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS step_tracker_asset_link_vehicle_active_uniq
            ON step_tracker_asset_link (company_id, vehicle_id) WHERE active
        """)

    @api.constrains('vehicle_id', 'company_id')
    def _check_vehicle_company(self):
        for link in self:
            if link.vehicle_id.company_id and link.vehicle_id.company_id != link.company_id:
                raise ValidationError(_('El vehículo %s pertenece a otra empresa.') % link.vehicle_id.display_name)

    # ------------------------------------------------------------------
    # Permisos
    # ------------------------------------------------------------------
    def _check_tracker_manager(self):
        user = self.env.user
        if not (user.has_group('base.group_system') or user.has_group('step_tracker_portal.group_tracker_manager')):
            raise AccessError(_('Solo un administrador de Tracker puede vincular activos con vehículos.'))

    # ------------------------------------------------------------------
    # Llamadas servidor a servidor a la API GPS (identidad firmada, sin exponer claves)
    # ------------------------------------------------------------------
    @api.model
    def _gps_base_url(self):
        url = self.env['ir.config_parameter'].sudo().get_param('step_management_costs_tracker.gps_api_url')
        return (url or 'http://127.0.0.1:8000').rstrip('/')

    @api.model
    def _gps_get(self, company, path, params=None):
        key = self.env['ir.config_parameter'].sudo().get_param('step_tracker_portal.bridge_key')
        if not key:
            raise UserError(_('Tracker está pendiente de configurar en esta base (falta la clave del puente).'))
        token = sign_identity(self.env.cr.dbname, company.id, self.env.uid, 'manager', key)
        try:
            return requests.get(f'{self._gps_base_url()}/v1/{path}', headers={'Authorization': 'Bearer ' + token},
                                params=params, timeout=GPS_TIMEOUT)
        except requests.RequestException as exc:
            _logger.warning('GPS API no disponible (%s)', type(exc).__name__)
            raise UserError(_('La API de Tracker no está disponible; vuelva a intentar.')) from exc

    @api.model
    def _remote_asset(self, company, asset_id):
        """Datos del activo si pertenece al cliente de la compañía; ``None`` si Tracker responde 404."""
        response = self._gps_get(company, 'assets/%s' % asset_id)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise UserError(_('Tracker rechazó la consulta del activo (%s).') % response.status_code)
        return response.json()

    # ------------------------------------------------------------------
    # Creación validada
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get('step_tracker_link_sync'):
            self._check_tracker_manager()
        for vals in vals_list:
            if vals.get('source', 'manual') == 'manual' and not self.env.context.get('step_tracker_skip_remote'):
                company = self.env['res.company'].browse(vals.get('company_id') or self.env.company.id)
                asset = self._remote_asset(company, (vals.get('asset_id') or '').strip())
                if asset is None:
                    raise ValidationError(_('El activo indicado no existe en Tracker para la empresa %s.') % company.name)
                vals.update(asset_id=vals['asset_id'].strip(), asset_name=asset.get('name'), asset_plate=asset.get('plate'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('step_tracker_link_sync'):
            self._check_tracker_manager()
        if {'asset_id', 'company_id'} & set(vals) and not self.env.context.get('step_tracker_link_sync'):
            raise UserError(_('El activo de un vínculo no se cambia: archive el vínculo y cree uno nuevo.'))
        return super().write(vals)

    # ------------------------------------------------------------------
    # Sincronización desde Tracker (activos importados desde Flota)
    # ------------------------------------------------------------------
    @api.model
    def sync_from_tracker(self, company=None):
        """Crea los vínculos de los activos que Tracker importó desde ``fleet.vehicle``.

        Devuelve ``{'created', 'existing', 'conflicts', 'skipped'}``. No cambia vínculos existentes: si
        un activo ya apunta a otro vehículo, se informa como conflicto y se conserva el vínculo vigente.
        """
        self._check_tracker_manager()
        company = company or self.env.company
        result = {'created': 0, 'existing': 0, 'conflicts': 0, 'skipped': 0}
        after = ''
        Link = self.with_context(step_tracker_link_sync=True).sudo()
        while True:
            response = self._gps_get(company, 'asset-sources', params={'after': after, 'limit': 200})
            if response.status_code == 403:
                raise AccessError(_('Tracker no autoriza la consulta de vínculos para este usuario.'))
            if response.status_code != 200:
                raise UserError(_('Tracker respondió %s al consultar los activos.') % response.status_code)
            page = response.json()
            for item in page['items']:
                source = item.get('source_id') or ''
                if not source.startswith(SOURCE_PREFIX):
                    result['skipped'] += 1           # activo manual: requiere vínculo explícito
                    continue
                try:
                    vehicle_id = int(source[len(SOURCE_PREFIX):])
                except ValueError:
                    result['skipped'] += 1
                    continue
                vehicle = self.env['fleet.vehicle'].sudo().browse(vehicle_id).exists()
                if not vehicle or (vehicle.company_id and vehicle.company_id != company):
                    result['skipped'] += 1
                    continue
                existing = Link.with_context(active_test=False).search([
                    ('company_id', '=', company.id), '|', ('asset_id', '=', item['asset_id']),
                    '&', ('vehicle_id', '=', vehicle.id), ('active', '=', True)])
                if existing:
                    same = existing.filtered(lambda l: l.asset_id == item['asset_id'] and l.vehicle_id == vehicle)
                    result['existing' if same else 'conflicts'] += 1
                    continue
                Link.create({
                    'company_id': company.id, 'asset_id': item['asset_id'], 'vehicle_id': vehicle.id,
                    'asset_name': item.get('name'), 'asset_plate': item.get('plate'), 'source': 'odoo_import'})
                result['created'] += 1
            after = page.get('next_cursor')
            if not after:
                return result

    def action_sync_from_tracker(self):
        result = self.sync_from_tracker()
        message = _('%(created)s vínculo(s) creado(s), %(existing)s ya existían, %(conflicts)s en conflicto, '
                    '%(skipped)s activo(s) sin origen Odoo (manuales) omitidos.') % result
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Vínculos con Tracker'), 'message': message, 'type': 'success', 'sticky': False}}

    # ------------------------------------------------------------------
    # Resolución (solo dentro de la compañía: un ID ajeno no encuentra nada)
    # ------------------------------------------------------------------
    @api.model
    def _resolve(self, company, asset_id):
        return self.search([('company_id', '=', company.id), ('asset_id', '=', asset_id)], limit=1)
