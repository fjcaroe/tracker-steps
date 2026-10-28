from odoo import api, models


class Partner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        for node in arch.xpath("//field[@widget='field_partner_autocomplete']"):
            node.attrib.pop('widget', None)
        return arch, view

    @api.model
    def autocomplete_by_name(self, query, query_country_id=False, timeout=15):
        return []

    @api.model
    def autocomplete_by_vat(self, vat, query_country_id=False, timeout=15):
        return []

    @api.model
    def enrich_by_duns(self, duns, timeout=15):
        return {}

    @api.model
    def enrich_by_gst(self, gst, timeout=15):
        return {}

    @api.model
    def enrich_by_domain(self, domain, timeout=15):
        return {}


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        info['iap_company_enrich'] = False
        return info
