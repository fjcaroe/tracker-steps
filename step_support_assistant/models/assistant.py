import datetime
import json
import os
import re

import requests

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from ..core import ANSWER_SCHEMA, INSTRUCTIONS, NO_EVIDENCE, parse_response, rank_sources


class AssistantUsage(models.Model):
    _name = "step.assistant.usage"
    _description = "Consumo del asistente (sin contenido de consultas)"
    _order = "create_date desc"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", required=True, index=True, ondelete="cascade")
    status = fields.Selection([(item, label) for item, label in [
        ("pending", "En curso"), ("answered", "Respondida"), ("no_evidence", "Sin información"),
        ("out_of_scope", "Fuera de alcance"), ("unavailable", "No disponible"),
    ]], default="pending", required=True)
    input_tokens = fields.Integer(readonly=True)
    output_tokens = fields.Integer(readonly=True)

    @api.autovacuum
    def _gc_usage(self):
        self.sudo().search([("create_date", "<", fields.Datetime.now() - datetime.timedelta(days=30))]).unlink()


class SupportAssistant(models.AbstractModel):
    _name = "step.support.assistant"
    _description = "Asistente de soporte Steps"

    def _check_user(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("El asistente está disponible para usuarios internos de Odoo."))

    def _config(self):
        params = self.env["ir.config_parameter"].sudo()
        def limit(name, default, maximum):
            try:
                return max(1, min(maximum, int(params.get_param("step_support_assistant." + name, default))))
            except (TypeError, ValueError):
                return default
        model = params.get_param("step_support_assistant.model", "gpt-4.1-mini")
        if not re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", model or ""):
            model = "gpt-4.1-mini"
        return {
            "enabled": params.get_param("step_support_assistant.enabled", "False") in ("True", "true", "1"),
            "key": os.environ.get("OPENAI_API_KEY", "").strip(),
            "model": model,
            "hourly_limit": limit("hourly_limit", 20, 200),
            "daily_limit": limit("daily_limit", 500, 10000),
        }

    @api.model
    def get_bootstrap(self):
        self._check_user()
        config = self._config()
        sources = self.env["step.assistant.article"]._available_sources()
        return {"ready": bool(config["enabled"] and config["key"]),
                "articles": [{"id": source["id"], "title": source["title"]} for source in sources],
                "support_url": "https://soporte.stepsapp.cl",
                "notice": "Los datos reales se consultan dentro de Odoo. Las preguntas de ayuda y sus guías se envían a OpenAI solo si la IA está habilitada. Evita incluir contraseñas o datos personales y revisa las fuentes."}

    def _reserve_usage(self, config):
        # Serializes reservations across workers for a base-wide daily cap.
        # No question, reply, identifier or credential is written to this model.
        self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (736482, 1))
        now = fields.Datetime.now()
        usage = self.env["step.assistant.usage"].sudo()
        if usage.search_count([("user_id", "=", self.env.uid),
                               ("create_date", ">=", now - datetime.timedelta(hours=1))]) >= config["hourly_limit"]:
            raise UserError(_("Alcanzaste el límite de consultas por hora. Puedes consultar los artículos de ayuda o contactar a soporte."))
        if usage.search_count([("create_date", ">=", now.replace(hour=0, minute=0, second=0, microsecond=0))]) >= config["daily_limit"]:
            raise UserError(_("El asistente alcanzó el límite diario. Consulta los artículos de ayuda o contacta a soporte."))
        return usage.create({"user_id": self.env.uid, "company_id": self.env.company.id})

    @api.model
    def ask(self, question, previous_questions=None):
        self._check_user()
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
            raise ValidationError(_("Escribe una consulta de entre 1 y 2.000 caracteres."))
        if previous_questions is None:
            previous_questions = []
        if not isinstance(previous_questions, list) or len(previous_questions) > 4 or any(
                not isinstance(item, str) or len(item) > 2000 for item in previous_questions):
            raise ValidationError(_("El contexto de la conversación no es válido."))
        question = question.strip()
        business = self._business_question(question)
        if business is not None:
            return business
        sources = rank_sources(question, self.env["step.assistant.article"]._available_sources(), previous_questions)
        if not sources:
            return {"status": "no_evidence", "answer": NO_EVIDENCE, "sources": []}
        config = self._config()
        if not config["enabled"] or not config["key"]:
            return {"status": "unavailable", "answer": "Las respuestas con IA aún no están habilitadas. Puedes abrir los artículos de ayuda relacionados o contactar a soporte.",
                    "sources": [{"id": source["id"], "title": source["title"], "quote": ""} for source in sources]}
        usage = self._reserve_usage(config)
        try:
            result, token_usage = self._request(config, question, previous_questions, sources)
        except (requests.RequestException, ValueError, KeyError, TypeError):
            # Never log the HTTP exception: it may carry authorization headers or prompt data.
            result, token_usage = {"status": "unavailable", "answer": "No pude obtener una respuesta verificada en este momento. Consulta las fuentes de ayuda o contacta a soporte.",
                                   "sources": [{"id": source["id"], "title": source["title"], "quote": ""} for source in sources]}, {}
        usage.write({"status": result["status"],
                     "input_tokens": self._safe_token_count(token_usage.get("input_tokens")),
                     "output_tokens": self._safe_token_count(token_usage.get("output_tokens"))})
        return result

    def _safe_token_count(self, value):
        return max(0, min(value, 2147483647)) if type(value) is int else 0

    def _request(self, config, question, previous_questions, sources):
        payload = {
            "model": config["model"], "store": False, "max_output_tokens": 1800,
            "instructions": INSTRUCTIONS,
            "input": [{"role": "user", "content": json.dumps({
                "question": question, "previous_questions": previous_questions,
                "sources": [{"id": source["id"], "title": source["title"], "content": source["content"]} for source in sources],
            }, ensure_ascii=False)}],
            "text": {"format": {"type": "json_schema", "name": "steps_help_answer", "strict": True, "schema": ANSWER_SCHEMA}},
        }
        # Fixed destination: neither user nor settings can redirect credentials.
        response = requests.post("https://api.openai.com/v1/responses", json=payload,
                                 headers={"Authorization": "Bearer " + config["key"]},
                                 timeout=(5, 30), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError("provider unavailable")
        body = response.json()
        usage = body.get("usage")
        return parse_response(body, sources), usage if isinstance(usage, dict) else {}
