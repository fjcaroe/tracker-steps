# -*- coding: utf-8 -*-
"""Resumen y exportación del flujo de caja.

Todo se deriva de `_summary_matrix()`, el mismo dato que alimenta las hojas y
los KPI. No hay una segunda tabla de totales que pueda desincronizarse.
"""

import base64
import io
import logging

from markupsafe import Markup, escape

from odoo import _, api, fields, models

from .cashflow_line import BUCKET_CODES

_logger = logging.getLogger(__name__)


class StepCashflowSummary(models.Model):
    _inherit = "step.cashflow"

    summary_html = fields.Html(
        string="Resumen", compute="_compute_summary_html", sanitize=False,
        help="Resumen acumulado derivado del mismo detalle que las hojas.",
    )

    @api.depends("line_ids.amount_flow", "line_ids.amount_aux", "line_ids.bucket", "line_ids.excluded",
                 "opening_balance", "currency_id", "aux_currency_id", "applied_rate")
    def _compute_summary_html(self):
        for flow in self:
            flow.summary_html = flow._render_summary_html()

    def _format(self, amount, currency=None):
        currency = currency or self.currency_id
        if not currency:
            return "%.2f" % (amount or 0.0)
        return currency.format(amount or 0.0) if hasattr(currency, "format") else \
            "%s %s" % (currency.symbol or currency.name, round(amount or 0.0, currency.decimal_places))

    def _render_summary_html(self):
        self.ensure_one()
        rows = self.get_summary_rows()
        flow_label = self.currency_id.name or ""
        aux_label = self.aux_currency_id.name or ""
        labels = self._bucket_labels()
        hints = self._bucket_label_hints()
        head = ["<table class='table table-sm o_treasury_summary'><thead><tr>",
                "<th class='o_treasury_concept'>%s</th>" % _("Concepto de flujo")]
        for code in BUCKET_CODES:
            hint = hints.get(code)
            head.append("<th class='text-end'>%s%s</th>" % (
                escape(labels[code]),
                "<div class='o_treasury_week_hint'>%s</div>" % escape(hint) if hint else "",
            ))
        head.append("<th class='text-end'>%s %s</th>" % (_("Total"), flow_label))
        if self.aux_currency_id:
            head.append("<th class='text-end'>%s %s</th>" % (_("Total"), aux_label))
        head.append("</tr></thead><tbody>")

        body = []
        for row in rows:
            css = {
                "opening": "o_treasury_opening",
                "subtotal": "o_treasury_subtotal fw-bold",
                "closing": "o_treasury_closing fw-bold",
            }.get(row["kind"], "")
            cells = ["<tr class='%s'>" % css,
                     "<td class='o_treasury_concept'>%s</td>" % row["label"]]
            for code in BUCKET_CODES:
                value = row["buckets"].get(code, 0.0)
                cells.append("<td class='text-end'>%s</td>" % self._format(value))
            cells.append("<td class='text-end'>%s</td>" % self._format(row["total"]))
            if self.aux_currency_id:
                cells.append("<td class='text-end'>%s</td>" % self._format(
                    row["total_aux"], self.aux_currency_id))
            cells.append("</tr>")
            body.append("".join(cells))
        return Markup("".join(head) + "".join(body) + "</tbody></table>")

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------
    def _export_matrix(self):
        """Filas planas de la exportación: mismas cifras que la interfaz."""
        self.ensure_one()
        labels = self._bucket_labels()
        header = [_("Concepto de flujo")] + [labels[code] for code in BUCKET_CODES]
        header += ["%s %s" % (_("Total"), self.currency_id.name or "")]
        if self.aux_currency_id:
            header += ["%s %s" % (_("Total"), self.aux_currency_id.name or "")]
        rows = []
        for row in self.get_summary_rows():
            values = [row["label"]] + [row["buckets"].get(code, 0.0) for code in BUCKET_CODES]
            values.append(row["total"])
            if self.aux_currency_id:
                values.append(row["total_aux"])
            rows.append(values)
        return header, rows

    def action_export_xlsx(self):
        """Exportación de revisión, derivada del mismo dataset canónico."""
        self.ensure_one()
        try:
            import xlsxwriter
        except ImportError:
            from odoo.exceptions import UserError
            raise UserError(_("Falta la librería xlsxwriter en el servidor."))

        stream = io.BytesIO()
        book = xlsxwriter.Workbook(stream, {"in_memory": True})
        bold = book.add_format({"bold": True})
        money = book.add_format({"num_format": "#,##0.00"})
        money_bold = book.add_format({"num_format": "#,##0.00", "bold": True})

        sheet = book.add_worksheet(_("Resumen")[:31])
        header, rows = self._export_matrix()
        for column, label in enumerate(header):
            sheet.write(0, column, label, bold)
        for index, values in enumerate(rows, start=1):
            strong = values[0] in (_("Sub total recaudaciones"), _("Sub total pagos"), _("Saldo Caja"))
            sheet.write(index, 0, values[0], bold if strong else None)
            for column, value in enumerate(values[1:], start=1):
                sheet.write_number(index, column, float(value or 0.0),
                                   money_bold if strong else money)
        sheet.set_column(0, 0, 32)
        sheet.set_column(1, len(header), 16)

        detail = book.add_worksheet(_("Detalle")[:31])
        columns = [_("Hoja"), _("Concepto"), _("Nombre"), _("RUT"), _("Tipo Doc"),
                   _("Fecha Doc"), _("Num Doc"), _("Vencimiento"), _("Moneda Doc"),
                   _("Saldo Docto"), _("Semana"), _("Importe"), _("Excluida")]
        for column, label in enumerate(columns):
            detail.write(0, column, label, bold)
        sheets = dict(self._fields["line_ids"].comodel_name and
                      self.env["step.cashflow.line"]._fields["sheet"].selection or [])
        bucket_labels = self._bucket_labels()
        for index, line in enumerate(self.line_ids, start=1):
            detail.write(index, 0, sheets.get(line.sheet, line.sheet or ""))
            detail.write(index, 1, line.concept_id.display_name or "")
            detail.write(index, 2, line.partner_id.display_name or "")
            detail.write(index, 3, line.partner_vat or "")
            detail.write(index, 4, line.doc_type_name or "")
            detail.write(index, 5, str(line.doc_date or ""))
            detail.write(index, 6, line.doc_number or "")
            detail.write(index, 7, str(line.due_date or ""))
            detail.write(index, 8, line.currency_id.name or "")
            detail.write_number(index, 9, float(line.amount_origin or 0.0), money)
            detail.write(index, 10, bucket_labels.get(line.bucket, ""))
            detail.write_number(index, 11, float(line.amount_flow or 0.0), money)
            detail.write(index, 12, _("Sí") if line.excluded else _("No"))
        detail.set_column(0, len(columns), 18)

        book.close()
        stream.seek(0)
        attachment = self.env["ir.attachment"].create({
            "name": "%s.xlsx" % (self.name or "flujo"),
            "type": "binary",
            "datas": base64.b64encode(stream.read()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })
        self.message_post(body=_("Exportación XLSX generada por %s.") % self.env.user.display_name)
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }

    def action_export_pdf(self):
        """PDF de revisión derivado del mismo resumen canónico."""
        self.ensure_one()
        self.message_post(body=_("Exportación PDF generada por %s.")
                          % self.env.user.display_name)
        return self.env.ref(
            "step_account_treasury.action_report_treasury_review"
        ).report_action(self, config=False)

    @api.model
    def get_treasury_dashboard_data(self):
        """Payload compacto de la portada de Tesorería.

        Sólo resume el flujo más reciente de la compañía activa y reutiliza
        `_summary_matrix()`. No recalcula documentos contables ni abre una
        segunda fuente de totales.
        """
        company = self.env.company
        flows = self.search(
            [("company_id", "=", company.id)],
            order="start_date desc, id desc", limit=8,
        )
        current = flows.filtered(lambda flow: flow.state in ("draft", "in_progress"))[:1]
        current = current or flows.filtered(lambda flow: flow.state == "approved")[:1]
        current = current or flows[:1]

        state_labels = dict(self._fields["state"].selection)
        counts = {code: 0 for code in state_labels}
        for state, count in self._read_group(
                [("company_id", "=", company.id)], ["state"], ["__count"]):
            counts[state] = count

        result = {
            "company_name": company.display_name,
            "counts": counts,
            "current": False,
            "recent": [{
                "id": flow.id,
                "name": flow.display_name,
                "start_date": fields.Date.to_string(flow.start_date),
                "end_date": fields.Date.to_string(flow.end_date),
                "state": flow.state,
                "state_label": state_labels.get(flow.state, flow.state),
                "closing": flow._format(flow.closing_balance),
                "negative": flow.has_negative_cash,
            } for flow in flows],
        }
        if not current:
            return result

        current.ensure_one()
        matrix = current._summary_matrix()
        bucket_labels = current._bucket_labels()
        closing_values = [matrix["closing"][code] for code in BUCKET_CODES]
        low = min(closing_values) if closing_values else 0.0
        high = max(closing_values) if closing_values else 0.0
        spread = high - low
        points = []
        bucket_rows = []
        for index, code in enumerate(BUCKET_CODES):
            x = 10.0 + (80.0 * index / max(len(BUCKET_CODES) - 1, 1))
            y = 50.0 if not spread else 88.0 - (76.0 * (closing_values[index] - low) / spread)
            points.append({"x": round(x, 2), "y": round(y, 2)})
            bucket_rows.append({
                "code": code,
                "label": bucket_labels[code],
                "inflow": current._format(matrix["inflow_total"][code]),
                "outflow": current._format(matrix["outflow_total"][code]),
                "closing": current._format(matrix["closing"][code]),
                "negative": matrix["closing"][code] < 0,
            })
        result["current"] = {
            "id": current.id,
            "name": current.display_name,
            "state": current.state,
            "state_label": state_labels.get(current.state, current.state),
            "period": "%s — %s" % (current.start_date, current.end_date),
            "currency": current.currency_id.name,
            "opening": current._format(current.opening_balance),
            "inflow": current._format(current.total_inflow),
            "outflow": current._format(current.total_outflow),
            "minimum": current._format(current.min_balance),
            "closing": current._format(current.closing_balance),
            "negative": current.has_negative_cash,
            "line_count": current.line_count,
            "buckets": bucket_rows,
            "chart_points": " ".join("%s,%s" % (p["x"], p["y"]) for p in points),
            "chart_nodes": points,
        }
        return result

    def action_open_lines(self):
        """Drill-down al detalle canónico del flujo."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Detalle de %s") % self.display_name,
            "res_model": "step.cashflow.line",
            "view_mode": "list,form",
            "domain": [("cashflow_id", "=", self.id)],
            "context": {"search_default_group_sheet": 1, "default_cashflow_id": self.id},
        }
