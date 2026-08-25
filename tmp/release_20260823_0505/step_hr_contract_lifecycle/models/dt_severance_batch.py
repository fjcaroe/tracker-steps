# -*- coding: utf-8 -*-
import base64
import csv
import hashlib
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError

MAX_ROWS_PER_FILE = 100

SEVERANCE_COLUMNS = [
    "RutEmpresa", "RutTrabajador", "FechaInicioContrato", "FechaTerminoContrato",
    "DeclaraNotificacionRetencionAlimento", "CausalFiniquitoId", "Funciones",
    "RegionTrabajoId", "ComunaId", "LugarPrestacionServiciosDireccion",
    "CantidadDiasVacaciones", "IndemnizacionFeriado", "IndemnizacionAvisoPrevio",
    "IndemnizacionServicio", "IndemnizacionOtras", "IndemnizacionArticulo163",
    "remuneracionPendiente", "Gratificaciones", "Bonos", "HorasExtraordinarias",
    "Aguinaldo", "SemanaCorrida", "ComisionOParticipacion", "Movilizacion",
    "Colacion", "PerdidaCaja", "DesgasteHerramientas", "Viaticos",
    "AsignacionesFamiliares", "DescuentoSeguridadSocial", "DescuentoImpuestos",
    "DescuentoAfc", "DescuentoAnticipado", "DescuentoIndemnizacion",
    "DescuentoPension", "DescuentoCajaCompensacion", "PrestamoAdeudado",
    "AnticipoSueldo", "VacacionesAnticipadas", "Email", "CodigoComunaPersonal",
    "CallePersonal", "NumeroPersonal", "DepartamentoBlockPersonal", "Telefono",
    "CuentaTransferencia", "BancoId", "TipoCuentaId",
]


def _rut_num(vat_or_id):
    if not vat_or_id:
        return ""
    clean = vat_or_id.replace(".", "").strip()
    return clean.split("-")[0] if "-" in clean else clean


def build_severance_row(severance):
    contract = severance.contract_id
    employee = contract.employee_id
    return {
        "RutEmpresa": _rut_num(severance.company_id.vat),
        "RutTrabajador": _rut_num(employee.identification_id),
        "FechaInicioContrato": contract.date_start.strftime("%d-%m-%Y") if contract.date_start else "",
        "FechaTerminoContrato": severance.date_termino.strftime("%d-%m-%Y") if severance.date_termino else "",
        "DeclaraNotificacionRetencionAlimento": "1" if severance.retencion_alimentos else "0",
        "CausalFiniquitoId": str(severance.causal_id.dt_codigo_causal or ""),
        "Funciones": contract.job_id.name or "",
        "RegionTrabajoId": contract.work_region_id.id and str(contract.work_region_id.id) or "",
        "ComunaId": contract.work_commune_id.code or "",
        "LugarPrestacionServiciosDireccion": " ".join(
            filter(None, [contract.work_street, contract.work_number])
        ),
        "CantidadDiasVacaciones": "%.2f" % (severance.feriado_dias_finales or 0),
        "IndemnizacionFeriado": "%d" % (severance.feriado_amount or 0),
        "IndemnizacionAvisoPrevio": "%d" % (severance.mes_aviso_amount or 0),
        "IndemnizacionServicio": "%d" % (severance.ias_anual_amount or 0),
        "IndemnizacionOtras": "%d" % (severance.ias_mensual_amount or 0),
        "IndemnizacionArticulo163": "0",
        "remuneracionPendiente": "%d" % (severance.remuneracion_pendiente or 0),
        "Gratificaciones": "%d" % (severance.gratificacion or 0),
        "Bonos": "%d" % (severance.bonos or 0),
        "HorasExtraordinarias": "%d" % (severance.horas_extraordinarias or 0),
        "Aguinaldo": "%d" % (severance.aguinaldo or 0),
        "SemanaCorrida": "%d" % (severance.semana_corrida or 0),
        "ComisionOParticipacion": "%d" % (severance.comision or 0),
        "Movilizacion": "%d" % (severance.movilizacion or 0),
        "Colacion": "%d" % (severance.colacion or 0),
        "PerdidaCaja": "%d" % (severance.perdida_caja or 0),
        "DesgasteHerramientas": "%d" % (severance.desgaste_herramientas or 0),
        "Viaticos": "%d" % (severance.viaticos or 0),
        "AsignacionesFamiliares": "%d" % (severance.asignaciones_familiares or 0),
        "DescuentoSeguridadSocial": "%d" % (severance.descuento_seguridad_social or 0),
        "DescuentoImpuestos": "%d" % (severance.descuento_impuestos or 0),
        "DescuentoAfc": "%d" % (severance.descuento_afc or 0),
        "DescuentoAnticipado": "%d" % (severance.descuento_anticipos or 0),
        "DescuentoIndemnizacion": "%d" % (severance.descuento_indemnizacion_anticipada or 0),
        "DescuentoPension": "%d" % (severance.descuento_pension_alimenticia or 0),
        "DescuentoCajaCompensacion": "%d" % (severance.descuento_caja_compensacion or 0),
        "PrestamoAdeudado": "%d" % (severance.descuento_prestamos or 0),
        "AnticipoSueldo": "%d" % (severance.descuento_anticipo_sueldo or 0),
        "VacacionesAnticipadas": "%d" % (severance.descuento_vacaciones_anticipadas or 0),
        "Email": employee.work_email or employee.private_email or "",
        "CodigoComunaPersonal": "",
        "CallePersonal": employee.private_street or "",
        "NumeroPersonal": "",
        "DepartamentoBlockPersonal": "",
        "Telefono": employee.mobile_phone or "",
        "CuentaTransferencia": (employee.bank_account_id.acc_number or "").replace(" ", "").replace("-", ""),
        "BancoId": employee.bank_account_id.bank_id.name or "",
        "TipoCuentaId": "",
    }


REQUIRED_SEVERANCE_FIELDS = [
    "RutEmpresa", "RutTrabajador", "FechaInicioContrato", "FechaTerminoContrato",
    "CausalFiniquitoId", "Funciones",
]


def validate_severance_row(severance):
    row = build_severance_row(severance)
    return [f for f in REQUIRED_SEVERANCE_FIELDS if not row.get(f)]


class HrSeveranceDtBatch(models.Model):
    _name = "hr.severance.dt.batch"
    _description = "Lote DT — carga masiva de finiquitos electrónicos"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    severance_ids = fields.Many2many("hr.severance", string="Finiquitos incluidos")
    severance_count = fields.Integer(compute="_compute_count")
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

    @api.depends("severance_ids")
    def _compute_count(self):
        for batch in self:
            batch.severance_count = len(batch.severance_ids)

    @api.constrains("severance_ids", "company_id")
    def _check_max_rows_and_company(self):
        for batch in self:
            if len(batch.severance_ids) > MAX_ROWS_PER_FILE:
                raise UserError(
                    _("Un lote no puede tener más de %s finiquitos.") % MAX_ROWS_PER_FILE
                )
            companies = batch.severance_ids.mapped("company_id")
            if len(companies) > 1:
                raise UserError(_("Un lote no puede mezclar compañías."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "hr.severance.dt.batch"
                ) or _("Nuevo")
        return super().create(vals_list)

    def action_validate(self):
        for batch in self:
            if not batch.severance_ids:
                raise UserError(_("El lote no tiene finiquitos."))
            errors = []
            for sev in batch.severance_ids:
                missing = validate_severance_row(sev)
                if missing:
                    errors.append("%s: faltan %s" % (sev.employee_id.name, ", ".join(missing)))
            batch.error_report = "\n".join(errors)
            batch.state = "draft" if errors else "validated"
            if errors:
                raise UserError(
                    _("Hay %(n)s finiquitos con datos faltantes:\n%(detail)s")
                    % {"n": len(errors), "detail": batch.error_report}
                )

    def action_generate_csv(self):
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Valide el lote antes de generar el CSV."))
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=",", lineterminator="\r\n")
        writer.writerow(SEVERANCE_COLUMNS)
        for sev in self.severance_ids:
            row = build_severance_row(sev)
            writer.writerow([row[col] for col in SEVERANCE_COLUMNS])
        content = buffer.getvalue().encode("utf-8")
        filename = "finiquitos_%s.csv" % fields.Date.context_today(self).strftime("%Y%m%d_%H%M%S")
        attachment = self.env["ir.attachment"].create(
            {
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(content),
                "res_model": "hr.severance.dt.batch",
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

    def action_record_result(self):
        for batch in self:
            if batch.dt_result == "pending":
                raise UserError(_("Indique si el lote fue aceptado u observado."))
            batch.state = "result_recorded"

    @api.model
    def create_batches_from_severances(self, severances):
        """Divide automáticamente en archivos de hasta 100 filas, sin
        mezclar compañías."""
        batches = self.browse()
        by_company = {}
        for sev in severances:
            by_company.setdefault(sev.company_id, self.env["hr.severance"].browse())
            by_company[sev.company_id] |= sev
        for company, sevs in by_company.items():
            sevs = list(sevs)
            for i in range(0, len(sevs), MAX_ROWS_PER_FILE):
                chunk = sevs[i:i + MAX_ROWS_PER_FILE]
                batch = self.create(
                    {
                        "company_id": company.id,
                        "severance_ids": [(6, 0, [s.id for s in chunk])],
                    }
                )
                batches |= batch
        return batches
