from urllib.parse import urlsplit

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


PERMISSIONS = [("none", "Sin acceso"), ("view", "Lectura"), ("edit", "Edición")]


class Document(models.Model):
    _name = "documents.document"
    _description = "Biblioteca documental"
    _auto = False
    _order = "name, id"

    name = fields.Char(readonly=True)
    type = fields.Selection([("folder", "Carpeta"), ("binary", "Archivo"), ("url", "Enlace")], readonly=True)
    active = fields.Boolean(readonly=True)
    folder_id = fields.Many2one("documents.document", string="Carpeta", readonly=True)
    attachment_id = fields.Many2one("ir.attachment", string="Archivo", readonly=True)
    company_id = fields.Many2one("res.company", string="Compañía", readonly=True)
    owner_id = fields.Many2one("res.users", string="Propietario", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contacto", readonly=True)
    res_model = fields.Char(readonly=True)
    res_id = fields.Integer(readonly=True)
    url = fields.Char(readonly=True)
    access_internal = fields.Selection(PERMISSIONS, string="Acceso interno", readonly=True)
    access_via_link = fields.Selection(PERMISSIONS, string="Acceso por enlace", readonly=True)
    is_access_via_link_hidden = fields.Boolean(readonly=True)
    is_pinned_folder = fields.Boolean(readonly=True)
    access_ids = fields.One2many("documents.access", "document_id", string="Accesos", readonly=True)
    user_permission = fields.Selection(PERMISSIONS, compute="_compute_permission", search="_search_permission")
    may_manage_access = fields.Boolean(compute="_compute_permission")

    def init(self):
        self.env.cr.execute("ALTER TABLE documents_document ADD COLUMN IF NOT EXISTS step_original_url_hash varchar")
        self.env.cr.execute("""CREATE UNIQUE INDEX IF NOT EXISTS step_document_library_original_url
                               ON documents_document (step_original_url_hash) WHERE step_original_url_hash IS NOT NULL""")

    @api.model
    def _adopt_dashboard(self):
        menu = self.env.ref("documents.dashboard")
        target = self.env.ref("step_document_library.action_library")
        if menu.action == target:
            return
        if menu.action._name != "ir.actions.act_window" or menu.action.res_model != self._name:
            raise ValidationError(_("La acción del menú original no abre la biblioteca documental."))
        menu.write({"action": "ir.actions.act_window,%d" % target.id})

    @api.model
    def _permissions(self):
        """Read original grants in the current company context. No document payload enters this query."""
        # Odoo expands record-rule domains on a sudo recordset. Validate the caller's
        # selected companies under their own identity before deriving document permissions.
        scope = self.env(user=self.env.uid, su=False)
        user = scope.user
        if not user.has_group("base.group_user"):
            return {}
        companies = scope.companies.ids
        assigned = user.sudo().with_context(active_test=False).company_ids.ids
        is_admin = user.has_group("documents.group_documents_system")
        is_manager = user.has_group("documents.group_documents_manager")
        self.env["documents.access"].flush_model(["document_id", "partner_id", "role", "expiration_date"])
        self.env.cr.execute("""
            WITH RECURSIVE explicit_grants AS (
                SELECT document_id, max(CASE role WHEN 'edit' THEN 2 WHEN 'view' THEN 1 ELSE 0 END) AS level
                  FROM documents_access
                 WHERE partner_id = %s AND (expiration_date IS NULL OR expiration_date > timezone('UTC', now()))
                 GROUP BY document_id
            ), direct AS (
                SELECT d.id, d.folder_id, d.company_id, d.access_internal, d.access_via_link, d.is_access_via_link_hidden,
                       CASE
                         WHEN d.company_id = ANY(%s) AND NOT (d.company_id = ANY(%s)) THEN 0
                         WHEN %s THEN 2
                         WHEN d.company_id IS NOT NULL AND NOT (d.company_id = ANY(%s)) THEN 0
                         WHEN d.owner_id = %s THEN 2
                         ELSE greatest(coalesce(g.level,0), CASE d.access_internal
                              WHEN 'edit' THEN 2 WHEN 'view' THEN 1 ELSE 0 END)
                       END AS level
                  FROM documents_document d LEFT JOIN explicit_grants g ON g.document_id=d.id
            ), visible(id, level) AS (
                SELECT id, CASE WHEN %s AND access_internal IN ('view','edit') THEN 2 ELSE level END
                  FROM direct WHERE level > 0
                UNION
                SELECT d.id, CASE d.access_via_link WHEN 'edit' THEN 2 ELSE 1 END
                  FROM direct d JOIN visible parent ON parent.id = d.folder_id
                 WHERE d.access_via_link IN ('view','edit') AND d.is_access_via_link_hidden IS NOT TRUE
                   AND (d.company_id IS NULL OR d.company_id = ANY(%s) OR NOT (d.company_id = ANY(%s)))
            )
            SELECT id, max(level) FROM visible GROUP BY id
        """, [user.partner_id.id, assigned, companies, is_admin, companies, user.id,
              is_manager, companies, assigned])
        return {ident: ("view" if level == 1 else "edit") for ident, level in self.env.cr.fetchall()}

    @api.depends_context("uid", "allowed_company_ids", "company")
    def _compute_permission(self):
        grants = self._permissions()
        manager = self.env.user.has_group("documents.group_documents_manager")
        for document in self:
            role = grants.get(document.id, "none")
            document.user_permission = role
            document.may_manage_access = (role == "edit" and document.type == "binary"
                                          and (manager or document.owner_id == self.env.user))

    @api.model
    def _search_permission(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(_("Operador de permiso no compatible."))
        included = set(value) if operator in ("in", "not in") else {value}
        if operator in ("!=", "not in"):
            included = {p[0] for p in PERMISSIONS} - included
        roles = self._permissions()
        if "none" in included:
            return [("id", "not in", [i for i, role in roles.items() if role not in included])]
        return [("id", "in", [i for i, role in roles.items() if role in included])]

    def action_open(self):
        self.ensure_one()
        self.check_access("read")
        if self.type == "folder":
            action = self.env["ir.actions.actions"]._for_xml_id("step_document_library.action_library")
            action.update(name=self.name, domain=[("folder_id", "=", self.id)])
            return action
        if self.type == "url":
            target = urlsplit(self.url or "")
            if target.scheme not in ("https", "http") or not target.netloc:
                raise UserError(_("El enlace no contiene una dirección web válida."))
            return {"type": "ir.actions.act_url", "url": self.url, "target": "new"}
        if self.type != "binary" or not self.attachment_id:
            raise UserError(_("Este elemento no contiene un archivo disponible."))
        self.attachment_id.check_access("read")
        return {"type": "ir.actions.act_url", "url": "/web/content/%d?download=true" % self.attachment_id.id,
                "target": "download"}

    def action_manage_access(self):
        self.ensure_one()
        self.check_access("write")
        if not self.may_manage_access:
            raise AccessError(_("Solo un propietario o gestor con permiso de edición puede modificar el acceso."))
        return {"type": "ir.actions.act_window", "res_model": "step.document.library.permission",
                "view_mode": "form", "target": "new", "context": {"default_document_id": self.id}}

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_("La biblioteca conserva los documentos originales."))

    def write(self, vals):
        raise AccessError(_("Esta biblioteca permite gestionar el permiso individual del archivo."))

    def unlink(self):
        raise AccessError(_("La biblioteca conserva los documentos originales."))


class DocumentAccess(models.Model):
    _name = "documents.access"
    _description = "Acceso individual a documento"
    _auto = False
    _log_access = False

    document_id = fields.Many2one("documents.document", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contacto", readonly=True)
    role = fields.Selection(PERMISSIONS[1:], string="Permiso", readonly=True)
    expiration_date = fields.Datetime(string="Vencimiento", readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_("Utilice el formulario de permisos del archivo."))

    def write(self, vals):
        raise AccessError(_("Utilice el formulario de permisos del archivo."))

    def unlink(self):
        raise AccessError(_("Utilice el formulario de permisos del archivo."))


class DocumentPermission(models.TransientModel):
    _name = "step.document.library.permission"
    _description = "Permiso individual sobre un archivo"

    document_id = fields.Many2one("documents.document", string="Archivo", required=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contacto del usuario interno", required=True)
    role = fields.Selection([("none", "Retirar permiso individual"), *PERMISSIONS[1:]],
                            string="Permiso individual", required=True, default="view")

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        doc = self.document_id
        # Lock the document before checking the actor's current permission or changing its grant.
        self.env.cr.execute("SELECT id FROM documents_document WHERE id=%s FOR UPDATE", [doc.id])
        doc.invalidate_recordset(["user_permission", "may_manage_access"])
        doc.action_manage_access()
        partner = self.partner_id
        partner.check_access("read")
        if not self.env["res.users"].sudo().search_count([
            ("active", "=", True), ("share", "=", False), ("partner_id", "=", partner.id),
        ]):
            raise ValidationError(_("Seleccione el contacto de un usuario interno activo."))
        access = self.env["documents.access"]
        grants = access.search([("document_id", "=", doc.id), ("partner_id", "=", partner.id)])
        if len(grants) > 1:
            raise ValidationError(_("Existen varios permisos individuales para este contacto."))
        changed = False
        if self.role == "none":
            if grants.role:
                # Keep the native row and visit history. A null role removes only the explicit grant.
                super(DocumentAccess, grants).write({"role": False})
                changed = True
        elif grants:
            if grants.expiration_date and grants.expiration_date <= fields.Datetime.now():
                raise ValidationError(_("Este permiso venció. Seleccione un permiso vigente."))
            if grants.role != self.role:
                super(DocumentAccess, grants).write({"role": self.role})
                changed = True
        else:
            super(DocumentAccess, access).create({"document_id": doc.id, "partner_id": partner.id, "role": self.role})
            changed = True
        if changed:
            # All mutations of this file's permissions update the locked document.
            # Concurrent grants then serialize using the standard Odoo retry mechanism.
            self.env.cr.execute("UPDATE documents_document SET write_uid=%s, write_date=timezone('UTC', now()) WHERE id=%s",
                                [self.env.uid, doc.id])
        doc.invalidate_recordset(["user_permission", "may_manage_access"])
        return {"type": "ir.actions.act_window_close"}
