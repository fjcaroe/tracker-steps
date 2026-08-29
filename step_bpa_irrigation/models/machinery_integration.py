from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.step_machinery.models.step_hrs_machinery import StepHrsMachinery

#: Campo Studio histórico que guardaba el folio BPA como texto libre. No se
#: declara como dependencia: puede no existir en una instalación limpia.
LEGACY_FOLIO_FIELD = "x_studio_folio_bpa"

#: Campos de la OT-BPA que alimentan el nombre compuesto de Horas Máquina.
#: Ambos están definidos en Python por este módulo (`bpa_native.py`), así que
#: siempre existen.
BPA_LABEL_FIELDS = ("x_studio_nmero_ot_bpa", "x_name")

#: Marca de contexto para no reentrar en la sincronización de nombres.
SYNC_CONTEXT_KEY = "skip_machinery_name_sync"


class StepHrsMachineryBpa(models.Model):
    _inherit = "step.hrs.machinery"

    # El folio BPA también debe poder buscarse desde el buscador general.
    _rec_names_search = list(StepHrsMachinery._rec_names_search) + ["bpa_folio"]

    bpa_order_id = fields.Many2one(
        "x_aplicacion_foliar", string="Folio BPA", check_company=True, tracking=True,
        help="OT-BPA de aplicación foliar que originó el uso de maquinaria. "
             "Es un dato distinto de la Orden de Trabajo de la labor.",
    )
    bpa_folio = fields.Char(
        string="Folio BPA (texto)", compute="_compute_bpa_folio", store=True,
        help="Número de la OT-BPA vinculada, usado para componer el nombre del registro.",
    )

    @api.depends("bpa_order_id", "bpa_order_id.x_studio_nmero_ot_bpa", "bpa_order_id.x_name")
    def _compute_bpa_folio(self):
        for record in self:
            record.bpa_folio = record._bpa_folio_label()

    def _bpa_folio_label(self):
        """Número visible de la OT-BPA, con respaldo en el campo Studio histórico."""
        self.ensure_one()
        order = self.bpa_order_id
        if order:
            label = (order.x_studio_nmero_ot_bpa or "").strip() or (order.x_name or "").strip()
            if label:
                return label
        if LEGACY_FOLIO_FIELD in self._fields:
            return (self[LEGACY_FOLIO_FIELD] or "").strip()
        return ""

    @api.model
    def _name_trigger_fields(self):
        return super()._name_trigger_fields() | {"bpa_order_id"}

    def _name_segments(self):
        """Agrega el segmento ``OT_BPA {folio}`` al nombre compuesto."""
        segments = super()._name_segments()
        label = self._bpa_folio_label()
        if label:
            segments.append("OT_BPA %s" % label)
        return segments

    @api.onchange("bpa_order_id")
    def _onchange_bpa_order_id(self):
        """La OT-BPA aporta fundo y empresa; la Orden de Trabajo se mantiene independiente."""
        for record in self:
            order = record.bpa_order_id
            if order:
                record.fundo_id = order.x_studio_fundo
                record.company_id = order.company_id

    @api.constrains("bpa_order_id", "company_id")
    def _check_bpa_order(self):
        for record in self.filtered("bpa_order_id"):
            if record.bpa_order_id.company_id != record.company_id:
                raise ValidationError(_("La OT-BPA debe pertenecer a la misma empresa."))
            if record.bpa_order_id.state != "status1":
                raise ValidationError(_("Sólo puede vincular una OT-BPA en estado Ingresado."))


class BpaFoliarApplicationNaming(models.Model):
    """Propaga a Horas Máquina los cambios de folio de la OT-BPA."""

    _inherit = "x_aplicacion_foliar"

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get(SYNC_CONTEXT_KEY):
            return result
        if not any(field in vals for field in BPA_LABEL_FIELDS):
            return result
        self._sync_machinery_names()
        return result

    def _sync_machinery_names(self):
        """Recompone el nombre de las Horas Máquina aún editables.

        Funciona para escrituras masivas (una sola búsqueda para todo el
        recordset) y respeta la congelación histórica: los registros costeados
        o contabilizados conservan su nombre.
        """
        if not self:
            return False
        usages = self.env["step.hrs.machinery"].sudo().search([
            ("bpa_order_id", "in", self.ids),
            ("state", "not in", ("costed", "accounted")),
            ("invoice_id", "=", False),
        ])
        if not usages:
            return False
        # `bpa_folio` es un calculado almacenado: hay que bajarlo a base antes
        # de recomponer para que la lista y el nombre queden coherentes.
        usages.flush_recordset(["bpa_folio"])
        usages.with_context(**{SYNC_CONTEXT_KEY: True})._sync_composed_name()
        return True
