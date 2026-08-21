from odoo import fields, models


class AccountReport(models.Model):
    _inherit = "account.report"

    def _init_options_custom(self, options, previous_options):
        super()._init_options_custom(options, previous_options)

        monetary_columns = [
            column
            for column in options.get("columns", [])
            if column.get("figure_type") == "monetary"
            and column.get("expression_label") != "amount_currency"
            and not column.get("step_presentation_currency_id")
            and not column.get("step_company_currency_column")
        ]
        if not monetary_columns:
            return

        company_currency = self.env.company.currency_id
        available_currencies = self.env["res.currency"].search(
            [("active", "=", True)], order="name"
        )
        rated_currency_ids = set(
            self.env["res.currency.rate"]
            .search(
                [
                    ("currency_id", "in", available_currencies.ids),
                    ("company_id", "in", [False, self.env.company.id]),
                ]
            )
            .mapped("currency_id")
            .ids
        )
        foreign_currencies = (available_currencies - company_currency).filtered(
            lambda currency: currency.id in rated_currency_ids
        )
        if not foreign_currencies:
            return

        requested_ids = previous_options.get("step_presentation_currency_ids")
        if requested_ids is None:
            default_currency = foreign_currencies.filtered(lambda currency: currency.name == "USD")[:1]
            requested_ids = default_currency.ids

        selected_currencies = foreign_currencies.filtered(
            lambda currency: currency.id in requested_ids
        )
        options["step_presentation_currency_ids"] = selected_currencies.ids
        options["step_presentation_currencies"] = [
            {
                "id": currency.id,
                "name": currency.name,
                "symbol": currency.symbol,
                "selected": currency in selected_currencies,
            }
            for currency in foreign_currencies
        ]
        options["step_company_currency"] = {
            "id": company_currency.id,
            "name": company_currency.name,
            "symbol": company_currency.symbol,
        }

        if not selected_currencies:
            return

        expanded_columns = []
        for column in options["columns"]:
            is_convertible = (
                column.get("figure_type") == "monetary"
                and column.get("expression_label") != "amount_currency"
                and not column.get("step_presentation_currency_id")
                and not column.get("step_company_currency_column")
            )
            if not is_convertible:
                expanded_columns.append(column)
                continue

            original_name = column.get("name") or "Importe"
            expanded_columns.append(
                {
                    **column,
                    "name": f"{original_name} ({company_currency.name})",
                    "step_company_currency_column": True,
                }
            )
            for currency in selected_currencies:
                expanded_columns.append(
                    {
                        **column,
                        "name": f"{original_name} ({currency.name})",
                        "sortable": False,
                        "step_presentation_currency_id": currency.id,
                    }
                )

        options["columns"] = expanded_columns

    def _build_column_dict(
        self,
        col_value,
        col_data,
        options=None,
        currency=False,
        digits=1,
        column_expression=None,
        has_sublines=False,
        report_line_id=None,
    ):
        presentation_currency_id = (col_data or {}).get(
            "step_presentation_currency_id"
        )
        if presentation_currency_id and isinstance(col_value, (int, float)):
            options = options or {}
            presentation_currency = self.env["res.currency"].browse(
                presentation_currency_id
            ).exists()
            if presentation_currency:
                column_group_key = (col_data or {}).get("column_group_key")
                forced_options = options.get("column_groups", {}).get(
                    column_group_key, {}
                ).get("forced_options", {})
                date_options = forced_options.get("date") or options.get("date", {})
                conversion_date = fields.Date.to_date(
                    date_options.get("date_to") or fields.Date.context_today(self)
                )
                col_value = self.env.company.currency_id._convert(
                    col_value,
                    presentation_currency,
                    self.env.company,
                    conversion_date,
                )
                currency = presentation_currency

        return super()._build_column_dict(
            col_value,
            col_data,
            options=options,
            currency=currency,
            digits=digits,
            column_expression=column_expression,
            has_sublines=has_sublines,
            report_line_id=report_line_id,
        )
