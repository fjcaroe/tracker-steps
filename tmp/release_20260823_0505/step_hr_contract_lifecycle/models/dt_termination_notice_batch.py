# -*- coding: utf-8 -*-
import base64
import csv
import hashlib
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError


def _rut_dv(identification_id):
    if not identification_id:
        return "", ""
    clean = identification_id.replace(".", "").strip()
    if "-" in clean:
        num, dv = clean.rsplit("-", 1)
        return num.strip(), dv.strip()
    return clean, ""


NOTICE_COLUMNS = [
    "rut_tr", "dv_tr", "nombres_tr", "ap_paterno_tr", "ap_materno_tr",
    "comuna_tr", "sexo", "fecha_notificacion", "medio_notificacion",
    "oficina_correos", "fecha_inicio", "fecha_termino",
    "monto_anio_servicio", "monto_aviso_previo", "CodigoTipoCausal",
    "ArticuloCausal", "HechosCausal", "EstadoCotizaciones",
    "TipoDocCotizaciones",
]


def build_notice_row(notice):
    contract = notice.contract_id
    employee = contract.employee_id
    rut, dv = _rut_dv(employee.identification_id)
    name_parts = (employee.name or "").split(" ")
    nombres = name_parts[0] if name_parts else ""
    apellidos = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    return {
        "rut_tr": rut,
        "dv_tr": dv,
        "nombres_tr": nombres,
        "ap_paterno_tr": apellidos.split(" ")[0] if apellidos else "",
        "ap_materno_tr": " ".join(apellidos.split(" ")[1:]) if apellidos else "",
        "comuna_tr": contract.work_commune_id.code or "",
        "sexo": {"male": "M", "female": "F"}.get(employee.gender, ""),
        "fecha_notificacion": notice.date_notificacion.strftime("%d/%m/%Y") if notice.date_notificacion else "",
        "medio_notificacion": {"personal": "P", "correo": "C"}.get(notice.medio_notificacion, ""),
        "oficina_correos": notice.oficina_correos or "",
        "fecha_inicio": contract.date_start.strftime("%d/%m/%Y") if contract.date_start else "",
        "fecha_termino": notice.date_termino.strftime("%d/%m/%Y") if notice.date_termino else "",
        "monto_anio_servicio": "%d" % (notice.monto_anio_servicio or 0),
        "monto_aviso_previo": "%d" % (notice.monto_aviso_previo or 0),
        "CodigoTipoCausal": str(notice.causal_id.dt_codigo_causal or ""),
        "ArticuloCausal": notice.causal_id.articulo or "",
        "HechosCausal": (notice.hechos_causal or "")[:200],
        "EstadoCotizaciones": (notice.estado_cotizaciones or "")[:200],
        "TipoDocCotizaciones": notice.tipo_doc_cotizaciones or "",
    }


REQUIRED_NOTICE_FIELDS = [
    "rut_tr", "dv_tr", "nombres_tr", "ap_paterno_tr", "comuna_tr", "sexo",
    "fecha_notificacion", "medio_notificacion", "fecha_inicio",
    "fecha_termino", "CodigoTipoCausal", "ArticuloCausal", "HechosCausal",
    "EstadoCotizaciones", "TipoDocCotizaciones",
]


def validate_notice_row(notice):
    row = build_notice_row(notice)
    missing = [f for f in REQUIRED_NOTICE_FIELDS if not row.get(f)]
    if notice.medio_notificacion == "correo" and not notice.oficina_correos:
        missing.append("oficina_correos")
    return missing


class HrTerminationNoticeDtBatch(models.Model):
    _name = "hr.termination.notice.dt.batch"
    _description = "Lote DT — carga masiva de avisos de término"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    notice_ids = fields.Many2many("hr.termination.notice", string="Avisos incluidos")
    notice_count = fields.Integer(compute="_compute_notice_count")
    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("validated", "Validado"),
            ("generated", "Archivo generado"),
            ("submitted", "Presentado"),
            ("result_recorded", "Resultado registrado"),
        ],
        default="draft",
        tracking=True,
    )
    csv_attachment_id = fields.Many2one("ir.attachment", readonly=True)
    csv_hash = fields.Char(readonly=True)
    error_report = fields.Text(readonly=True)
    dt_result = fields.Selection(
        [("pending", "Pendiente"), ("accepted", "Aceptado"), ("observed", "Observado / rechazado")],
        default="pending",
        tracking=True,
    )
    dt_result_notes = fields.Text()

    @api.depends("notice_ids")
    def _compute_notice_count(self):
        for batch in self:
            batch.notice_count = len(batch.notice_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hr.termination.notice.dt.batch"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_validate(self):
        for batch in self:
            if not batch.notice_ids:
                raise UserError(_("El lote no tiene avisos."))
            errors = []
            for notice in batch.notice_ids:
                missing = validate_notice_row(notice)
                if missing:
                    errors.append(
                        "%s: faltan %s" % (notice.employee_id.name, ", ".join(missing))
                    )
            batch.error_report = "\n".join(errors)
            batch.state = "draft" if errors else "validated"
            if errors:
                raise UserError(
                    _("Hay %(n)s avisos con datos faltantes:\n%(detail)s")
                    % {"n": len(errors), "detail": batch.error_report}
                )

    def action_generate_csv(self):
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Valide el lote antes de generar el CSV."))
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=",", lineterminator="\r\n")
        writer.writerow(NOTICE_COLUMNS)
        for notice in self.notice_ids:
            row = build_notice_row(notice)
            writer.writerow([row[col] for col in NOTICE_COLUMNS])
        content = buffer.getvalue().encode("utf-8")
        filename = "avisos_%s.csv" % fields.Date.context_today(self).strftime("%Y%m%d")
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(content),
                "res_model": "hr.termination.notice.dt.batch",
                "res_id": self.id,
                "mimetype": "text/csv",
            }
        )
        self.write(
            {
                "csv_attachment_id": attachment.id,
                "csv_hash": hashlib.sha256(content).hexdigest(),
                "state": "generated",
            }
        )
        for notice in self.notice_ids:
            notice.registration_state = "file_generated"

    def action_record_result(self):
        for batch in self:
            if batch.dt_result == "pending":
                raise UserError(_("Indique si el lote fue aceptado u observado."))
            batch.state = "result_recorded"
            new_state = "accepted" if batch.dt_result == "accepted" else "observed_rejected"
            batch.notice_ids.write({"registration_state": new_state})
