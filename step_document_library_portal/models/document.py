from hashlib import sha256

from odoo import api, models


class Document(models.Model):
    _inherit = "documents.document"

    def init(self):
        super().init()
        self.env.cr.execute("ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS step_portal_reference_hash char(64)")
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS step_document_portal_reference_hash_idx
            ON documents_document(step_portal_reference_hash) WHERE step_portal_reference_hash IS NOT NULL
        """)

    @api.model
    def _external_file(self, reference):
        """Resolve an adopted native reference without granting general access to attachments."""
        if not isinstance(reference, str) or not 1 <= len(reference) <= 256:
            return self.browse()
        user = self.env.user
        portal_contact = user.partner_id.id if user.has_group("base.group_portal") and not user._is_public() else None
        self.env.cr.execute("""
            SELECT d.id, d.access_via_link, EXISTS (
                SELECT 1 FROM documents_access a WHERE a.document_id=d.id AND a.partner_id=%s
                  AND a.role IN ('view','edit') AND (a.expiration_date IS NULL OR a.expiration_date > timezone('UTC',now()))
            ) FROM documents_document d WHERE d.step_portal_reference_hash=%s
            AND d.active IS TRUE AND d.type='binary' AND d.attachment_id IS NOT NULL
        """, [portal_contact, sha256(reference.encode()).hexdigest()])
        row = self.env.cr.fetchone()
        if not row:
            return self.browse()
        record = self.browse(row[0])
        if row[1] in ("view", "edit") or row[2] or (user._is_internal() and record.has_access("read")):
            # Only this exact native reference and its checked permission authorize reading the linked attachment.
            return record.sudo()
        return self.browse()
