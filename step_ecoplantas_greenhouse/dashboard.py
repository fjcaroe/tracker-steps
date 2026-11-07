from odoo import _, api, models
from odoo.exceptions import AccessError

from .hooks import DEMO


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def get_steps_greenhouse_dashboard(self):
        if not self.env.user.has_group("base.group_user"):
            raise AccessError(_("El panel requiere un usuario interno."))

        def visible(key):
            record = self.env.ref(f"{DEMO}.{key}", raise_if_not_found=False)
            if not record or not record.exists():
                return None
            try:
                record.check_access("read")
                if record.company_id == self.env.company:
                    return record
            except AccessError:
                pass
            return None

        def form(record, state_field=None):
            if not record:
                return None
            status = None
            if state_field:
                status = dict(record._fields[state_field]._description_selection(self.env)).get(record[state_field])
            return {
                "id": record.id, "model": record._name,
                "name": record.display_name, "status": status,
            }

        batch = visible("batch")
        receipt = visible("receipt")
        point = visible("inspection")
        dispatch = visible("dispatch")
        project = visible("project")
        maintenance = visible("pump_check")
        plant = visible("plant")
        checks = self.env["quality.check"]
        if batch and point and checks.has_access("read"):
            checks = checks.search([("production_id", "=", batch.id), ("point_id", "=", point.id)])
        tasks = self.env["project.task"]
        return {
            "planned": batch.product_qty if batch else None,
            "operations": len(batch.bom_id.operation_ids) if batch else None,
            "tasks": tasks.search_count([
                ("project_id", "=", project.id), ("state", "not in", ["1_done", "1_canceled"]),
            ]) if project and tasks.has_access("read") else None,
            "receipt": form(receipt, "state"),
            "batch": form(batch, "state"),
            "inspection": form(checks[:1], "quality_state") if checks else form(point),
            "dispatch": form(dispatch, "state"),
            "project": form(project),
            "maintenance": form(maintenance),
            "plant": form(plant),
        }
