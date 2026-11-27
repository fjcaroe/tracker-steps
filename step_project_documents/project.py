from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class DocumentTag(models.Model):
    _name = "documents.tag"
    _description = "Tag"
    _auto = False
    _log_access = True
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer()
    color = fields.Integer()
    tooltip = fields.Char()
    document_ids = fields.Many2many("documents.document", "document_tag_rel",
                                   "documents_tag_id", "documents_document_id", readonly=True)

    @api.model_create_multi
    def create(self, values):
        raise AccessError(_("Las etiquetas históricas se administran desde la biblioteca."))

    def write(self, values):
        raise AccessError(_("Las etiquetas históricas se administran desde la biblioteca."))

    def unlink(self):
        raise AccessError(_("Las etiquetas históricas se administran desde la biblioteca."))


class Project(models.Model):
    _inherit = "project.project"

    use_documents = fields.Boolean(string="Documents")
    documents_folder_id = fields.Many2one("documents.document", string="Workspace",
                                          domain=[("type", "=", "folder")])
    documents_tag_ids = fields.Many2many("documents.tag", "project_documents_tag_rel",
                                         "project_project_id", "documents_tag_id", string="Tags")
    document_count = fields.Integer(string="Documents", compute="_compute_project_document_count")

    @api.depends("documents_folder_id")
    def _compute_project_document_count(self):
        projects = self._origin.filtered("id")
        projects.check_access("read")
        folders = projects.documents_folder_id
        grouped = self.env["documents.document"].sudo()._read_group(
            [("folder_id", "in", folders.ids), ("type", "!=", "folder")], ["folder_id"], ["__count"])
        counts = dict(grouped)
        for project in self:
            project.document_count = counts.get(project.documents_folder_id, 0)


class Task(models.Model):
    _inherit = "project.task"

    planned_date_begin = fields.Datetime(string="Start Date", copy=False)
    documents_folder_id = fields.Many2one(related="project_id.documents_folder_id")
    project_use_documents = fields.Boolean(related="project_id.use_documents")
    document_count = fields.Integer(string="Documents", compute="_compute_task_document_count")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS | {"document_count", "planned_date_begin", "project_use_documents"}

    def _compute_task_document_count(self):
        tasks = self._origin.filtered("id")
        tasks.check_access("read")
        grouped = self.env["documents.document"].sudo()._read_group(
            [("res_model", "=", self._name), ("res_id", "in", tasks.ids)], ["res_id"], ["__count"])
        counts = dict(grouped)
        for task in self:
            task.document_count = counts.get(task._origin.id, 0)

    def action_view_documents_project_task(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "name": _("Documentos"),
            "type": "ir.actions.act_window",
            "res_model": "documents.document",
            "domain": [("res_model", "=", self._name), ("res_id", "=", self.id)],
            "view_mode": "list,form",
            "views": [(self.env.ref("step_document_library.library_list").id, "list"),
                      (self.env.ref("step_document_library.library_form").id, "form")],
        }

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            expressions = {
                "planning_overlap": "not planning_overlap",
                "dependency_warning": "not dependency_warning",
                "leave_warning": "not leave_warning or not user_ids",
            }
            for name, expression in expressions.items():
                if name not in self._fields:
                    for node in arch.xpath(".//*[@invisible=$expr and .//field[@name=$name]]", expr=expression, name=name):
                        node.getparent().remove(node)
        return arch, view
