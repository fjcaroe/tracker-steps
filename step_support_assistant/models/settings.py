import os

from odoo import fields, models


class AssistantSettings(models.TransientModel):
    _inherit = "res.config.settings"

    step_assistant_enabled = fields.Boolean("Activar respuestas con IA", config_parameter="step_support_assistant.enabled")
    step_assistant_guide_profile = fields.Selection([
        ("general", "Todas las aplicaciones disponibles"),
        ("accounting", "Contabilidad y tesorería"),
    ], string="Enfoque de las guías", default="general",
        config_parameter="step_support_assistant.guide_profile")
    step_assistant_model = fields.Char("Modelo de OpenAI", default="gpt-4.1-mini", config_parameter="step_support_assistant.model")
    step_assistant_hourly_limit = fields.Integer("Consultas por hora y usuario", default=20, config_parameter="step_support_assistant.hourly_limit")
    step_assistant_daily_limit = fields.Integer("Consultas por día en esta base", default=500, config_parameter="step_support_assistant.daily_limit")
    step_assistant_key_available = fields.Boolean("Clave disponible en el servidor", compute="_compute_key_available")

    def _compute_key_available(self):
        for record in self:
            record.step_assistant_key_available = bool(os.environ.get("OPENAI_API_KEY", "").strip())
