from odoo import fields, models, _
from odoo.exceptions import UserError


class SagService(models.Model):
    _name = 'step.packing.sag.service'
    _description = 'Tipo de servicio SAG'
    _order = 'sequence,id'

    name = fields.Char('Servicio', required=True, translate=True)
    code = fields.Char('Código interno', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    file_format = fields.Selection([('INS', 'INS — inspección/reinspección/fumigación'),
        ('INT', 'INT — recepción interplanta/devolución'), ('REP', 'REP — repaletizaje'),
        ('DET', 'DET — anulación'), ('DES', 'DES — despacho')], string='Archivo Anexo 5')
    sanitary = fields.Boolean('Registra resultado fitosanitario', default=True)
    reinspection = fields.Boolean('Admite tarjas con inspecciones anteriores')
    _sql_constraints = [('code_unique', 'unique(code)', 'El código de servicio debe ser único.')]

    def write(self, vals):
        if {'file_format', 'sanitary', 'reinspection'} & vals.keys() and self.env['step.packing.inspection'].search_count([('sag_service_id', 'in', self.ids)]):
            raise UserError(_('Conserve la configuración del servicio ya utilizado. Cree otro tipo si cambia su alcance.'))
        return super().write(vals)


class Partner(models.Model):
    _inherit = 'res.partner'
    step_sag_plant_number = fields.Char('Número SAG de establecimiento sin región', help='Identificador oficial sin región. Anexo 5: nombre de archivo de 3 dígitos y encabezado de 4.')


class Country(models.Model):
    _inherit = 'res.country'
    step_sag_code = fields.Char('Código país SAG', help='Código numérico oficial SAG (3 posiciones); no es el código ISO.')


class City(models.Model):
    _inherit = 'res.city'
    # No province model exists in this installation. Province is descriptive
    # metadata on the existing commune; it is never substituted for its region.
    step_sag_province_name = fields.Char('Provincia de la comuna (SAG)')


class Fundo(models.Model):
    _inherit = 'step.fundo'
    step_sag_city_id = fields.Many2one('res.city', string='Comuna de origen SAG')


class Package(models.Model):
    _inherit = 'stock.quant.package'
    step_sag_folio = fields.Char('Folio numérico SAG sin verificador', help='Complete si la referencia de tarja no representa el folio oficial. No cambia la referencia ni el código de la tarja.')
