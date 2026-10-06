"""Adopt the existing freight folio without resetting its counter or ranges."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env.ref('step_operations_ui.sequence_freight_order', raise_if_not_found=False):
        sequences = env['ir.sequence'].search([('code', '=', 'gastos.fletes')])
        if sequences:
            sequence = sequences.filtered(lambda item: not item.company_id) or sequences[:1]
            if len(sequence) != 1:
                raise RuntimeError('Ambiguous freight folio counter; preserve and review before migration')
            env['ir.model.data'].create({
                'module': 'step_operations_ui', 'name': 'sequence_freight_order',
                'model': 'ir.sequence', 'res_id': sequence.id, 'noupdate': True,
            })
