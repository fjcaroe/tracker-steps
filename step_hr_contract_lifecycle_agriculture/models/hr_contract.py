# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    """Mapea el motor agrícola Steps (step_hr / l10n_cl_hr) hacia la
    interfaz de adaptación que define el núcleo. Ningún cálculo legal,
    flujo de aprobación, documento o CSV vive aquí: sólo el mapeo de
    datos."""

    _inherit = "hr.contract"

    fundo_id = fields.Many2one("step.fundo", string="Fundo / predio", tracking=True)

    @api.onchange("fundo_id")
    def _onchange_fundo_id_sync_work_location(self):
        for contract in self:
            contract.work_location_id = contract._agriculture_sync_work_location()

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts:
            if contract.fundo_id and not contract.work_location_id:
                contract.work_location_id = contract._agriculture_sync_work_location()
        return contracts

    def write(self, vals):
        res = super().write(vals)
        if "fundo_id" in vals:
            for contract in self:
                contract.work_location_id = contract._agriculture_sync_work_location()
        return res

    def _agriculture_sync_work_location(self):
        """Busca o crea la ubicación neutral (hr.work.location)
        correspondiente al fundo elegido, sin duplicar si ya existe una
        con el mismo nombre para la misma compañía."""
        self.ensure_one()
        if not self.fundo_id:
            return self.work_location_id
        WorkLocation = self.env["hr.work.location"]
        location = WorkLocation.search(
            [
                ("name", "=", self.fundo_id.name),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if not location:
            location = WorkLocation.create(
                {"name": self.fundo_id.name, "company_id": self.company_id.id}
            )
        return location

    # -- Interfaz de adaptación (sobreescribe al núcleo) -------------------------
    def _steps_contract_payload(self):
        self.ensure_one()
        payload = super()._steps_contract_payload()
        payload.update(
            {
                "tipo_jornada_code": self.tipo_de_jornada or "",
            }
        )
        return payload

    def _steps_pension_payload(self):
        self.ensure_one()
        return {
            "afp_name": self.afp_id.name or "",
            "health_name": self.isapre_id.name or "",
            "health_type": "isapre" if self.isapre_id else "fonasa",
        }

    def _steps_termination_payload(self):
        self.ensure_one()
        Cause = self.env["step.hr.termination.cause"]
        legacy_causal = getattr(self, "causal_id", False)
        if not legacy_causal:
            return super()._steps_termination_payload()
        mapped = Cause.search(
            [
                ("origin_model", "=", "hr.causal.termino"),
                ("origin_id", "=", legacy_causal.id),
            ],
            limit=1,
        )
        return {"termination_cause_id": mapped}
