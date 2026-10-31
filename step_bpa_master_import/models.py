from odoo import _, api, fields, models


class ActiveIngredient(models.Model):
    _inherit = 'step.agriculture.active.ingredient'

    name = fields.Char(string='Sustancias activas')

    @api.model
    def get_import_templates(self):
        return [{'label': _('Sustancias activas'),
                 'template': '/step_bpa_master_import/static/xlsx/sustancias_activas.xlsx'}]


class PesticideAptitude(models.Model):
    _inherit = 'step.agriculture.pesticide.aptitude'

    @api.model
    def get_import_templates(self):
        return [{'label': _('Aptitudes plaguicidas'),
                 'template': '/step_bpa_master_import/static/xlsx/aptitudes_plaguicidas.xlsx'}]
