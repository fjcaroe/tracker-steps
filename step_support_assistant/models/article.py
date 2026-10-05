from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssistantArticle(models.Model):
    _name = "step.assistant.article"
    _description = "Fuente aprobada de ayuda Steps"
    _order = "sequence, name, id"

    name = fields.Char("Título", required=True, index=True)
    sequence = fields.Integer("Orden", default=100)
    category = fields.Selection([
        ("general", "Ayuda general"), ("accounting", "Contabilidad y tesorería"),
        ("colaciones", "Colaciones"),
    ], string="Tema", default="general", required=True, index=True)
    content = fields.Text("Instrucciones para usuarios", required=True)
    keywords = fields.Char("Palabras de búsqueda")
    provenance = fields.Char("Referencia de revisión", help="Documento o módulo usado para verificar estas instrucciones. No incluya secretos.")
    active = fields.Boolean(default=True)
    published = fields.Boolean("Aprobado para el asistente", default=False)
    company_id = fields.Many2one("res.company", "Compañía", index=True,
                                 help="Vacío: guía compartida entre compañías.")
    group_ids = fields.Many2many("res.groups", string="Grupos autorizados",
                                 help="Vacío: todos los usuarios internos. Un grupo coincidente habilita esta fuente.")
    module_name = fields.Char("Módulo requerido", help="Nombre técnico del módulo que debe estar instalado. Vacío para ayuda general.")
    required_model = fields.Char("Permiso de lectura requerido", help="Modelo del módulo al que el usuario debe tener acceso de lectura. Por ejemplo, step.colacion.registration.")

    @api.constrains("content", "name", "module_name")
    def _check_source(self):
        import re
        for article in self:
            if not article.content.strip() or len(article.content) > 12000:
                raise ValidationError(_("Cada artículo debe contener entre 1 y 12.000 caracteres."))
            if article.module_name and not re.fullmatch(r"[a-z][a-z0-9_]*", article.module_name):
                raise ValidationError(_("Use un nombre técnico de módulo válido."))

    def _guide_profile(self):
        profile = self.env["ir.config_parameter"].sudo().get_param(
            "step_support_assistant.guide_profile", "general")
        return "accounting" if profile == "accounting" else "general"

    def _available_sources(self):
        """Record rules apply before retrieving text. Never elevate article reads."""
        domain = [
            ("published", "=", True), ("active", "=", True),
            "|", ("company_id", "=", False), ("company_id", "=", self.env.company.id),
            "|", ("group_ids", "=", False), ("group_ids", "in", self.env.user.groups_id.ids),
        ]
        if self._guide_profile() == "accounting":
            domain.append(("category", "in", ["general", "accounting"]))
        articles = self.search(domain)
        required = set(articles.mapped("module_name")) - {False, ""}
        # Module state is technical metadata; article permissions remain those of the caller.
        installed = set(self.env["ir.module.module"].sudo().search([
            ("name", "in", list(required)), ("state", "=", "installed")
        ]).mapped("name")) if required else set()
        return [{"id": article.id, "title": article.name, "content": article.content,
                 "keywords": article.keywords or ""}
                for article in articles
                if (not article.module_name or article.module_name in installed)
                and (not article.required_model or
                     article.required_model in self.env.registry.models and
                     self.env[article.required_model].has_access("read"))]
