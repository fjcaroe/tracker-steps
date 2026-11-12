from uuid import UUID

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class NurseryEvent(models.Model):
    _inherit = "step.nursery.event"

    offline_key = fields.Char(string="Identificador offline", readonly=True, copy=False, index=True)
    _sql_constraints = [
        ("offline_event_key", "UNIQUE(company_id, operator_id, offline_key)",
         "Esta captura offline ya se sincronizó."),
    ]

    @api.model
    def _ingest_offline_event(self, payload):
        self.check_access("create")
        if not isinstance(payload, dict):
            raise ValidationError(_("Formato de captura no válido."))
        try:
            raw_key = payload["id"]
            event_key = str(UUID(raw_key, version=4))
            order_id = payload["order_id"]
            performed = fields.Datetime.to_datetime(payload["performed_at"])
            kind = payload["kind"]
            sample, germinated = payload.get("sample", 0), payload.get("germinated", 0)
            note = payload.get("note", "")
            if (event_key != raw_key or type(order_id) is not int or not performed
                    or type(sample) is not int or type(germinated) is not int
                    or not 0 <= germinated <= sample <= 1000000
                    or not isinstance(note, str) or len(note) > 1000
                    or kind not in ("germination", "watering", "observation")
                    or (kind != "germination" and (sample or germinated or not note.strip()))):
                raise ValueError
        except (KeyError, AttributeError, ValueError, TypeError, OverflowError) as error:
            raise ValidationError(_("Revise fecha, tipo, muestra y observación de la captura.")) from error
        order = self.env["mrp.production"].search([
            ("id", "=", order_id), ("company_id", "=", self.env.company.id),
            ("step_nursery_plan_ids", "!=", False), ("state", "!=", "cancel"),
        ], limit=1)
        if not order:
            raise ValidationError(_("La orden de vivero no está disponible en esta empresa."))
        values = {
            "production_id": order.id, "operator_id": self.env.uid, "offline_key": event_key,
            "performed_at": performed, "kind": kind, "note": note or False,
            "sample_count": sample, "germinated_count": germinated,
        }
        prior = self.search([
            ("company_id", "=", self.env.company.id), ("operator_id", "=", self.env.uid),
            ("offline_key", "=", event_key),
        ], limit=1)
        if prior:
            if (prior.production_id != order or prior.performed_at != performed or prior.kind != kind
                    or prior.sample_count != sample or prior.germinated_count != germinated
                    or (prior.note or "") != note):
                raise ValidationError(_("El identificador offline ya corresponde a otra captura."))
            return prior
        return self.create(values)
