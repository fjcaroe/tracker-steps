import re

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import content_disposition, request

from .custody import MODEL


class CAFCustodyController(http.Controller):
    @http.route('/steps/caf/custody/<string:record_id>/download', type='http', auth='user', methods=['GET'])
    def download_caf(self, record_id, **kwargs):
        if not re.fullmatch(r'-?[0-9]{1,10}', str(record_id)):
            raise AccessError('Registro CAF inválido.')
        record = request.env[MODEL].browse(int(record_id)).exists()
        record.ensure_one()
        raw = record._step_custody_original_bytes()
        return request.make_response(raw, headers=[
            ('Content-Type', 'application/xml'),
            ('Content-Disposition', content_disposition(record.filename or 'CAF.xml')),
            ('Cache-Control', 'no-store, private'), ('Pragma', 'no-cache'),
        ])
