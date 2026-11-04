from odoo import http
from odoo.http import content_disposition, request
from werkzeug.exceptions import NotFound


class PackingReport(http.Controller):

    @http.route('/packing/process/<int:production_id>/xlsx', type='http', auth='user', readonly=True)
    def download(self, production_id):
        production = request.env['step.packing.production'].browse(production_id).exists()
        if not production:
            raise NotFound()
        content = production._packing_process_xlsx()
        return request.make_response(content, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(f'Packing - {production.name}.xlsx')),
            ('Cache-Control', 'private, no-store'),
        ])
