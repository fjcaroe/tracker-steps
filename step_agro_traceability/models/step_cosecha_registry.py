# -*- coding: utf-8 -*-
"""Estado fitosanitario del registro de cosecha.

Aporta la respuesta que el sistema hoy no puede dar: *¿puedo cosechar este
cuartel en esta fecha?*  La lectura del formulario usa la tabla materializada
—rápida y con permisos propios— mientras que la aprobación refresca en vivo el
cuartel involucrado antes de decidir, para que un dato recién cargado en BPA no
pase inadvertido.
"""

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StepCosechaRegistry(models.Model):
    _inherit = "step.cosecha.registry"

    step_phyto_status = fields.Selection(
        selection=[
            ("unknown", "Sin cuartel"),
            ("clear", "Liberado"),
            ("carencia", "En carencia"),
        ],
        string="Estado fitosanitario",
        compute="_compute_step_phyto",
    )
    step_phyto_allowed_from = fields.Datetime(
        string="Cosecha permitida desde", compute="_compute_step_phyto",
    )
    step_phyto_message = fields.Char(
        string="Detalle fitosanitario", compute="_compute_step_phyto",
    )
    step_phyto_restriction_ids = fields.Many2many(
        "step.phyto.restriction", string="Restricciones vigentes",
        compute="_compute_step_phyto",
    )
    step_phyto_reentry_active = fields.Boolean(
        string="Reingreso vigente", compute="_compute_step_phyto",
        help="El cuartel todavía no cumple el período de reingreso sin EPP.",
    )

    @api.depends("cuartel_id", "date")
    def _compute_step_phyto(self):
        restriction_model = self.env["step.phyto.restriction"]
        # Una sola consulta para todos los cuarteles del lote: la lista de
        # cosechas pinta este estado en cada fila.
        cache = restriction_model.evaluate_many(self.mapped("cuartel_id"))
        for record in self:
            result = restriction_model.evaluate_from_cache(
                record.cuartel_id, record.date, cache,
            )
            record.step_phyto_status = result["status"]
            record.step_phyto_allowed_from = result["allowed_from"]
            record.step_phyto_restriction_ids = result["restrictions"]
            record.step_phyto_reentry_active = bool(result["reentry"])
            record.step_phyto_message = record._step_phyto_message(result)

    def _step_phyto_message(self, result):
        """Texto corto y accionable para el banner del formulario."""
        self.ensure_one()
        if result["status"] == "unknown":
            return _("Indique el cuartel para verificar carencia y reingreso.")
        if result["status"] == "clear":
            if result["reentry"]:
                return _(
                    "Sin carencia vigente, pero el cuartel aún está en período de "
                    "reingreso: el personal requiere EPP."
                )
            return _("Cuartel liberado: sin carencia ni reingreso vigentes.")
        restrictions = result["restrictions"]
        products = ", ".join(sorted(set(restrictions.mapped("product_ids.name"))))
        return _(
            "Cuartel en carencia hasta el %(fecha)s por %(cantidad)s aplicación(es): %(productos)s",
            fecha=fields.Date.to_string(fields.Datetime.to_datetime(result["allowed_from"]).date()),
            cantidad=len(restrictions),
            productos=products or _("productos sin detalle"),
        )

    def action_open_phyto_restrictions(self):
        """Permite bajar del indicador a los registros que lo explican."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Restricciones del cuartel %s", self.cuartel_id.name or ""),
            "res_model": "step.phyto.restriction",
            "view_mode": "list,form",
            "domain": [("cuartel_id", "=", self.cuartel_id.id)],
            "context": {"search_default_group_cuartel": 1},
        }

    def action_apro(self):
        """Verifica carencia antes de dejar que la cosecha avance."""
        self._step_phyto_guard()
        return super().action_apro()

    def _step_phyto_guard(self):
        restriction_model = self.env["step.phyto.restriction"]
        for record in self:
            policy = record.company_id.step_phyto_policy or "warn"
            if policy == "off" or not record.cuartel_id:
                continue
            # Refresco en vivo del cuartel: una aplicación cargada hace un
            # minuto en BPA debe pesar en esta decisión.
            result = restriction_model.evaluate(
                record.cuartel_id, record.date, refresh=True,
            )
            if result["status"] != "carencia":
                if result["reentry"]:
                    record.message_post(body=Markup("<b>%s</b> %s") % (
                        _("Reingreso vigente."),
                        _(
                            "El cuartel %(cuartel)s fue tratado recientemente; el "
                            "personal debe ingresar con EPP hasta el %(hasta)s.",
                            cuartel=record.cuartel_id.name,
                            hasta=max(result["reentry"].mapped("reentry_allowed_from")),
                        ),
                    ))
                continue

            detail = record._step_phyto_message(result)
            if policy == "block":
                raise UserError(_(
                    "%(detalle)s\n\n"
                    "No es posible aprobar la cosecha de %(registro)s dentro del "
                    "período de carencia. Corrija la fecha de cosecha o revise las "
                    "aplicaciones del cuartel.",
                    detalle=detail,
                    registro=record.display_name,
                ))
            record.message_post(body=Markup("<b>%s</b> %s") % (
                _("Alerta de carencia."), detail,
            ))
