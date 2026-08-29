from copy import deepcopy

from odoo import models
from odoo.tools import SQL


class AccountReport(models.Model):
    _inherit = "account.report"

    def _init_options_custom(self, options, previous_options):
        """Agrega columnas basadas en importes históricos almacenados.

        Cada columna operacional recibe su propio grupo de opciones. Por eso
        el motor vuelve a ejecutar la consulta usando
        ``account_move_line.operational_*``; no convierte el total al tipo de
        cambio de la fecha del informe.
        """
        super()._init_options_custom(options, previous_options)
        currency = self.env.company.operational_currency_id
        # Sólo se duplica una columna cuando todas las hojas del informe se
        # resuelven mediante expresiones domain/aggregation. Reportes con
        # handlers SQL propios (Libro Mayor, Antigüedad, Flujo de Caja, etc.)
        # requieren un adaptador específico; mostrarlos como operacionales
        # convertiría una columna CLP en una columna falsamente rotulada USD.
        engines = set(self.line_ids.expression_ids.mapped("engine"))
        supported_engines = {"domain", "aggregation", "cross_report"}
        supports_stored_operational = (
            "domain" in engines and engines.issubset(supported_engines)
        )
        if not currency or not supports_stored_operational:
            return
        enabled = previous_options.get("step_show_operational_currency", True)
        options["step_show_operational_currency"] = bool(enabled)
        options["step_operational_currency"] = {
            "id": currency.id,
            "name": currency.name,
            "symbol": currency.symbol,
        }
        if not enabled:
            return

        original_groups = options.get("column_groups", {})
        expanded_columns = []
        for column in list(options.get("columns", [])):
            expanded_columns.append(column)
            if column.get("figure_type") != "monetary":
                continue
            source_key = column.get("column_group_key")
            if source_key not in original_groups:
                continue
            operational_key = "%s__step_operational" % source_key
            if operational_key not in options["column_groups"]:
                group = deepcopy(original_groups[source_key])
                group.setdefault("forced_options", {})[
                    "step_use_operational_values"
                ] = True
                options["column_groups"][operational_key] = group
            expanded_columns.append({
                **column,
                "column_group_key": operational_key,
                "name": "%s (%s)" % (column.get("name") or "Importe", currency.name),
                "step_operational_currency_column": True,
                "sortable": False,
            })
        options["columns"] = expanded_columns

    def _compute_formula_batch_with_engine_domain(
        self, options, date_scope, formulas_dict, current_groupby,
        next_groupby, offset=0, limit=None, warnings=None,
    ):
        if options.get("step_use_operational_values"):
            report = self.with_context(step_operational_report=True)
            return super(AccountReport, report)._compute_formula_batch_with_engine_domain(
                options, date_scope, formulas_dict, current_groupby,
                next_groupby, offset=offset, limit=limit, warnings=warnings,
            )
        return super()._compute_formula_batch_with_engine_domain(
            options, date_scope, formulas_dict, current_groupby,
            next_groupby, offset=offset, limit=limit, warnings=warnings,
        )

    def _currency_table_apply_rate(self, value: SQL) -> SQL:
        if self.env.context.get("step_operational_report"):
            expression = value.code.strip()
            replacements = {
                "account_move_line.balance": "account_move_line.operational_balance",
                "account_move_line.debit": "account_move_line.operational_debit",
                "account_move_line.credit": "account_move_line.operational_credit",
            }
            if expression in replacements:
                return SQL(replacements[expression])
        return super()._currency_table_apply_rate(value)

    def _build_column_dict(
        self, col_value, col_data, options=None, currency=False, digits=1,
        column_expression=None, has_sublines=False, report_line_id=None,
    ):
        if (col_data or {}).get("step_operational_currency_column"):
            currency = self.env.company.operational_currency_id
        return super()._build_column_dict(
            col_value, col_data, options=options, currency=currency,
            digits=digits, column_expression=column_expression,
            has_sublines=has_sublines, report_line_id=report_line_id,
        )
