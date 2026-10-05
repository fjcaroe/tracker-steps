from odoo import fields, models
from odoo.tools import html2plaintext


class KnowledgeApproval(models.Model):
    _name = "step.assistant.knowledge.approval"
    _description = "Artículo de Conocimiento aprobado para soporte"
    _rec_name = "article_id"

    article_id = fields.Many2one("knowledge.article", "Artículo de Conocimiento", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", "Compañía", help="Vacío: todas las compañías. Los permisos originales del artículo se mantienen.")
    group_ids = fields.Many2many("res.groups", string="Grupos autorizados", help="Restricción adicional; no concede acceso al artículo.")
    keywords = fields.Char("Palabras de búsqueda")
    published = fields.Boolean("Aprobado para el asistente", default=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [("article_unique", "unique(article_id)", "Este artículo ya tiene una aprobación. Edite la aprobación existente.")]


class AssistantKnowledgeSources(models.Model):
    _inherit = "step.assistant.article"

    def _available_sources(self):
        sources = super()._available_sources()
        Knowledge = self.env["knowledge.article"]
        if not Knowledge.has_access("read"):
            return sources
        # Only approval metadata is elevated. Read original articles in the caller's environment.
        approvals = self.env["step.assistant.knowledge.approval"].sudo().search([
            ("active", "=", True), ("published", "=", True),
            "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id),
            "|", ("group_ids", "=", False), ("group_ids", "in", self.env.user.groups_id.ids),
        ])
        keywords = {approval.article_id.id: approval.keywords or "" for approval in approvals}
        articles = Knowledge.search([("id", "in", list(keywords)), ("active", "=", True),
                                     ("to_delete", "=", False), ("user_has_access", "=", True),
                                     ("is_template", "=", False)])
        for article in articles:
            if not article.user_can_read:
                continue
            # Strip embedded widgets/markup. No attachments, images, children or business records are fetched.
            content = html2plaintext(article.body or "").strip()[:12000]
            if content:
                sources.append({"id": -article.id, "title": article.name or "Artículo de Conocimiento",
                                "content": content, "keywords": keywords[article.id]})
        return sources
