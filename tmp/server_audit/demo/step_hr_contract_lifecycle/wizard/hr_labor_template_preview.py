# -*- coding: utf-8 -*-
from odoo import fields, models


class HrLaborTemplatePreview(models.TransientModel):
    _name = "hr.labor.template.preview"
    _description = "Vista previa de plantilla laboral"

    template_id = fields.Many2one("hr.labor.template", readonly=True)
    preview_html = fields.Html(readonly=True, sanitize=False)
