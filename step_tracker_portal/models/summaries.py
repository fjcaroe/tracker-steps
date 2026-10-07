"""Read-only incident summaries. Tracker remains the source of truth."""
import logging
import requests
from odoo import api, fields, models
from ..signing import sign_identity

_logger = logging.getLogger(__name__)


class ProtectionSummary(models.Model):
    _name = 'step.tracker.protection.summary'
    _description = 'Resumen de incidente Steps Protección'
    _order = 'updated_at desc, id desc'

    name = fields.Char(required=True, readonly=True)
    tracker_id = fields.Char(required=True, readonly=True, index=True)
    asset_id = fields.Char(readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    vehicle_id = fields.Many2one('fleet.vehicle', readonly=True, check_company=True)
    kind = fields.Char(string='Tipo', readonly=True)
    severity = fields.Selection([('high', 'Alta'), ('medium', 'Media')], readonly=True)
    state = fields.Selection([('open', 'Abierto'), ('acknowledged', 'Reconocido'), ('closed', 'Cerrado')], readonly=True)
    responsible = fields.Char(string='Responsable Tracker', readonly=True)
    opened_at = fields.Datetime(string='Abierto', readonly=True)
    updated_at = fields.Datetime(string='Actualizado en Tracker', readonly=True)
    _sql_constraints = [('incident_company_unique', 'unique(tracker_id,company_id)', 'Incidente ya sincronizado.')]


class ProtectionSync(models.Model):
    _name = 'step.tracker.protection.sync'
    _description = 'Cursor de sincronización de Protección'

    company_id = fields.Many2one('res.company', required=True, index=True)
    cursor = fields.Char(readonly=True)
    last_sync = fields.Datetime(readonly=True)
    last_error = fields.Char(readonly=True)
    _sql_constraints = [('company_unique', 'unique(company_id)', 'Ya existe un cursor para esta compañía.')]

    @api.model
    def _cron_sync(self):
        key = self.env['ir.config_parameter'].sudo().get_param('step_tracker_portal.bridge_key')
        if not key:
            return
        for company in self.env['res.company'].sudo().search([]):
            try:
                with self.env.cr.savepoint():
                    state = self.sudo().search([('company_id', '=', company.id)], limit=1)
                    if not state:
                        state = self.sudo().create({'company_id': company.id})
                    # Transaction lock prevents cron/manual concurrency on a cursor.
                    self.env.cr.execute('SELECT id FROM step_tracker_protection_sync WHERE id=%s FOR UPDATE', [state.id])
                    state.invalidate_recordset()
                    for page in range(10):
                        token = sign_identity(self.env.cr.dbname, company.id, 'odoo:incident-sync', 'manager', key)
                        response = requests.get('http://127.0.0.1:8000/v1/sync/changes',
                            headers={'Authorization': 'Bearer '+token}, params={'cursor': state.cursor or '', 'limit': 100}, timeout=20)
                        response.raise_for_status()
                        data = response.json()
                        for event in data['items']:
                            incident, asset = event['incident'], event['asset']
                            if not incident or not asset:
                                continue
                            vehicle_id = False
                            if asset['source_id'].startswith('odoo:fleet.vehicle:'):
                                vehicle = self.env['fleet.vehicle'].sudo().browse(int(asset['source_id'].split(':')[-1])).exists()
                                if vehicle and vehicle.company_id == company:
                                    vehicle_id = vehicle.id
                            values = {'name': asset['name'], 'tracker_id': incident['id'], 'asset_id': asset['asset_id'],
                                'company_id': company.id, 'vehicle_id': vehicle_id, 'kind': incident['type'],
                                'severity': incident['severity'], 'state': incident['state'], 'responsible': incident['responsible'],
                                'opened_at': incident['created_at'][:19].replace('T', ' '),
                                'updated_at': incident['updated_at'][:19].replace('T', ' ')}
                            model = self.env['step.tracker.protection.summary'].sudo()
                            row = model.search([('company_id', '=', company.id), ('tracker_id', '=', incident['id'])], limit=1)
                            row.write(values) if row else model.create(values)
                        state.write({'cursor': data['cursor'], 'last_sync': fields.Datetime.now(), 'last_error': False})
                        if not data['has_more']:
                            break
            except Exception as exc:
                # No tokens or request headers in logs. Retry the unchanged cursor next time.
                _logger.warning('Protección sync failed for company %s: %s', company.id, type(exc).__name__)
                state = self.sudo().search([('company_id', '=', company.id)], limit=1)
                if state:
                    state.last_error = type(exc).__name__
