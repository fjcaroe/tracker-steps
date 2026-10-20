/** @odoo-module **/
import { onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ExportDashboard } from "@step_export/js/dashboard";

export class ComparativeExportDashboard extends ExportDashboard {
    setup() {
        super.setup();
        Object.assign(this.state, {
            filters: { season_id: "", month: "", week: "" }, comparison: null,
            comparisonLoading: true, comparisonError: "",
        });
        this.comparisonRequest = 0;
        onWillStart(() => this.loadComparison());
    }
    async loadComparison() {
        const request = ++this.comparisonRequest;
        this.state.comparisonLoading = true;
        this.state.comparisonError = "";
        try {
            const data = await this.orm.call("step.export.sales.program", "dashboard_comparison", [], {
                filters: { ...this.state.filters },
            });
            if (request === this.comparisonRequest) this.state.comparison = data;
        } catch (error) {
            if (request === this.comparisonRequest) {
                this.state.comparison = null;
                this.state.comparisonError = "No se pudo cargar el comparativo. Revisa tus permisos o vuelve a intentar.";
            }
        } finally {
            if (request === this.comparisonRequest) this.state.comparisonLoading = false;
        }
    }
    changeFilter(key, event) {
        this.state.filters[key] = event.target.value;
        if (key === "month") this.state.filters.week = "";
        return this.loadComparison();
    }
    formatValue(value) {
        return value === null || value === undefined ? "—" : new Intl.NumberFormat("es-CL", {
            maximumFractionDigits: 1,
        }).format(value);
    }
}
registry.category("actions").add("step_export.dashboard", ComparativeExportDashboard, { force: true });
