from odoo import fields, models


class StepMobilizationDriverDevice(models.Model):
    _inherit = "step.mobilization.driver.device"

    app_device_id = fields.Many2one(
        "step.app.device", string="Dispositivo de la app Steps", copy=False, index=True, ondelete="set null",
        help="Si está definido, este registro representa un teléfono con sesión personal. No tiene token ni código de "
             "emparejamiento, por lo que la API de dispositivos /mobilization/v1 no puede usarlo.")

    _sql_constraints = [("app_device_unique", "unique(app_device_id)", "El dispositivo de la app ya está asociado.")]

    def _for_app(self, app_device, chofer, company):
        """Registro de dispositivo de Movilización para un teléfono con sesión personal (se crea al primer uso)."""
        record = self.sudo().search([("app_device_id", "=", app_device.id)], limit=1)
        if record:
            if record.chofer_id != chofer or record.company_id != company:
                record.write({"chofer_id": chofer.id, "company_id": company.id})
            return record
        return self.sudo().create({
            "chofer_id": chofer.id, "company_id": company.id, "app_device_id": app_device.id,
            "device_uuid": "app-%d" % app_device.id, "state": "active",
        })
