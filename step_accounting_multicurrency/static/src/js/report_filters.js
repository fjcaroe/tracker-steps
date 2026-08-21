/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { AccountReportHeader } from "@account_reports/components/account_report/header/header";

patch(AccountReportFilters.prototype, {
    get stepPresentationCurrencyLabel() {
        const companyCurrency = this.controller.options.step_company_currency;
        const selectedCurrencies = (
            this.controller.options.step_presentation_currencies || []
        ).filter((currency) => currency.selected);
        return [companyCurrency, ...selectedCurrencies]
            .filter(Boolean)
            .map((currency) => currency.name)
            .join(" + ");
    },

    async stepTogglePresentationCurrency(currencyId) {
        const selectedIds = new Set(
            this.controller.options.step_presentation_currency_ids || []
        );
        if (selectedIds.has(currencyId)) {
            selectedIds.delete(currencyId);
        } else {
            selectedIds.add(currencyId);
        }
        await this.controller.updateOption(
            "step_presentation_currency_ids",
            [...selectedIds],
            true
        );
    },
});

patch(AccountReportHeader.prototype, {
    get subheaders() {
        const columns = this.controller.options.columns || [];
        const lineColumns = this.controller.lines[0]?.columns || [];
        if (
            this.controller.options.step_presentation_currency_ids?.length &&
            columns.length === lineColumns.length
        ) {
            return JSON.parse(JSON.stringify(columns));
        }
        return super.subheaders;
    },
});
