from odoo import fields, models


class StockPicking(models.Model):
    """Campos del "Formulario de operaciones" pedidos en el documento de
    diseño del ticket 22: "Crear campos de: Número OP: Ingresar una OP
    vigente / Número OT: Ingresar una OT vigente".

    Se implementan como texto libre, igual que el precedente existente en
    step_management_costs/wizard/out_of_op_classifier.py (campo op_names):
    no hay en el código un modelo formal de OP/OT contra el cual validar,
    y el documento no lo pide ("vigente" es responsabilidad de quien
    escribe el dato, no una validación de sistema)."""

    _inherit = "stock.picking"

    num_op = fields.Char(
        string="Número OP",
        help="OP (Orden de Proceso/Presupuesto) vigente asociada a esta operación.",
    )
    num_ot = fields.Char(
        string="Número OT",
        help="OT (Orden de Trabajo) vigente asociada a esta operación: "
             "Cosecha, BPA o Maquinaria.",
    )
