from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from .hooks import DEMO


class Http(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        batch = self.env.ref(f"{DEMO}.batch", raise_if_not_found=False)
        if batch and self.env.user.has_group("step_ecoplantas_greenhouse.group_greenhouse"):
            company = batch.sudo().company_id
            if company in self.env.user.company_ids:
                result["steps_greenhouse_company"] = company.id
        return result


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def get_steps_greenhouse_dashboard(self):
        if not self.env.user.has_group("step_ecoplantas_greenhouse.group_greenhouse"):
            raise AccessError(_("El panel requiere acceso a Invernadero."))
        batch_ref = self.env.ref(f"{DEMO}.batch", raise_if_not_found=False)
        if not batch_ref or batch_ref.sudo().company_id != self.env.company:
            raise UserError(_("Seleccione EcoPlantas como empresa activa para abrir Invernadero."))

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
        maintenance = visible("pump_check")
        plant = visible("plant") if self.env["stock.lot"].has_access("read") else None
        tasks = self.env["project.task"]
        project = visible("project") if tasks.has_access("read") else None
        bom = batch.bom_id if batch else None
        checks = self.env["quality.check"]
        if batch and point and checks.has_access("read"):
            checks = checks.search([("production_id", "=", batch.id), ("point_id", "=", point.id)])
        open_tasks = tasks.search_count([
            ("project_id", "=", project.id), ("state", "not in", ["1_done", "1_canceled"]),
        ]) if project else None
        operations = len(bom.operation_ids) if bom and bom.has_access("read") else None
        metrics = {}

        def metric(section, label, value):
            metrics.setdefault(section, []).append({"label": label, "value": value})

        if receipt and receipt.move_ids.has_access("read"):
            metric("receipt", _("insumos"), len(receipt.move_ids))
        if batch:
            metric("batch", _("plantines planificados"), batch.product_qty)
        if operations is not None:
            metric("batch", _("operaciones"), operations)
        if point and checks.has_access("read"):
            metric("inspection", _("controles pendientes"), len(checks.filtered(lambda check: check.quality_state == "none")))
            metric("inspection", _("aprobados"), len(checks.filtered(lambda check: check.quality_state == "pass")))
        if plant:
            metric("lots", _("lotes registrados"), self.env["stock.lot"].search_count([
                ("product_id", "=", plant.id), ("company_id", "=", self.env.company.id),
            ]))
        if plant and dispatch and self.env["stock.quant"].has_access("read"):
            available = round(self.env["stock.quant"]._get_available_quantity(plant, dispatch.location_id), 4)
            metric("dispatch", _("plantines disponibles"), available)
        if project:
            metric("project", _("labores abiertas"), open_tasks)
        if maintenance:
            metric("maintenance", _("etapa"), maintenance.stage_id.name)
        return {
            "planned": batch.product_qty if batch else None,
            "operations": operations,
            "tasks": open_tasks,
            "subpage_metrics": metrics,
            "receipt": form(receipt, "state"),
            "batch": form(batch, "state"),
            "inspection": form(checks[:1], "quality_state") if checks else form(point),
            "dispatch": form(dispatch, "state"),
            "project": form(project),
            "maintenance": form(maintenance),
            "plant": form(plant),
        }
