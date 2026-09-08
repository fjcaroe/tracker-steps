"""Lectura conciliable del gasto/ingreso real desde la contabilidad.

Principio (ADR-001 D-B / plan D01):
- el valor sale EXCLUSIVAMENTE de apuntes contables **publicados**
  (`account.move.line.parent_state == 'posted'`) imputados por distribución
  analítica (`account.move.line.analytic_distribution`);
- no se crea una segunda tabla de montos: esto es sólo lectura.

Supuestos que requieren validación de Contabilidad (D01/D15) — cambiarlos es un
cambio acotado a este archivo:

  A1. Valor = `account.move.line.balance` prorrateado por el porcentaje de la
      distribución analítica que apunta a la cuenta del centro.
  A2. Naturaleza (costo/ingreso) = `account_type` de la cuenta del apunte:
      'expense*' → costo (balance deudor, positivo); 'income*' → ingreso
      (balance acreedor, se muestra positivo). Otros tipos se ignoran.
  A3. Grupo presupuesto = `product_id._get_management_budget_group()` (producto
      → subcategoría → categoría). Sin producto o sin grupo → «Sin clasificar».
  A4. Reversa / nota de crédito: se refleja con su signo real (invierte el
      balance); no se «corrige» a mano.
  A5. Multimoneda: se parte de `balance` (moneda de compañía) y se convierte a
      la moneda del presupuesto a la fecha de cada apunte.
"""

import re

from odoo import fields, models, _
from odoo.exceptions import UserError

from .budget_import import MONTH_KEY_BY_NUMBER


class StepManagementOperationalBudgetActuals(models.Model):
    _inherit = "step.management.operational.budget"

    def _season_date_range(self):
        """Rango de fechas por defecto de la temporada (mayo–abril heredado)."""
        self.ensure_one()
        years = [int(v) for v in re.findall(r"\b\d{4}\b", self.season or "")]
        base_year = years[0] if years else (self.date.year if self.date else fields.Date.context_today(self).year)
        end_year = years[1] if len(years) > 1 else base_year + 1
        return fields.Date.to_date("%s-05-01" % base_year), fields.Date.to_date("%s-04-30" % end_year)

    def _read_analytic_actuals(self, date_from=None, date_to=None):
        """Devuelve buckets agregados:
        {center_id, group_id, month, flow_type, actual_amount, actual_qty,
         move_line_ids}. Sólo apuntes publicados."""
        self.ensure_one()
        if not date_from or not date_to:
            d_from, d_to = self._season_date_range()
            date_from = date_from or d_from
            date_to = date_to or d_to

        centers = self.allocation_ids.center_id | self.line_ids.center_id
        duplicates = self._duplicate_analytic_centers()
        if duplicates:
            raise UserError(_(
                "No es posible comparar con el real porque varios centros del "
                "presupuesto comparten una cuenta analítica: %s"
            ) % "; ".join(
                ", ".join(group.mapped("display_name")) for group in duplicates
            ))
        account_to_center = {
            c.analytic_account_id.id: c for c in centers if c.analytic_account_id
        }
        if not account_to_center:
            return []

        move_lines = self.env["account.move.line"].search([
            ("parent_state", "=", "posted"),
            ("date", ">=", date_from), ("date", "<=", date_to),
            ("company_id", "=", self.company_id.id),
            ("display_type", "in", ("product", False)),
        ])

        buckets = {}
        for mline in move_lines:
            if not mline.analytic_distribution:
                continue
            account_type = mline.account_id.account_type or ""
            if account_type.startswith("expense"):
                flow_type, sign = "cost", 1.0
            elif account_type.startswith("income"):
                flow_type, sign = "income", -1.0
            else:
                continue
            distribution = mline.analytic_distribution or {}
            # cada clave puede ser "12" o "12,34" (combinación multi-plan)
            pct_for_center = {}
            for raw_key, pct in distribution.items():
                for token in str(raw_key).split(","):
                    try:
                        acc_id = int(token)
                    except (TypeError, ValueError):
                        continue
                    if acc_id in account_to_center:
                        pct_for_center[acc_id] = pct_for_center.get(acc_id, 0.0) + pct
            if not pct_for_center:
                continue

            month_key = MONTH_KEY_BY_NUMBER.get(mline.date.month)
            group = (
                mline.product_id._get_management_budget_group(self.company_id)
                if mline.product_id else False
            )
            group_id = group.id if group else False
            for acc_id, pct in pct_for_center.items():
                center = account_to_center[acc_id]
                company_amount = sign * mline.balance * (pct / 100.0)
                amount = self.company_id.currency_id._convert(
                    company_amount, self.currency_id, self.company_id,
                    mline.date, round=False,
                )
                quantity_sign = -1.0 if company_amount < 0 else 1.0
                qty = quantity_sign * (mline.quantity or 0.0) * (pct / 100.0)
                key = (center.id, group_id, month_key, flow_type)
                bucket = buckets.setdefault(key, {
                    "center_id": center.id, "group_id": group_id,
                    "month": month_key, "flow_type": flow_type,
                    "actual_amount": 0.0, "actual_qty": 0.0,
                    "move_line_ids": self.env["account.move.line"],
                })
                bucket["actual_amount"] += amount
                bucket["actual_qty"] += qty
                bucket["move_line_ids"] |= mline
        return list(buckets.values())

    def action_open_variance(self):
        self.ensure_one()
        d_from, d_to = self._season_date_range()
        return {
            "type": "ir.actions.act_window",
            "name": "Presupuesto vs. real",
            "res_model": "step.management.budget.variance.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_budget_id": self.id,
                "default_date_from": fields.Date.to_string(d_from),
                "default_date_to": fields.Date.to_string(d_to),
            },
        }
