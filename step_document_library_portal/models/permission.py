from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IndividualPermission(models.TransientModel):
    _inherit = "step.document.library.permission"

    user_id = fields.Many2one(string="Cuenta del destinatario", domain=lambda self: self._recipient_domain())

    @api.model
    def _recipient_domain(self):
        groups = self.env.ref("base.group_user") | self.env.ref("base.group_portal")
        return [("active", "=", True), ("groups_id", "in", groups.ids)]

    def action_apply(self):
        self.ensure_one()
        if self.user_id.share and self.role == "edit":
            raise ValidationError(_("El acceso externo a este archivo permite lectura."))
        return super().action_apply()


class LinkPermission(models.TransientModel):
    _name = "step.document.library.link.permission"
    _description = "Acceso externo mediante enlace"

    document_id = fields.Many2one("documents.document", string="Archivo", required=True, readonly=True)
    level = fields.Selection([("none", "Solo destinatarios"), ("view", "Lectura mediante enlace")],
                             string="Acceso", required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        document = self.document_id
        self.env.cr.execute("SELECT access_via_link FROM documents_document WHERE id=%s FOR UPDATE", [document.id])
        row = self.env.cr.fetchone()
        document.invalidate_recordset(["user_permission", "may_manage_access", "access_via_link"])
        document.action_manage_access()
        if not row or row[0] not in ("none", "view"):
            raise ValidationError(_("Esta configuración de acceso requiere revisión."))
        if self.level != row[0]:
            self.env.cr.execute("""
                UPDATE documents_document SET access_via_link=%s, write_uid=%s, write_date=timezone('UTC',now())
                 WHERE id=%s
            """, [self.level, self.env.uid, document.id])
            document.invalidate_recordset(["access_via_link", "user_permission", "may_manage_access"])
        return {"type": "ir.actions.act_window_close"}


class Document(models.Model):
    _inherit = "documents.document"

    def action_external_link_permission(self):
        self.ensure_one()
        self.action_manage_access()
        if self.access_via_link not in ("none", "view"):
            raise ValidationError(_("Esta configuración de acceso requiere revisión."))
        return {"type": "ir.actions.act_window", "name": _("Acceso mediante enlace"),
                "res_model": "step.document.library.link.permission", "view_mode": "form", "target": "new",
                "context": {"default_document_id": self.id, "default_level": self.access_via_link}}
