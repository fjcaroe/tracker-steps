/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";
import { AccountReportHeader } from "@account_reports/components/account_report/header/header";

patch(AccountReportFilters.prototype, {
    async stepToggleOperationalCurrency() {
        await this.controller.updateOption(
            "step_show_operational_currency",
            !this.controller.options.step_show_operational_currency,
            true
        );
    },
});

patch(AccountReportHeader.prototype, {
    get subheaders() {
        const columns = this.controller.options.columns || [];
        const lineColumns = this.controller.lines[0]?.columns || [];
        if (
            this.controller.options.step_show_operational_currency &&
            columns.length === lineColumns.length
        ) {
            return JSON.parse(JSON.stringify(columns));
        }
        return super.subheaders;
    },
});
