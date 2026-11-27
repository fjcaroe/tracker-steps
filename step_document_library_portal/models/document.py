from hashlib import sha256
from urllib.parse import quote

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError


class Document(models.Model):
    _inherit = "documents.document"

    def init(self):
        super().init()
        self.env.cr.execute("""
            ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS step_portal_reference_hash char(64),
                       ADD COLUMN IF NOT EXISTS step_portal_reference_prefix text,
                       ADD COLUMN IF NOT EXISTS step_portal_reference_suffix text
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS step_document_portal_reference_hash_idx
            ON documents_document(step_portal_reference_hash) WHERE step_portal_reference_hash IS NOT NULL
        """)

    @api.model
    def _external_file(self, reference):
        """Resolve an adopted native reference without granting general access to attachments."""
        if not isinstance(reference, str) or not 1 <= len(reference) <= 256:
            return self.browse()
        return self._external_file_by_digest(sha256(reference.encode()).hexdigest())

    @api.model
    def _external_file_by_digest(self, reference_digest):
        user = self.env.user
        portal_contact = user.partner_id.id if user.has_group("base.group_portal") and not user._is_public() else None
        self.env.cr.execute("""
            SELECT d.id, d.access_via_link, EXISTS (
                SELECT 1 FROM documents_access a WHERE a.document_id=d.id AND a.partner_id=%s
                  AND a.role IN ('view','edit') AND (a.expiration_date IS NULL OR a.expiration_date > timezone('UTC',now()))
            ) FROM documents_document d WHERE d.step_portal_reference_hash=%s
            AND d.active IS TRUE AND d.type='binary' AND d.attachment_id IS NOT NULL
        """, [portal_contact, reference_digest])
        row = self.env.cr.fetchone()
        if not row:
            return self.browse()
        record = self.browse(row[0])
        if row[1] in ("view", "edit") or row[2] or (user._is_internal() and record.has_access("read")):
            # Only this exact native reference and its checked permission authorize reading the linked attachment.
            return record.sudo()
        return self.browse()


    def _original_external_reference(self):
        self.ensure_one()
        self.env.cr.execute("""
            SELECT step_portal_reference_prefix || document_token || step_portal_reference_suffix,
                   step_portal_reference_hash FROM documents_document WHERE id=%s
        """, [self.id])
        row = self.env.cr.fetchone()
        if not row or not row[0] or sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValidationError(_("Falta verificar el enlace de este elemento con su referencia original."))
        return row[0]

    def _editor_external_url(self):
        self.ensure_one()
        self.check_access("write")
        if self.user_permission != "edit" or self.type not in ("binary", "folder"):
            raise AccessError(_("Necesita permiso de edición para copiar este enlace."))
        return self.get_base_url().rstrip("/") + "/odoo/documents/" + quote(self._original_external_reference(), safe="")

    def action_copy_external_url(self):
        self.ensure_one()
        self._editor_external_url()
        return {"type": "ir.actions.act_window", "name": _("Copiar enlace"),
                "res_model": "step.document.library.reference", "view_mode": "form", "target": "new",
                "context": {"default_document_id": self.id}}
