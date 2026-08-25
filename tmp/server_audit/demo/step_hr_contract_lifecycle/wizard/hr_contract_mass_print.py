# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class HrContractMassPrint(models.TransientModel):
    """Selección masiva de contratos a imprimir. Genera el PDF de cada
    contrato usando su plantilla laboral y deja copia en el historial del
    trabajador (chatter de hr.contract y hr.employee)."""

    _name = "hr.contract.mass.print"
    _description = "Impresión masiva de contratos"

    contract_ids = fields.Many2many("hr.contract", string="Contratos")
    generated_document_ids = fields.Many2many(
        "hr.labor.document", string="Documentos generados", readonly=True
    )

    def action_print(self):
        self.ensure_one()
        Document = self.env["hr.labor.document"]
        generated = Document.browse()
        skipped = []
        for contract in self.contract_ids:
            template = contract.labor_template_id
            if not template:
                skipped.append(contract.employee_id.name or contract.display_name)
                continue
            doc = Document.generate_from_template(contract, template, "contract")
            contract.document_state = "generated"
            generated |= doc
        self.generated_document_ids = generated
        if skipped:
            raise UserError(
                _(
                    "Los siguientes contratos no tienen plantilla laboral asignada "
                    "y no se generaron: %s. El resto sí se generó correctamente "
                    "(%s documentos)."
                )
                % (", ".join(skipped), len(generated))
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Documentos generados"),
            "res_model": "hr.labor.document",
            "view_mode": "list,form",
            "domain": [("id", "in", generated.ids)],
        }
