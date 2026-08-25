import base64
import logging
import uuid
from datetime import datetime, timedelta, timezone

import pytz
from psycopg2 import IntegrityError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

#: Cantidad máxima de capturas aceptadas en una sola sincronización por lote.
MAX_BATCH_RECORDS = 100


class StepColacionTotem(models.Model):
    _name = "step.colacion.totem"
    _description = "Tótem de colaciones"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    code = fields.Char(string="ID del tótem", required=True, copy=False, tracking=True, index=True)
    access_token = fields.Char(
        string="Token de acceso",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: str(uuid.uuid4()),
        groups="step_colaciones.group_colaciones_manager",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto de colación",
        required=True,
        tracking=True,
        domain="[('is_meal', '=', True)]",
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        required=True,
        tracking=True,
        domain="[('is_meal_supplier', '=', True)]",
    )
    identification_method = fields.Selection(
        [("barcode", "Código de barras"), ("pin", "NIP"), ("nfc", "NFC")],
        string="Método de identificación",
        required=True,
        default="barcode",
        tracking=True,
    )
    allow_offline = fields.Boolean(string="Permitir modo offline", default=True)
    offline_max_hours = fields.Integer(
        string="Antigüedad offline máxima (horas)",
        default=72,
        help="Los registros capturados sin conexión que superen este tiempo serán rechazados.",
    )
    active = fields.Boolean(default=True, tracking=True)
    last_seen_at = fields.Datetime(string="Última conexión", readonly=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True)
    device_uuid = fields.Char(
        string="Instalación asociada",
        readonly=True,
        copy=False,
        groups="step_colaciones.group_colaciones_manager",
        help="Identificador de instalación informado por el último dispositivo que usó este tótem.",
    )
    device_platform = fields.Char(string="Plataforma del dispositivo", readonly=True, copy=False)
    device_app_version = fields.Char(string="Versión de la App", readonly=True, copy=False)
    registration_count = fields.Integer(compute="_compute_registration_count")
    app_base_url = fields.Char(
        string="URL de la aplicación",
        compute="_compute_app_base_url",
        help="Dirección pública configurada para la App de Colaciones de esta compañía.",
    )
    totem_url = fields.Char(
        string="URL del tótem",
        compute="_compute_totem_url",
        groups="step_colaciones.group_colaciones_manager",
    )
    pairing_qr = fields.Binary(
        string="Código de asociación",
        compute="_compute_pairing_qr",
        groups="step_colaciones.group_colaciones_manager",
    )

    _sql_constraints = [
        ("code_company_unique", "unique(code, company_id)", "El ID del tótem debe ser único por empresa."),
        ("access_token_unique", "unique(access_token)", "El token del tótem debe ser único."),
        ("offline_hours_positive", "check(offline_max_hours >= 1)", "La antigüedad offline debe ser de al menos una hora."),
    ]

    def _compute_registration_count(self):
        grouped = self.env["step.colacion.registration"]._read_group(
            [("totem_id", "in", self.ids)], ["totem_id"], ["__count"]
        ) if self.ids else []
        counts = {totem.id: count for totem, count in grouped}
        for totem in self:
            totem.registration_count = counts.get(totem.id, 0)

    @api.depends("company_id")
    def _compute_app_base_url(self):
        for totem in self:
            totem.app_base_url = totem.company_id.colaciones_app_base_url() if totem.company_id else ""

    @api.depends("company_id", "access_token")
    def _compute_totem_url(self):
        for totem in self:
            base = totem.company_id.colaciones_app_base_url() if totem.company_id else ""
            totem.totem_url = "%s/#token=%s" % (base, totem.access_token) if base and totem.access_token else False

    @api.depends("totem_url")
    def _compute_pairing_qr(self):
        Report = self.env["ir.actions.report"].sudo()
        for totem in self:
            totem.pairing_qr = False
            if not totem.totem_url:
                continue
            try:
                totem.pairing_qr = base64.b64encode(
                    Report.barcode("QR", totem.totem_url, width=320, height=320)
                )
            except Exception:  # pragma: no cover - depende de la librería de códigos
                _logger.debug("No fue posible generar el código QR del tótem %s", totem.id)

    def action_open_totem(self):
        self.ensure_one()
        if not self.totem_url:
            raise UserError(_(
                "Configure la URL de la App de Colaciones en "
                "Colaciones → Configuración → Ajustes."
            ))
        return {"type": "ir.actions.act_url", "url": self.totem_url, "target": "new"}

    def action_view_registrations(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("step_colaciones.action_colacion_registration")
        action["domain"] = [("totem_id", "=", self.id)]
        action["context"] = {"default_totem_id": self.id}
        return action

    def action_regenerate_token(self):
        self.ensure_one()
        self.write({
            "access_token": str(uuid.uuid4()),
            "device_uuid": False,
            "device_platform": False,
            "device_app_version": False,
        })
        self.message_post(body=_(
            "Se regeneró el token de acceso del tótem. El dispositivo anterior quedó revocado."
        ))

    # ------------------------------------------------------------------
    # Dispositivo asociado
    # ------------------------------------------------------------------
    def _touch_device(self, device=None, synced=False):
        """Registra el último contacto del dispositivo sin datos invasivos."""
        self.ensure_one()
        values = {"last_seen_at": fields.Datetime.now()}
        if synced:
            values["last_sync_at"] = fields.Datetime.now()
        if isinstance(device, dict):
            for key, field_name in (
                ("uuid", "device_uuid"),
                ("platform", "device_platform"),
                ("app_version", "device_app_version"),
            ):
                value = device.get(key)
                if isinstance(value, str) and value.strip():
                    values[field_name] = value.strip()[:64]
        self.sudo().write(values)

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------
    def _get_employee(self, identifier):
        self.ensure_one()
        identifier = (identifier or "").strip()
        if not identifier:
            raise ValidationError(_("Ingrese un identificador."))
        field_name = {
            "barcode": "barcode",
            "pin": "pin",
            "nfc": "meal_nfc_uid",
        }[self.identification_method]
        employees = self.env["hr.employee"].sudo().search([
            (field_name, "=", identifier),
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], limit=2)
        if not employees:
            raise ValidationError(_("No se encontró un trabajador activo con esa identificación."))
        if len(employees) > 1:
            raise ValidationError(_("La identificación está asignada a más de un trabajador. Solicite ayuda al administrador."))
        if not employees.meal_eligible:
            raise ValidationError(_("El trabajador no está habilitado para recibir colación."))
        return employees

    def _parse_event_datetime(self, value, offline=False):
        now = datetime.now(timezone.utc)
        if not offline:
            return fields.Datetime.now()
        if not self.allow_offline:
            raise ValidationError(_("Este tótem no permite registros capturados sin conexión."))
        try:
            parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise ValidationError(_("La fecha del registro offline no es válida."))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        parsed = parsed.astimezone(timezone.utc)
        if parsed > now + timedelta(minutes=5):
            raise ValidationError(_("La hora del dispositivo está adelantada. Corríjala antes de registrar."))
        if now - parsed > timedelta(hours=self.offline_max_hours):
            raise ValidationError(_("El registro offline excede la antigüedad permitida por el tótem."))
        return parsed.replace(tzinfo=None)

    def _mask_identifier(self, identifier):
        identifier = (identifier or "").strip()
        visible = 2 if self.identification_method == "pin" else 4
        return "%s%s" % ("•" * max(0, len(identifier) - visible), identifier[-visible:])

    def register_identifier(self, identifier, client_uuid, event_datetime=None, offline=False):
        self.ensure_one()
        if not self.active:
            raise UserError(_("El tótem está deshabilitado."))
        if not client_uuid:
            raise ValidationError(_("Falta el identificador único del registro."))
        Registration = self.env["step.colacion.registration"].sudo()
        existing = Registration.search([("client_uuid", "=", client_uuid)], limit=1)
        if existing:
            return existing._totem_response(duplicate=True)

        employee = self._get_employee(identifier)
        event_dt = self._parse_event_datetime(event_datetime, offline=offline)
        values = {
            "event_datetime": event_dt,
            "received_datetime": fields.Datetime.now(),
            "totem_id": self.id,
            "employee_id": employee.id,
            "employee_name_snapshot": employee.name,
            "identifier_method": self.identification_method,
            "identifier_masked": self._mask_identifier(identifier),
            "product_tmpl_id": self.product_tmpl_id.id,
            "supplier_id": self.supplier_id.id,
            "quantity": 1,
            "source": "totem_offline" if offline else "totem_online",
            "client_uuid": client_uuid,
            "company_id": self.company_id.id,
        }
        try:
            with self.env.cr.savepoint():
                registration = Registration.create(values)
        except IntegrityError:
            registration = Registration.search([
                ("employee_id", "=", employee.id),
                ("product_tmpl_id", "=", self.product_tmpl_id.id),
                ("meal_date", "=", Registration._meal_date_for(event_dt, self.company_id)),
                ("company_id", "=", self.company_id.id),
            ], limit=1)
            if not registration:
                raise
            return registration._totem_response(duplicate=True)
        self.sudo().write({"last_sync_at": fields.Datetime.now(), "last_seen_at": fields.Datetime.now()})
        return registration._totem_response()

    def register_batch(self, records, device=None):
        """Sincroniza varias capturas y responde el estado individual de cada UUID.

        Una captura inválida nunca aborta el lote completo: cada elemento recibe
        ``registered``, ``duplicate``, ``rejected`` (definitivo) o ``retry``
        (temporal, el dispositivo debe conservarlo).
        """
        self.ensure_one()
        if not isinstance(records, list):
            raise ValidationError(_("El lote de sincronización debe ser una lista de capturas."))
        if len(records) > MAX_BATCH_RECORDS:
            raise ValidationError(_(
                "El lote supera el máximo de %s capturas por envío.", MAX_BATCH_RECORDS
            ))
        results = []
        for record in records:
            if not isinstance(record, dict):
                results.append({
                    "client_uuid": False,
                    "status": "rejected",
                    "message": _("Captura con formato inválido."),
                })
                continue
            client_uuid = record.get("client_uuid")
            try:
                with self.env.cr.savepoint():
                    response = self.register_identifier(
                        record.get("identifier"),
                        client_uuid,
                        event_datetime=record.get("event_datetime"),
                        offline=bool(record.get("offline", True)),
                    )
            except (ValidationError, UserError) as exc:
                results.append({
                    "client_uuid": client_uuid,
                    "status": "rejected",
                    "message": str(exc),
                })
                continue
            except Exception:  # pragma: no cover - fallo inesperado del servidor
                _logger.exception("Error sincronizando la captura %s del tótem %s", client_uuid, self.id)
                results.append({
                    "client_uuid": client_uuid,
                    "status": "retry",
                    "message": _("El servidor no pudo procesar la captura. Se reintentará."),
                })
                continue
            results.append({
                "client_uuid": client_uuid,
                "status": "duplicate" if response.get("duplicate") else "registered",
                "message": response.get("message"),
                "registration": response.get("registration"),
                "employee": response.get("employee"),
            })
        self._touch_device(device=device, synced=True)
        return results

    def totem_configuration(self):
        """Configuración operativa que necesita la aplicación del tótem."""
        self.ensure_one()
        return {
            "ok": True,
            "api_version": 2,
            "server_time": fields.Datetime.now().replace(microsecond=0).isoformat() + "Z",
            "name": self.name,
            "code": self.code,
            "product": self.product_tmpl_id.display_name,
            "supplier": self.supplier_id.display_name,
            "identification_method": self.identification_method,
            "allow_offline": self.allow_offline,
            "offline_max_hours": self.offline_max_hours,
            "max_batch_records": MAX_BATCH_RECORDS,
        }


class StepColacionTotemTimezoneMixin(models.AbstractModel):
    _name = "step.colacion.timezone.mixin"
    _description = "Utilidades de zona horaria para colaciones"

    @api.model
    def company_timezone(self, company):
        timezone_name = company.resource_calendar_id.tz or company.partner_id.tz or "UTC"
        try:
            return pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            return pytz.UTC
