"""Explicit commercial classification on existing documents and live reports."""
from odoo import _, fields, models
from odoo.exceptions import UserError

MODES = [('firm', 'A firme'), ('consignment', 'Consignación')]
HELP = ('A firme: el precio del contrato es final y no tiene liquidación. '
        'Consignación: el precio es referencial; el precio final se determina '
        'según la venta en el ciclo de Liquidación de productor.')

class PurchaseContract(models.Model):
    _inherit = 'step.producer.purchase.contract'
    purchase_mode = fields.Selection(MODES, string='Modalidad de compra', tracking=True, help=HELP)

    def write(self, vals):
        if 'purchase_mode' in vals and any(r.state != 'draft' and r.purchase_mode
                and r.purchase_mode != vals['purchase_mode'] for r in self):
            raise UserError(_('Cree una revisión para cambiar la modalidad de un contrato confirmado.'))
        return super().write(vals)

    def action_revise(self):
        self.ensure_one()
        return super(PurchaseContract, self.with_context(default_purchase_mode=self.purchase_mode)).action_revise()

class Estimate(models.Model):
    _inherit = 'step.export.estimate'
    purchase_mode = fields.Selection(MODES, string='Modalidad de compra', tracking=True, help=HELP)

    def write(self, vals):
        if 'purchase_mode' in vals and any(r.state in ('current', 'replaced') and r.purchase_mode
                and r.purchase_mode != vals['purchase_mode'] for r in self):
            raise UserError(_('Cree otra versión para cambiar la modalidad de una estimación vigente.'))
        return super().write(vals)

def extend_report(model, source, link):
    # Reuse the original projection and all its valuations and identities.
    model.env.cr.execute('SELECT pg_get_viewdef(%s::regclass, true)', (model._table,))
    original = model.env.cr.fetchone()[0].rstrip().rstrip(';')
    # Names below are static code constants, never user input.
    model.env.cr.execute('CREATE OR REPLACE VIEW '+model._table+' AS SELECT r.*, s.purchase_mode '
        'FROM ('+original+') r JOIN '+source+' s ON s.id=r.'+link)

class ContractReport(models.Model):
    _inherit = 'step.producer.contract.report'
    purchase_mode = fields.Selection(MODES, string='Modalidad de compra', readonly=True, help=HELP)

    def init(self):
        super().init()
        extend_report(self, 'step_producer_purchase_contract', 'contract_id')

class EstimateReport(models.Model):
    _inherit = 'step.producer.estimate.report'
    purchase_mode = fields.Selection(MODES, string='Modalidad de compra', readonly=True, help=HELP)

    def init(self):
        super().init()
        extend_report(self, 'step_export_estimate', 'estimate_id')
