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
        return self._external_item_by_digest(reference_digest, ["binary"])

    @api.model
    def _external_item(self, reference):
        if not isinstance(reference, str) or not 1 <= len(reference) <= 256:
            return self.browse()
        return self._external_item_by_digest(sha256(reference.encode()).hexdigest(), ["binary", "folder"])

    @api.model
    def _external_item_by_digest(self, reference_digest, item_types):
        user = self.env.user
        portal_contact = user.partner_id.id if user.has_group("base.group_portal") and not user._is_public() else None
        self.env.cr.execute("""
            SELECT d.id, d.type, d.access_via_link,
                   coalesce(a.role IN ('view','edit') AND
                       (a.expiration_date IS NULL OR a.expiration_date > timezone('UTC',now())),false)
              FROM documents_document d LEFT JOIN documents_access a ON a.document_id=d.id AND a.partner_id=%s
             WHERE d.step_portal_reference_hash=%s AND d.active IS TRUE AND d.type=ANY(%s)
               AND (d.type='folder' OR d.attachment_id IS NOT NULL)
        """, [portal_contact, reference_digest, item_types])
        row = self.env.cr.fetchone()
        if not row:
            return self.browse()
        record = self.browse(row[0])
        if row[2] in ("view", "edit") or row[3] or (user._is_internal() and record.has_access("read")):
            return record.sudo()
        return self.browse()

    @api.model
    def _listed_folder_children(self, folder):
        folder.ensure_one()
        if folder.type != "folder":
            return self.browse()
        user = self.env.user
        if user._is_internal():
            return self.search([("folder_id", "=", folder.id), ("type", "in", ("binary", "folder"))])
        partner = user.partner_id.id if user.has_group("base.group_portal") and not user._is_public() else None
        self.env.cr.execute("""
            SELECT c.id FROM documents_document c JOIN documents_document p ON p.id=c.folder_id
              LEFT JOIN documents_access pa ON pa.document_id=p.id AND pa.partner_id=%s
              LEFT JOIN documents_access ca ON ca.document_id=c.id AND ca.partner_id=%s
             WHERE p.id=%s AND p.active IS TRUE AND c.active IS TRUE AND c.type IN ('folder','binary') AND (
                (ca.role IN ('view','edit') AND (ca.expiration_date IS NULL OR ca.expiration_date > timezone('UTC',now())))
                OR (c.is_access_via_link_hidden IS NOT TRUE AND c.access_via_link IN ('view','edit') AND (
                    p.access_via_link IN ('view','edit') OR (pa.role IN ('view','edit') AND
                    (pa.expiration_date IS NULL OR pa.expiration_date > timezone('UTC',now()))))))
             ORDER BY c.type='folder' DESC, c.name, c.id
        """, [partner, partner, folder.id])
        return self.sudo().browse([row[0] for row in self.env.cr.fetchall()])

    @api.model
    def _remember_folder(self, folder):
        user = self.env.user
        if user._is_public() or not user.has_group("base.group_portal"):
            return
        partner = user.partner_id.id
        # Only an already authorized first visit can create a visit row. The existing role,
        # expiration and original date survive subsequent visits or grant changes.
        self.env.cr.execute("""
            INSERT INTO documents_access(document_id,partner_id,last_access_date)
            SELECT d.id,%s,timezone('UTC',now()) FROM documents_document d
             WHERE d.id=%s AND d.type='folder' AND d.active IS TRUE AND
                (d.access_via_link IN ('view','edit') OR EXISTS (
                    SELECT 1 FROM documents_access a WHERE a.document_id=d.id AND a.partner_id=%s
                      AND a.role IN ('view','edit') AND (a.expiration_date IS NULL OR a.expiration_date>timezone('UTC',now()))))
            ON CONFLICT(document_id,partner_id) DO UPDATE SET last_access_date=excluded.last_access_date
                WHERE documents_access.last_access_date IS NULL
        """, [partner, folder.id, partner])

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
